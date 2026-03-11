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
 * Each <span data-run> is one run. Text nodes outside spans inherit the
 * container's current default style (passed as `defaultProps`).
 */
export function domToRuns(container: HTMLElement, defaultProps: TextProps): TextRun[] {
  const runs: TextRun[] = [];

  const walk = (node: ChildNode) => {
    if (node.nodeType === Node.TEXT_NODE) {
      const text = node.textContent ?? '';
      if (!text) return;
      // Inherit from closest ancestor span
      const parent = node.parentElement;
      const span   = parent?.closest('[data-run]') as HTMLElement | null;
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
      // Block elements = newline before content
      if (runs.length > 0) runs[runs.length - 1].text += '\n';
      node.childNodes.forEach(walk);
    } else {
      node.childNodes.forEach(walk);
    }
  };

  container.childNodes.forEach(walk);

  // Merge adjacent runs that share identical style
  const merged: TextRun[] = [];
  for (const run of runs) {
    const prev = merged[merged.length - 1];
    if (
      prev &&
      prev.bold       === run.bold       &&
      prev.italic     === run.italic     &&
      prev.fontFamily === run.fontFamily &&
      prev.fontSize   === run.fontSize   &&
      prev.color      === run.color
    ) {
      prev.text += run.text;
    } else {
      merged.push({ ...run });
    }
  }
  return merged;
}

/**
 * Apply a style to the current Selection (or an explicitly passed range) inside `container`.
 * Returns true if a range was found and acted on.
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

  const anchor = range.startContainer.parentElement?.closest('[data-run]') as HTMLElement | null;
  const existingBold       = anchor?.dataset.bold       === 'true';
  const existingItalic     = anchor?.dataset.italic     === 'true';
  const existingFontFamily = anchor?.dataset.fontFamily ?? 'Helvetica';
  const existingFontSize   = parseFloat(anchor?.dataset.fontSize ?? '12');
  const existingColor      = anchor?.dataset.color      ?? '#000000';

  const fragment = range.extractContents();

  const applyToSpan = (span: HTMLElement) => {
    if (style.bold !== undefined) span.dataset.bold = String(style.bold);
    if (style.italic !== undefined) span.dataset.italic = String(style.italic);
    if (style.fontFamily !== undefined && style.fontFamily !== '') span.dataset.fontFamily = style.fontFamily;
    if (style.fontSize !== undefined && style.fontSize !== '') span.dataset.fontSize = String(style.fontSize);
    if (style.color !== undefined && style.color !== '') span.dataset.color = style.color;

    const family = span.dataset.fontFamily ?? 'Helvetica';
    Object.assign(span.style, {
      fontFamily:  FONT_TO_CSS[family] ?? 'Helvetica, Arial, sans-serif',
      fontWeight:  span.dataset.bold   === 'true' ? 'bold'   : 'normal',
      fontStyle:   span.dataset.italic === 'true' ? 'italic' : 'normal',
      fontSize:    `${parseFloat(span.dataset.fontSize || '12') * scale}px`,
      color:       span.dataset.color,
      lineHeight:  '1.2',
      whiteSpace:  'pre-wrap',
    });
  };

  const spans = fragment.querySelectorAll('[data-run]');
  spans.forEach(span => applyToSpan(span as HTMLElement));

  const walkAndWrap = (node: Node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      if (node.textContent && node.textContent.length > 0) {
        const span = document.createElement('span');
        span.dataset.run = '1';
        span.dataset.bold       = String(style.bold       !== undefined ? style.bold       : existingBold);
        span.dataset.italic     = String(style.italic     !== undefined ? style.italic     : existingItalic);
        span.dataset.fontFamily = (style.fontFamily !== undefined && style.fontFamily !== '') ? style.fontFamily : existingFontFamily;
        span.dataset.fontSize   = String((style.fontSize !== undefined && style.fontSize !== '') ? style.fontSize : existingFontSize);
        span.dataset.color      = (style.color !== undefined && style.color !== '') ? style.color : existingColor;
        applyToSpan(span);
        node.parentNode?.insertBefore(span, node);
        span.appendChild(node);
      }
    } else if (node.nodeType === Node.ELEMENT_NODE) {
      const el = node as HTMLElement;
      if (el.dataset?.run) return;
      // Do not descend into block-level elements (DIV, P). Their inline content
      // is already handled by the applyToSpan pass over [data-run] spans above.
      // Descending and wrapping text nodes inside a block element causes those
      // wrapped spans to be re-inserted inside the block, forcing a new line.
      const tag = el.tagName;
      if (tag === 'DIV' || tag === 'P') return;
      Array.from(el.childNodes).forEach(walkAndWrap);
    }
  };

  Array.from(fragment.childNodes).forEach(walkAndWrap);

  const firstChild = fragment.firstChild;
  const lastChild = fragment.lastChild;
  
  range.insertNode(fragment);

  if (firstChild && lastChild) {
    const newRange = document.createRange();
    newRange.setStartBefore(firstChild);
    newRange.setEndAfter(lastChild);
    sel?.removeAllRanges();
    sel?.addRange(newRange);
  }
  return true;
}

/**
 * Build initial innerHTML for a contentEditable from a node's runs.
 * Each run becomes a <span data-run ...>.
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
    // Escape HTML entities in text, convert \n to <br>
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