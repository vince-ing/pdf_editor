// frontend/src/utils/textUtils.ts

import React from 'react';
import { FONT_TO_CSS, type TextProps, type TextRun } from '../types/textProps';

/** Convert a TextRun to inline CSS properties for a <span>. */
export function runToSpanStyle(run: TextRun, scale: number): React.CSSProperties {
  const family = run.fontFamily ?? 'Helvetica';
  return {
    fontFamily:  FONT_TO_CSS[family] ?? 'Helvetica, Arial, sans-serif',
    fontWeight:  run.bold   ? 'bold'   : 'normal',
    fontStyle:   run.italic ? 'italic' : 'normal',
    fontSize:    (run.fontSize ?? 12) * scale,
    color:       run.color ?? '#000000',
    lineHeight:  1.2,
    whiteSpace:  'pre-wrap',
  };
}

/** Flatten a TextRun[] to a plain string (for text_content fallback). */
export const runsToPlainText = (runs: TextRun[]): string => runs.map(r => r.text).join('');

/**
 * Walk a contentEditable div and extract TextRun[].
 */
export function domToRuns(container: HTMLElement, defaultProps: TextProps): TextRun[] {
  const runs: TextRun[] = [];

  const walk = (node: ChildNode) => {
    if (node.nodeType === Node.TEXT_NODE) {
      const text = node.textContent ?? '';
      if (!text) return;
      const span = (node.parentElement as HTMLElement | null)?.closest('[data-run]') as HTMLElement | null;
      if (span) {
        let size = parseFloat(span.dataset.fontSize ?? '');
        if (isNaN(size)) size = defaultProps.fontSize;
        runs.push({
          text,
          bold:       span.dataset.bold       === 'true',
          italic:     span.dataset.italic     === 'true',
          fontFamily: span.dataset.fontFamily ?? defaultProps.fontFamily,
          fontSize:   size,
          color:      span.dataset.color      ?? defaultProps.color,
        });
      } else {
        runs.push({
          text,
          bold:       defaultProps.isBold,
          italic:     defaultProps.isItalic,
          fontFamily: defaultProps.fontFamily,
          fontSize:   defaultProps.fontSize,
          color:      defaultProps.color,
        });
      }
    } else if (node.nodeName === 'BR') {
      if (runs.length > 0) runs[runs.length - 1].text += '\n';
      else runs.push({ text: '\n', bold: false, italic: false, fontFamily: defaultProps.fontFamily, fontSize: defaultProps.fontSize, color: defaultProps.color });
    } else if (node.nodeName === 'DIV' || node.nodeName === 'P') {
      if (runs.length > 0) runs[runs.length - 1].text += '\n';
      node.childNodes.forEach(walk);
    } else {
      node.childNodes.forEach(walk);
    }
  };

  container.childNodes.forEach(walk);

  const merged: TextRun[] = [];
  for (const run of runs) {
    const prev = merged[merged.length - 1];
    if (prev && prev.bold === run.bold && prev.italic === run.italic &&
        prev.fontFamily === run.fontFamily && prev.fontSize === run.fontSize &&
        prev.color === run.color) {
      prev.text += run.text;
    } else {
      merged.push({ ...run });
    }
  }
  return merged;
}

/**
 * Apply a style to the current Selection inside `container`.
 */
