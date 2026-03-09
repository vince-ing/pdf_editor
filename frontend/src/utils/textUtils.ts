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
        runs.push({
          text,
          bold:       span.dataset.bold       === 'true',
          italic:     span.dataset.italic     === 'true',
          fontFamily: span.dataset.fontFamily ?? defaultProps.fontFamily,
          fontSize:   parseFloat(span.dataset.fontSize ?? String(defaultProps.fontSize)),
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

  // Use explicit range if provided (survives React state-update cycles), otherwise
  // fall back to live selection.
  let range: Range | null = explicitRange ?? null;
  if (!range) {
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return false;
    range = sel.getRangeAt(0);
  }
  if (!container.contains(range.commonAncestorContainer)) return false;

  const span = document.createElement('span');
  span.dataset.run = '1';

  // Inherit current style from the span the cursor/selection starts in
  const anchor = range.startContainer.parentElement?.closest('[data-run]') as HTMLElement | null;
  const existingBold       = anchor?.dataset.bold       === 'true';
  const existingItalic     = anchor?.dataset.italic     === 'true';
  const existingFontFamily = anchor?.dataset.fontFamily ?? 'Helvetica';
  const existingFontSize   = parseFloat(anchor?.dataset.fontSize ?? '12');
  const existingColor      = anchor?.dataset.color      ?? '#000000';

  span.dataset.bold       = String(style.bold       !== undefined ? style.bold       : existingBold);
  span.dataset.italic     = String(style.italic     !== undefined ? style.italic     : existingItalic);
  span.dataset.fontFamily = style.fontFamily ?? existingFontFamily;
  span.dataset.fontSize   = String(style.fontSize   !== undefined ? style.fontSize   : existingFontSize);
  span.dataset.color      = style.color      ?? existingColor;

  const family = span.dataset.fontFamily;
  Object.assign(span.style, {
    fontFamily:  FONT_TO_CSS[family] ?? 'Helvetica, Arial, sans-serif',
    fontWeight:  span.dataset.bold   === 'true' ? 'bold'   : 'normal',
    fontStyle:   span.dataset.italic === 'true' ? 'italic' : 'normal',
    fontSize:    `${parseFloat(span.dataset.fontSize) * scale}px`,
    color:       span.dataset.color,
    lineHeight:  '1.2',
    whiteSpace:  'pre-wrap',
  });

  try {
    range.surroundContents(span);
  } catch {
    // surroundContents throws when selection crosses element boundaries
    // Fall back: extract → wrap → insert
    const fragment = range.extractContents();
    span.appendChild(fragment);
    range.insertNode(span);
  }

  // Restore selection to the new span
  const newRange = document.createRange();
  newRange.selectNodeContents(span);
  sel?.removeAllRanges();
  sel?.addRange(newRange);
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