export function applyStyleToSelection(
  container: HTMLElement,
  style: Partial<{ bold: boolean; italic: boolean; fontFamily: string; fontSize: number; color: string }>,
  scale: number,
  explicitRange?: Range,
): boolean {
  const sel = window.getSelection();

  let range: Range | null = explicitRange ?? null;
  if (!range) {
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return false;
    range = sel.getRangeAt(0);
  }
  if (!container.contains(range.commonAncestorContainer)) return false;

  const styleSpan = (span: HTMLElement) => {
    if (style.bold       !== undefined)                           span.dataset.bold       = String(style.bold);
    if (style.italic     !== undefined)                           span.dataset.italic     = String(style.italic);
    if (style.fontFamily !== undefined && style.fontFamily !== '') span.dataset.fontFamily = style.fontFamily;
    if (style.fontSize   !== undefined)                           span.dataset.fontSize   = String(style.fontSize);
    if (style.color      !== undefined && style.color !== '')     span.dataset.color      = style.color;
    const family = span.dataset.fontFamily ?? 'Helvetica';
    Object.assign(span.style, {
      fontFamily: FONT_TO_CSS[family] ?? 'Helvetica, Arial, sans-serif',
      fontWeight: span.dataset.bold   === 'true' ? 'bold'   : 'normal',
      fontStyle:  span.dataset.italic === 'true' ? 'italic' : 'normal',
      fontSize:   `${parseFloat(span.dataset.fontSize || '12') * scale}px`,
      color:      span.dataset.color,
      lineHeight: '1.2',
      whiteSpace: 'pre-wrap',
    });
  };

  const cloneAttrs = (src: HTMLElement): HTMLElement => {
    const el = document.createElement('span');
    el.dataset.run        = '1';
    el.dataset.bold       = src.dataset.bold       ?? 'false';
    el.dataset.italic     = src.dataset.italic     ?? 'false';
    el.dataset.fontFamily = src.dataset.fontFamily ?? 'Helvetica';
    el.dataset.fontSize   = src.dataset.fontSize   ?? '12';
    el.dataset.color      = src.dataset.color      ?? '#000000';
    const family = el.dataset.fontFamily!;
    Object.assign(el.style, {
      fontFamily: FONT_TO_CSS[family] ?? 'Helvetica, Arial, sans-serif',
      fontWeight: el.dataset.bold   === 'true' ? 'bold'   : 'normal',
      fontStyle:  el.dataset.italic === 'true' ? 'italic' : 'normal',
      fontSize:   `${parseFloat(el.dataset.fontSize!) * scale}px`,
      color:      el.dataset.color,
      lineHeight: '1.2',
      whiteSpace: 'pre-wrap',
    });
    return el;
  };

  const allSpans = Array.from(container.querySelectorAll('[data-run]')) as HTMLElement[];
  const overlapping = allSpans.filter(s => range!.intersectsNode(s));
  if (overlapping.length === 0) return false;

  const styledPieces: { span: HTMLElement; selStart: number; selEnd: number }[] = [];

  for (const span of overlapping) {
    const textNode = span.firstChild as Text | null;
    if (!textNode || textNode.nodeType !== Node.TEXT_NODE) {
      styleSpan(span);
      styledPieces.push({ span, selStart: 0, selEnd: span.textContent?.length ?? 0 });
      continue;
    }

    const len = textNode.data.length;

    // When the range boundary is not inside this exact text node (e.g. the
    // range starts/ends in a different span or a parent element), treat this
    // span as fully covered — intersectsNode already confirmed it overlaps.
    const startOffset = range.startContainer === textNode ? range.startOffset : 0;
    const endOffset   = range.endContainer   === textNode ? range.endOffset   : len;

    if (startOffset === 0 && endOffset === len) {
      styleSpan(span);
      styledPieces.push({ span, selStart: 0, selEnd: len });
      continue;
    }

    const before   = textNode.data.slice(0, startOffset);
    const selected = textNode.data.slice(startOffset, endOffset);
    const after    = textNode.data.slice(endOffset);

    const parent = span.parentNode!;
    const next   = span.nextSibling;

    if (before) {
      const b = cloneAttrs(span);
      b.textContent = before;
      parent.insertBefore(b, next ?? null);
    }

    const s = cloneAttrs(span);
    s.textContent = selected;
    styleSpan(s);
    parent.insertBefore(s, next ?? null);
    styledPieces.push({ span: s, selStart: 0, selEnd: selected.length });

    if (after) {
      const a = cloneAttrs(span);
      a.textContent = after;
      parent.insertBefore(a, next ?? null);
    }

    span.remove();
  }

  // Restore selection to the styled region
  if (styledPieces.length > 0 && sel) {
    const first = styledPieces[0];
    const last  = styledPieces[styledPieces.length - 1];
    const firstText = first.span.firstChild as Text | null;
    const lastText  = last.span.firstChild  as Text | null;
    if (firstText && lastText) {
      const r = document.createRange();
      r.setStart(firstText, first.selStart);
      r.setEnd(lastText,   last.selEnd);
      sel.removeAllRanges();
      sel.addRange(r);
    }
  }

  return true;
}

/**
 * Build initial innerHTML for a contentEditable from a node's runs.
 */
export function runsToHtml(runs: TextRun[], defaultProps: TextProps, scale: number): string {
  if (!runs || runs.length === 0) return '';
  return runs.map(run => {
    const family  = run.fontFamily ?? defaultProps.fontFamily;
    const fs      = run.fontSize   ?? defaultProps.fontSize;
    const color   = run.color      ?? defaultProps.color;
    const bold    = run.bold       ?? false;
    const italic  = run.italic     ?? false;
    const cssFont = FONT_TO_CSS[family] ?? 'Helvetica, Arial, sans-serif';
    const escaped = run.text
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/\n/g, '<br>');
    return `<span data-run="1" data-bold="${bold}" data-italic="${italic}" `
      + `data-font-family="${family}" data-font-size="${fs}" data-color="${color}" `
      + `style="font-family:${cssFont};font-weight:${bold ? 'bold' : 'normal'};`
      + `font-style:${italic ? 'italic' : 'normal'};font-size:${fs * scale}px;`
      + `color:${color};line-height:1.2;white-space:pre-wrap">${escaped}</span>`;
  }).join('');
}