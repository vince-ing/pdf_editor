// frontend/src/components/canvas/Canvas.tsx
//
// Rich text text boxes:
//  • contentEditable div — supports mixed bold/italic/color/font per selection
//  • Ctrl+B / Ctrl+I toggle bold/italic on current selection
//  • When a node is selected (select/edittext tool), right-panel textProps
//    are pre-populated from the node's runs (or top-level style) and any
//    change in the panel is applied live to the selection or whole node
//  • Enter commits, Escape cancels (transient) / reverts (committed)
//  • On commit, DOM is serialized → TextRun[] for the backend

import { useRef, useEffect, useState, useCallback } from 'react';
import { engineApi } from '../../api/client';
import { usePdfCanvas } from '../../hooks/usePdfCanvas';
import { usePageChars } from '../../hooks/usePageChars';
import { useDragSelection } from '../../hooks/useDragSelection';
import * as pdfjsLib from 'pdfjs-dist';
import {
  FONT_TO_CSS, DEFAULT_TEXT_PROPS,
  type TextProps, type TextRun,
} from '../../types/textProps';

type ToolId = import('./Toolbar').ToolId;

// ── Data types ─────────────────────────────────────────────────────────────────

interface AnnotationNode {
  id:           string;
  node_type:    string;
  bbox?:        { x: number; y: number; width: number; height: number };
  color?:       string;
  opacity?:     number;
  text_content?: string;
  font_size?:   number;
  font_family?: string;
  bold?:        boolean;
  italic?:      boolean;
  runs?:        TextRun[];
}
interface PageNode {
  id: string; page_number?: number; rotation?: number;
  metadata?: { width: number; height: number };
  crop_box?: { x: number; y: number; width: number; height: number };
  children?: AnnotationNode[];
}
interface DocumentState { children?: PageNode[]; file_name?: string; }
interface CanvasProps {
  pdfDoc?:            pdfjsLib.PDFDocumentProxy | null;
  documentState?:     DocumentState | null;
  activeTool:         ToolId;
  scale:              number;
  textProps?:         TextProps;
  onTextPropsChange?: (p: TextProps) => void;
  onAnnotationAdded?: () => Promise<void>;
  onDocumentChanged?: () => Promise<void>;
  onTextSelected?:    (text: string) => void;
  pageRefs?:          React.MutableRefObject<(HTMLDivElement | null)[]>;
}

// ── Constants ──────────────────────────────────────────────────────────────────

const CURSORS: Partial<Record<ToolId, string>> = {
  hand: 'grab', select: 'default', zoom: 'zoom-in',
  addtext: 'crosshair', edittext: 'text',
  highlight: 'crosshair', redact: 'crosshair', crop: 'crosshair', underline: 'crosshair',
};
const SEL_COLOR: Partial<Record<ToolId, string>> = {
  highlight: 'rgba(245,158,11,0.25)', redact: 'rgba(239,68,68,0.25)',
  select: 'rgba(74,144,226,0.2)', crop: 'rgba(0,0,0,0)', underline: 'rgba(255,255,255,0.1)',
};

// ── Rich-text helpers ──────────────────────────────────────────────────────────

/** Convert a TextRun to inline CSS properties for a <span>. */
function runToSpanStyle(run: TextRun, scale: number): React.CSSProperties {
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
const runsToPlainText = (runs: TextRun[]): string => runs.map(r => r.text).join('');

/**
 * Walk a contentEditable div and extract TextRun[].
 * Each <span data-run> is one run. Text nodes outside spans inherit the
 * container's current default style (passed as `defaultProps`).
 */
function domToRuns(container: HTMLElement, defaultProps: TextProps): TextRun[] {
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
function applyStyleToSelection(
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
function runsToHtml(runs: TextRun[], defaultProps: TextProps, scale: number): string {
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

// ── Resize handles ─────────────────────────────────────────────────────────────

type HandleDef = { id: string; cursor: string; tx: number; ty: number; dx: 1|0|-1; dy: 1|0|-1 };
const HANDLES: HandleDef[] = [
  { id: 'nw', cursor: 'nw-resize', tx: 0,   ty: 0,   dx: -1, dy: -1 },
  { id: 'n',  cursor: 'n-resize',  tx: 0.5, ty: 0,   dx:  0, dy: -1 },
  { id: 'ne', cursor: 'ne-resize', tx: 1,   ty: 0,   dx:  1, dy: -1 },
  { id: 'e',  cursor: 'e-resize',  tx: 1,   ty: 0.5, dx:  1, dy:  0 },
  { id: 'se', cursor: 'se-resize', tx: 1,   ty: 1,   dx:  1, dy:  1 },
  { id: 's',  cursor: 's-resize',  tx: 0.5, ty: 1,   dx:  0, dy:  1 },
  { id: 'sw', cursor: 'sw-resize', tx: 0,   ty: 1,   dx: -1, dy:  1 },
  { id: 'w',  cursor: 'w-resize',  tx: 0,   ty: 0.5, dx: -1, dy:  0 },
];
const MIN_W = 40, MIN_H = 16;
type GeoRect = { x: number; y: number; w: number; h: number };

function useResizeDrag(scale: number, onUpdate: (g: GeoRect) => void) {
  return useCallback((e: React.PointerEvent, handle: HandleDef, snap: GeoRect) => {
    e.preventDefault(); e.stopPropagation();
    const sx = e.clientX, sy = e.clientY;
    const calc = (ev: PointerEvent): GeoRect => {
      const ddx = (ev.clientX - sx) / scale, ddy = (ev.clientY - sy) / scale;
      let { x, y, w, h } = snap;
      if (handle.dx ===  1) w = Math.max(MIN_W, snap.w + ddx);
      if (handle.dx === -1) { w = Math.max(MIN_W, snap.w - ddx); x = snap.x + snap.w - w; }
      if (handle.dy ===  1) h = Math.max(MIN_H, snap.h + ddy);
      if (handle.dy === -1) { h = Math.max(MIN_H, snap.h - ddy); y = snap.y + snap.h - h; }
      return { x, y, w, h };
    };
    const onMove = (ev: PointerEvent) => onUpdate(calc(ev));
    const onUp   = (ev: PointerEvent) => { onUpdate(calc(ev)); window.removeEventListener('pointermove', onMove); window.removeEventListener('pointerup', onUp); };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  }, [scale, onUpdate]);
}

function ResizeHandles({ geo, scale, onResize }: {
  geo: GeoRect; scale: number;
  onResize: (e: React.PointerEvent, h: HandleDef, snap: GeoRect) => void;
}) {
  return (
    <>
      {HANDLES.map(h => (
        <div key={h.id} onPointerDown={e => onResize(e, h, geo)} style={{
          position: 'absolute',
          left: `calc(${h.tx * 100}% - 4px)`, top: `calc(${h.ty * 100}% - 4px)`,
          width: 8, height: 8, background: '#fff',
          border: '1.5px solid #4a90e2', borderRadius: 1.5,
          cursor: h.cursor, zIndex: 4, boxShadow: '0 1px 3px rgba(0,0,0,0.25)',
        }} />
      ))}
    </>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// RichTextEditor — shared contentEditable core used by both Transient and Node
// ══════════════════════════════════════════════════════════════════════════════

interface RichTextEditorProps {
  initialHtml:   string;
  scale:         number;
  textProps:     TextProps;
  isTransient:   boolean;    // true = new box, false = editing committed node
  onCommit:      (runs: TextRun[], plainText: string) => void;
  onCancel:      () => void;
  onPropsChange?:(p: TextProps) => void; // reflect selection style back to panel
}

// ID used to identify the right panel — blur is suppressed when focus moves there
const RIGHT_PANEL_ID = 'text-props-panel';

function RichTextEditor({
  initialHtml, scale, textProps, isTransient, onCommit, onCancel, onPropsChange,
}: RichTextEditorProps) {
  const editorRef     = useRef<HTMLDivElement>(null);
  // Keep a live ref to textProps so event handlers always see current values
  // without needing to be re-created on every render
  const textPropsRef  = useRef(textProps);
  useEffect(() => { textPropsRef.current = textProps; }, [textProps]);

  // Set initial HTML once
  useEffect(() => {
    if (editorRef.current && initialHtml !== undefined) {
      editorRef.current.innerHTML = initialHtml;
      const range = document.createRange();
      range.selectNodeContents(editorRef.current);
      range.collapse(false);
      const sel = window.getSelection();
      sel?.removeAllRanges();
      sel?.addRange(range);
      editorRef.current.focus();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // pendingStyle holds style overrides that should apply to the NEXT typed character.
  const pendingStyle = useRef<Partial<{ bold: boolean; italic: boolean; fontFamily: string; fontSize: number; color: string }>>({});

  // savedRange preserves the user's text selection across React state updates.
  // Set by reflectSelection before calling onPropsChange; consumed by the textProps effect.
  const savedRange = useRef<Range | null>(null);

  // Track previous textProps to detect what changed
  const prevProps = useRef(textProps);

  useEffect(() => {
    const p = textProps, pp = prevProps.current;
    const changes: typeof pendingStyle.current = {};
    if (p.isBold     !== pp.isBold)     changes.bold       = p.isBold;
    if (p.isItalic   !== pp.isItalic)   changes.italic     = p.isItalic;
    if (p.fontFamily !== pp.fontFamily) changes.fontFamily  = p.fontFamily;
    if (p.fontSize   !== pp.fontSize)   changes.fontSize   = p.fontSize;
    if (p.color      !== pp.color)      changes.color      = p.color;
    prevProps.current = p;

    if (!Object.keys(changes).length || !editorRef.current) return;

    const sel = window.getSelection();
    const rangeToUse = savedRange.current;
    const liveNonCollapsed = sel && !sel.isCollapsed && sel.rangeCount > 0 &&
      editorRef.current.contains(sel.anchorNode);
    const hasSelection = rangeToUse || liveNonCollapsed;

      changes,
      hasSavedRange: !!rangeToUse,
      savedRangeText: rangeToUse?.toString(),
      liveNonCollapsed,
      liveSelectionText: liveNonCollapsed ? sel?.toString() : null,
      editorHTML: editorRef.current.innerHTML.slice(0, 200),
    });

    if (hasSelection) {
      if (rangeToUse && sel) {
        sel.removeAllRanges();
        sel.addRange(rangeToUse);
      }
      applyStyleToSelection(editorRef.current, changes, scale);
      savedRange.current = null;
    } else {
      pendingStyle.current = { ...pendingStyle.current, ...changes };
    }
  }, [textProps, scale]);

  const commit = useCallback(() => {
    if (!editorRef.current) return;
    const runs = domToRuns(editorRef.current, textPropsRef.current);
    const plain = runsToPlainText(runs);
    if (plain.trim()) onCommit(runs, plain);
    else onCancel();
  }, [onCommit, onCancel]);

  // Guard blur: if focus moved into the panel, refocus the editor instead of committing
  const handleBlur = useCallback((e: React.FocusEvent) => {
    const relatedTarget = e.relatedTarget as HTMLElement | null;
    if (relatedTarget && document.getElementById(RIGHT_PANEL_ID)?.contains(relatedTarget)) {
      setTimeout(() => editorRef.current?.focus(), 0);
      return;
    }
    commit();
  }, [commit]);

  // Reflect selection style back to panel when user selects text.
  // Also save the range so it survives the onPropsChange state update.
  const reflectSelection = useCallback(() => {
    if (!onPropsChange || !editorRef.current) return;
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return;
    if (!editorRef.current.contains(sel.anchorNode)) return;

    savedRange.current = sel.getRangeAt(0).cloneRange();

    const anchor = sel.anchorNode?.parentElement?.closest('[data-run]') as HTMLElement | null;
    if (!anchor) return;
    onPropsChange({
      fontFamily: anchor.dataset.fontFamily ?? textPropsRef.current.fontFamily,
      fontSize:   parseFloat(anchor.dataset.fontSize ?? String(textPropsRef.current.fontSize)),
      color:      anchor.dataset.color      ?? textPropsRef.current.color,
      isBold:     anchor.dataset.bold       === 'true',
      isItalic:   anchor.dataset.italic     === 'true',
    });
  }, [onPropsChange]);

  // Helper: make a styled span from current textProps + any pendingStyle overrides
  const makeStyledSpan = useCallback((): HTMLSpanElement => {
    const tp = textPropsRef.current;
    const ps = pendingStyle.current;
    const bold       = ps.bold       ?? tp.isBold;
    const italic     = ps.italic     ?? tp.isItalic;
    const fontFamily = ps.fontFamily ?? tp.fontFamily;
    const fontSize   = ps.fontSize   ?? tp.fontSize;
    const color      = ps.color      ?? tp.color;
    const cssFont    = FONT_TO_CSS[fontFamily] ?? 'Helvetica, Arial, sans-serif';

    const span = document.createElement('span');
    span.dataset.run        = '1';
    span.dataset.bold       = String(bold);
    span.dataset.italic     = String(italic);
    span.dataset.fontFamily = fontFamily;
    span.dataset.fontSize   = String(fontSize);
    span.dataset.color      = color;
    Object.assign(span.style, {
      fontFamily:  cssFont,
      fontWeight:  bold   ? 'bold'   : 'normal',
      fontStyle:   italic ? 'italic' : 'normal',
      fontSize:    `${fontSize * scale}px`,
      color,
      lineHeight:  '1.2',
      whiteSpace:  'pre-wrap',
    });
    pendingStyle.current = {}; // consumed
    return span;
  }, [scale]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    // Escape always cancels
    if (e.key === 'Escape') { e.preventDefault(); onCancel(); return; }

    // Enter = newline (browser default), Shift+Enter also newline — never commit on Enter
    // Commit only happens on blur (clicking outside) or Ctrl+Enter
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); commit(); return; }

    // Ctrl+B / Ctrl+I
    const tp = textPropsRef.current;
    if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
      e.preventDefault();
      const next = !tp.isBold;
      const sel = window.getSelection();
      const hasSelection = sel && !sel.isCollapsed && editorRef.current?.contains(sel.anchorNode);
      if (hasSelection && editorRef.current) {
        applyStyleToSelection(editorRef.current, { bold: next }, scale);
      } else {
        pendingStyle.current = { ...pendingStyle.current, bold: next };
      }
      onPropsChange?.({ ...tp, isBold: next });
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 'i') {
      e.preventDefault();
      const next = !tp.isItalic;
      const sel = window.getSelection();
      const hasSelection = sel && !sel.isCollapsed && editorRef.current?.contains(sel.anchorNode);
      if (hasSelection && editorRef.current) {
        applyStyleToSelection(editorRef.current, { italic: next }, scale);
      } else {
        pendingStyle.current = { ...pendingStyle.current, italic: next };
      }
      onPropsChange?.({ ...tp, isItalic: next });
      return;
    }

    // For any printable character, if there's a pending style we insert a
    // pre-styled span manually so the character appears with the right style.
    // We only do this when pendingStyle is non-empty AND the cursor is not
    // already inside a matching [data-run] span.
    if (Object.keys(pendingStyle.current).length > 0 && !e.ctrlKey && !e.metaKey && !e.altKey && e.key.length === 1) {
      e.preventDefault();
      const sel = window.getSelection();
      if (!sel || sel.rangeCount === 0) return;
      const range = sel.getRangeAt(0);
      // Delete any selected content first
      if (!sel.isCollapsed) range.deleteContents();

      const span = makeStyledSpan();
      const textNode = document.createTextNode(e.key);
      span.appendChild(textNode);
      range.insertNode(span);

      // Place cursor after the inserted character
      const newRange = document.createRange();
      newRange.setStartAfter(textNode);
      newRange.collapse(true);
      sel.removeAllRanges();
      sel.addRange(newRange);
    }
  };

  // Wrap any bare text nodes in the editor into styled spans immediately after
  // the browser inserts them. This prevents defaultStyle CSS from cascading into
  // unstyled text and causing the "first word changes color" bug.
  const handleInput = useCallback(() => {
    const editor = editorRef.current;
    if (!editor) return;
    const sel = window.getSelection();
    const cursorNode  = sel?.anchorNode ?? null;
    const cursorOffset = sel?.anchorOffset ?? 0;

    let wrapped: Node | null = null;

    // Walk all direct and nested children, find bare text nodes not in a [data-run]
    const walkAndWrap = (node: Node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        if (!(node.parentElement?.closest('[data-run]'))) {
          // This text node is bare — wrap it
          const tp = textPropsRef.current;
          const ps = pendingStyle.current;
          const bold       = ps.bold       !== undefined ? ps.bold       : tp.isBold;
          const italic     = ps.italic     !== undefined ? ps.italic     : tp.isItalic;
          const fontFamily = ps.fontFamily ?? tp.fontFamily;
          const fontSize   = ps.fontSize   ?? tp.fontSize;
          const color      = ps.color      ?? tp.color;
          const cssFont    = FONT_TO_CSS[fontFamily] ?? 'Helvetica, Arial, sans-serif';

          const span = document.createElement('span');
          span.dataset.run        = '1';
          span.dataset.bold       = String(bold);
          span.dataset.italic     = String(italic);
          span.dataset.fontFamily = fontFamily;
          span.dataset.fontSize   = String(fontSize);
          span.dataset.color      = color;
          Object.assign(span.style, {
            fontFamily: cssFont,
            fontWeight: bold   ? 'bold'   : 'normal',
            fontStyle:  italic ? 'italic' : 'normal',
            fontSize:   `${fontSize * scale}px`,
            color,
            lineHeight: '1.2',
            whiteSpace: 'pre-wrap',
          });

          node.parentNode!.insertBefore(span, node);
          span.appendChild(node);
          if (node === cursorNode) wrapped = span;
          pendingStyle.current = {};
        }
        return;
      }
      // Don't recurse into existing [data-run] spans
      if ((node as HTMLElement).dataset?.run) return;
      node.childNodes.forEach(walkAndWrap);
    };

    editor.childNodes.forEach(walkAndWrap);

    // Restore cursor if we wrapped the node it was in
    if (wrapped && sel) {
      const range = document.createRange();
      const textChild = (wrapped as HTMLElement).firstChild;
      if (textChild) {
        range.setStart(textChild, Math.min(cursorOffset, (textChild as Text).length));
        range.collapse(true);
        sel.removeAllRanges();
        sel.addRange(range);
      }
    }
  }, [scale]);

  const defaultStyle: React.CSSProperties = {
    // Only layout properties — NO color, font, size here.
    // All text must be inside [data-run] spans which carry their own styles.
    // If we put color/fontWeight etc. here they cascade into bare text nodes
    // and make the whole box change style when textProps changes.
    lineHeight:   1.2,
    wordBreak:    'break-word',
    overflowWrap: 'break-word',
    whiteSpace:   'pre-wrap',
    overflow:     'hidden',
    padding:      0,
    margin:       0,
  };

  return (
    <div
      ref={editorRef}
      contentEditable
      suppressContentEditableWarning
      onKeyDown={onKeyDown}
      onBlur={handleBlur}
      onInput={handleInput}
      onMouseUp={reflectSelection}
      onKeyUp={reflectSelection}
      onPointerDown={e => e.stopPropagation()}
      style={{
        ...defaultStyle,
        position:   'absolute', inset: 0,
        outline:    '1.5px solid #4a90e2',
        background: 'transparent',
        cursor:     'text',
        boxSizing:  'border-box',
        userSelect: 'text',
      }}
    />
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// TransientTextBox
// ══════════════════════════════════════════════════════════════════════════════

interface TransientBoxProps {
  initialX: number; initialY: number;
  scale:      number;
  textProps:  TextProps;
  onPropsChange?: (p: TextProps) => void;
  onCommit: (runs: TextRun[], plain: string, x: number, y: number, w: number, h: number) => void;
  onCancel: () => void;
}

function TransientTextBox({ initialX, initialY, scale, textProps, onPropsChange, onCommit, onCancel }: TransientBoxProps) {
  const INIT_W = 160;
  const INIT_H = Math.ceil(textProps.fontSize * 1.2) + 2;
  const [geo, setGeo] = useState<GeoRect>({ x: initialX, y: initialY, w: INIT_W, h: INIT_H });

  const startMove = useCallback((e: React.PointerEvent) => {
    // Only move if the target is the wrapper div (not the editor inside)
    if ((e.target as HTMLElement).isContentEditable) return;
    e.preventDefault(); e.stopPropagation();
    const sx = e.clientX, sy = e.clientY, ox = geo.x, oy = geo.y;
    const onMove = (ev: PointerEvent) => setGeo(g => ({ ...g, x: ox + (ev.clientX - sx) / scale, y: oy + (ev.clientY - sy) / scale }));
    const onUp   = () => { window.removeEventListener('pointermove', onMove); window.removeEventListener('pointerup', onUp); };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  }, [geo.x, geo.y, scale]);

  const handleResize = useResizeDrag(scale, setGeo);

  return (
    <div
      style={{
        position: 'absolute',
        left: geo.x * scale, top: geo.y * scale,
        width: geo.w * scale, height: geo.h * scale,
        zIndex: 60, boxSizing: 'border-box',
        border: '1.5px solid #4a90e2',
        cursor: 'move',
      }}
      onPointerDown={startMove}
    >
      <RichTextEditor
        initialHtml=""
        scale={scale}
        textProps={textProps}
        isTransient
        onPropsChange={onPropsChange}
        onCommit={(runs, plain) => onCommit(runs, plain, geo.x, geo.y, geo.w, geo.h)}
        onCancel={onCancel}
      />
      <ResizeHandles geo={geo} scale={scale} onResize={handleResize} />
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// NodeOverlay — committed annotations
// ══════════════════════════════════════════════════════════════════════════════

function NodeOverlay({ node, scale, activeTool, textProps, onPropsChange, onUpdate }: {
  node:          AnnotationNode;
  scale:         number;
  activeTool?:   ToolId;
  textProps:     TextProps;
  onPropsChange?:(p: TextProps) => void;
  onUpdate?:     (id: string, updates: Partial<AnnotationNode & { runs: TextRun[] }>) => void;
}) {
  const isTextTool = activeTool === 'select' || activeTool === 'addtext' || activeTool === 'edittext';
  const isEditable = node.node_type === 'text' && isTextTool;

  const [geo, setGeo]        = useState<GeoRect>({ x: node.bbox?.x ?? 0, y: node.bbox?.y ?? 0, w: node.bbox?.width ?? 100, h: node.bbox?.height ?? 30 });
  const [isEditing, setEdit] = useState(false);
  const [editKey, setEditKey]= useState(0); // bump to force RichTextEditor remount
  const dragging             = useRef(false);

  useEffect(() => {
    if (!dragging.current && node.bbox)
      setGeo({ x: node.bbox.x, y: node.bbox.y, w: node.bbox.width, h: node.bbox.height });
  }, [node.bbox]);

  // When user clicks this node with select/edittext, populate the panel
  useEffect(() => {
    if (isEditable && !isEditing && onPropsChange && node.runs && node.runs.length > 0) {
      const first = node.runs[0];
      onPropsChange({
        fontFamily: first.fontFamily ?? node.font_family ?? 'Helvetica',
        fontSize:   first.fontSize   ?? node.font_size   ?? 12,
        color:      first.color      ?? node.color       ?? '#000000',
        isBold:     first.bold       ?? node.bold        ?? false,
        isItalic:   first.italic     ?? node.italic      ?? false,
      });
    }
  // Only run when edit state or editability changes, not on every textProps update
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEditable]);

  const startMove = useCallback((e: React.PointerEvent) => {
    if (!isEditable || isEditing) return;
    e.preventDefault(); e.stopPropagation();
    dragging.current = true;
    const sx = e.clientX, sy = e.clientY, ox = geo.x, oy = geo.y;
    const onMove = (ev: PointerEvent) => setGeo(g => ({ ...g, x: ox + (ev.clientX - sx) / scale, y: oy + (ev.clientY - sy) / scale }));
    const onUp   = (ev: PointerEvent) => {
      dragging.current = false;
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      const nx = ox + (ev.clientX - sx) / scale, ny = oy + (ev.clientY - sy) / scale;
      setGeo(g => ({ ...g, x: nx, y: ny }));
      if (onUpdate && node.bbox) onUpdate(node.id, { ...node, bbox: { ...node.bbox, x: nx, y: ny } });
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  }, [isEditable, isEditing, geo, scale, onUpdate, node]);

  const handleResize = useResizeDrag(scale, (g) => {
    setGeo(g);
    if (onUpdate && node.bbox) onUpdate(node.id, { ...node, bbox: { x: g.x, y: g.y, width: g.w, height: g.h } });
  });

  const commitEdit = useCallback((runs: TextRun[], plain: string) => {
    setEdit(false);
    if (onUpdate) onUpdate(node.id, { ...node, runs, text_content: plain });
  }, [node, onUpdate]);

  // Highlight / redact
  if (node.node_type === 'highlight') {
    if (!node.bbox) return null;
    const s: React.CSSProperties = {
      position: 'absolute', zIndex: 20, pointerEvents: 'none', borderRadius: 1,
      left: node.bbox.x * scale, top: node.bbox.y * scale,
      width: node.bbox.width * scale, height: node.bbox.height * scale,
    };
    return node.color === '#000000'
      ? <div style={{ ...s, background: '#000' }} />
      : <div style={{ ...s, background: node.color ?? '#f59e0b', opacity: node.opacity ?? 0.42, mixBlendMode: 'multiply' }} />;
  }
  if (node.node_type !== 'text' || !node.bbox) return null;

  const pw = Math.max(geo.w * scale, 10), ph = Math.max(geo.h * scale, 10);

  // Build initial HTML from stored runs (or flat style)
  const storedRuns: TextRun[] = node.runs && node.runs.length > 0
    ? node.runs
    : node.text_content
      ? [{ text: node.text_content, bold: node.bold ?? false, italic: node.italic ?? false,
           fontFamily: node.font_family ?? 'Helvetica', fontSize: node.font_size ?? 12, color: node.color ?? '#000000' }]
      : [];

  // Display div — render runs as spans
  const displayContent = storedRuns.length > 0 ? (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', lineHeight: 1.2, wordBreak: 'break-word', whiteSpace: 'pre-wrap' }}>
      {storedRuns.map((run, i) => (
        <span key={i} style={runToSpanStyle(run, scale)}>{run.text}</span>
      ))}
    </div>
  ) : null;

  return (
    <div
      style={{
        position: 'absolute', zIndex: 20,
        left: geo.x * scale, top: geo.y * scale,
        width: pw, height: ph, boxSizing: 'border-box',
        outline: isEditable && !isEditing ? '1.5px dashed rgba(74,144,226,0.45)' : 'none',
        outlineOffset: '1px',
        cursor: isEditable ? (isEditing ? 'text' : 'grab') : 'default',
      }}
      onPointerDown={isEditable ? startMove : undefined}
      onDoubleClick={isEditable ? () => { setEdit(true); setEditKey(k => k + 1); } : undefined}
    >
      {isEditing ? (
        <RichTextEditor
          key={editKey}
          initialHtml={runsToHtml(storedRuns, textProps, scale)}
          scale={scale}
          textProps={textProps}
          isTransient={false}
          onPropsChange={onPropsChange}
          onCommit={commitEdit}
          onCancel={() => setEdit(false)}
        />
      ) : displayContent}

      {isEditable && !isEditing && (
        <ResizeHandles geo={geo} scale={scale} onResize={handleResize} />
      )}
    </div>
  );
}

// ── CopyToast ──────────────────────────────────────────────────────────────────
const CopyToast = ({ visible }: { visible: boolean }) => (
  <div className={`fixed bottom-10 left-1/2 -translate-x-1/2 bg-[#2d3338] text-white border border-white/[0.07] px-4 py-2 rounded-lg text-sm font-medium shadow-xl flex items-center gap-2 pointer-events-none z-50 transition-all duration-200 ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}>
    <span className="text-green-400">✓</span> Copied to clipboard
  </div>
);

// ══════════════════════════════════════════════════════════════════════════════
// PageRenderer
// ══════════════════════════════════════════════════════════════════════════════
function PageRenderer({
  pageNode, pdfDoc, pageIndex, totalPages, scale, activeTool, textProps, onTextPropsChange,
  onAnnotationAdded, onDocumentChanged, onTextSelected, containerRef,
}: {
  pageNode: PageNode; pdfDoc: pdfjsLib.PDFDocumentProxy;
  pageIndex: number; totalPages: number; scale: number; activeTool: ToolId;
  textProps: TextProps; onTextPropsChange?: (p: TextProps) => void;
  onAnnotationAdded?: () => Promise<void>; onDocumentChanged?: () => Promise<void>;
  onTextSelected?: (text: string) => void; containerRef?: React.Ref<HTMLDivElement>;
}) {
  const overlayRef  = useRef<HTMLDivElement>(null);
  const clearSelRef = useRef<(() => void) | null>(null);
  const toastTimer  = useRef<ReturnType<typeof setTimeout>>();
  const busyRef     = useRef(false);

  const [annotations,    setAnnotations]   = useState<AnnotationNode[]>(pageNode.children ?? []);
  const [hovered,        setHovered]       = useState(false);
  const [busy,           setBusy]          = useState(false);
  const [localRotation,  setLocalRotation] = useState(pageNode.rotation ?? 0);
  const [showToast,      setShowToast]     = useState(false);
  const [showCtrl,       setShowCtrl]      = useState(false);
  const [transientPos,   setTransientPos]  = useState<{ x: number; y: number } | null>(null);

  useEffect(() => { setAnnotations(pageNode.children ?? []); }, [pageNode.children]);
  useEffect(() => { if (typeof pageNode.rotation === 'number') setLocalRotation(pageNode.rotation); }, [pageNode.rotation, pageNode.id]);

  const { canvasRef, fullDimensions } = usePdfCanvas({ pdfDoc, pageNode, pageIndex, scale, localRotation });
  const { pageChars } = usePageChars({ pageNodeId: pageNode.id, localRotation, metadata: pageNode.metadata });

  const withBusy = useCallback(async (fn: () => Promise<void>) => {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true);
    try { await fn(); } finally { busyRef.current = false; setBusy(false); }
  }, []);

  const toast = useCallback(() => {
    setShowToast(true); clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setShowToast(false), 2000);
  }, []);

  const handleNodeUpdate = useCallback(async (nodeId: string, updatedNode: Partial<AnnotationNode & { runs: TextRun[] }>) => {
    setAnnotations(prev => prev.map(n => n.id === nodeId ? { ...n, ...updatedNode } as AnnotationNode : n));
    try {
      await engineApi.updateAnnotation(nodeId, {
        page_id:      pageNode.id,
        x:            updatedNode.bbox?.x,
        y:            updatedNode.bbox?.y,
        width:        updatedNode.bbox?.width,
        height:       updatedNode.bbox?.height,
        text_content: updatedNode.text_content,
        runs:         updatedNode.runs,
      });
    } catch (err) { console.error('Failed to update node:', err); }
  }, [pageNode.id]);

  const handleAction = useCallback(async (rects: { x: number; y: number; width: number; height: number }[]) => {
    if (activeTool === 'crop') return;
    if (activeTool === 'select') {
      const tol = 4;
      const sel = pageChars
        .filter(c => { const cx = c.x + c.width / 2, cy = c.y + c.height / 2; return rects.some(r => cx >= r.x - tol && cx <= r.x + r.width + tol && cy >= r.y - tol && cy <= r.y + r.height + tol); })
        .sort((a, b) => Math.abs(a.y - b.y) > 5 ? a.y - b.y : a.x - b.x);
      if (!sel.length) return;
      let text = sel[0].text;
      for (let i = 1; i < sel.length; i++) {
        const p = sel[i - 1], c = sel[i];
        const avgH = (p.height + c.height) / 2;
        text += Math.abs((p.y + p.height / 2) - (c.y + c.height / 2)) > avgH * 0.75 ? '\n' + c.text : (c.x - (p.x + p.width) > p.width * 0.4 ? ' ' : '') + c.text;
      }
      try { await navigator.clipboard.writeText(text); toast(); onTextSelected?.(text); }
      catch { window.prompt('Copy (Ctrl+C):', text); onTextSelected?.(text); }
      return;
    }
    try {
      if (activeTool === 'highlight') {
        const res = await fetch('http://localhost:8000/api/annotations/highlight', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ page_id: pageNode.id, rects }),
        }).then(r => r.json());
        if (res?.node) { setAnnotations(p => [...p, res.node]); onAnnotationAdded?.(); }
      } else if (activeTool === 'redact') {
        const res = await engineApi.applyRedaction(pageNode.id, rects);
        const nodes = res?.node ? [res.node] : (res?.nodes ?? []);
        if (nodes.length) { setAnnotations(p => [...p, ...nodes]); onAnnotationAdded?.(); }
      }
      clearSelRef.current?.();
    } catch (e) { console.error(e); }
  }, [activeTool, pageNode.id, pageChars, toast, onAnnotationAdded]);

  const isDragTool = ['highlight', 'redact', 'select', 'crop', 'underline'].includes(activeTool);
  const { liveRects, committedRects, clearSelection, handlers } = useDragSelection({ overlayRef, pageChars, scale, activeTool, metadata: pageNode.metadata, onAction: handleAction });
  useEffect(() => { clearSelRef.current = clearSelection; }, [clearSelection]);

  const displayRects = liveRects.length > 0 ? liveRects : committedRects;
  const cropRect = activeTool === 'crop' && committedRects[0];

  const cropBox   = pageNode.crop_box;
  const isCropped = cropBox && typeof cropBox.width === 'number';
  const outerW = isCropped ? cropBox!.width  * scale : fullDimensions.width;
  const outerH = isCropped ? cropBox!.height * scale : fullDimensions.height;
  const innerX = isCropped ? -(cropBox!.x    * scale) : 0;
  const innerY = isCropped ? -(cropBox!.y    * scale) : 0;

  const handleTextCommit = useCallback(async (runs: TextRun[], plain: string, x: number, y: number, w: number, h: number) => {
    setTransientPos(null);
    try {
      const res = await engineApi.addTextAnnotation(
        pageNode.id, plain, x, y, w, h,
        textProps.fontFamily, textProps.fontSize, textProps.color,
        textProps.isBold, textProps.isItalic, runs,
      );
      if (res?.node) { setAnnotations(p => [...p, res.node]); onAnnotationAdded?.(); }
    } catch (err) { console.error(err); }
  }, [pageNode.id, textProps, onAnnotationAdded]);

  return (
    <div
      ref={containerRef as React.Ref<HTMLDivElement>}
      style={{ width: outerW, height: outerH, opacity: busy ? 0.75 : 1 }}
      className={`relative bg-white flex-shrink-0 mx-auto mb-6 transition-shadow rounded-sm ${hovered ? 'shadow-2xl' : 'shadow-xl'} ${isCropped ? 'overflow-hidden' : ''}`}
      onMouseEnter={() => { setHovered(true);  setShowCtrl(true);  }}
      onMouseLeave={() => { setHovered(false); setShowCtrl(false); }}
    >
      {showCtrl && !cropRect && (
        <div className="absolute -top-9 left-1/2 -translate-x-1/2 z-30 flex items-center gap-1 bg-[#2d3338] border border-white/[0.07] rounded-lg px-2 py-1.5 shadow-xl animate-ctrl-in">
          {[
            { icon: '↑', title: 'Move up',    disabled: pageIndex === 0,             onClick: () => withBusy(async () => { await engineApi.movePage(pageNode.id, pageIndex - 1);  await onDocumentChanged?.(); }) },
            { icon: '↓', title: 'Move down',  disabled: pageIndex >= totalPages - 1, onClick: () => withBusy(async () => { await engineApi.movePage(pageNode.id, pageIndex + 1);  await onDocumentChanged?.(); }) },
            null,
            { icon: '↻', title: 'Rotate CW',  onClick: () => withBusy(async () => { const r = await engineApi.rotatePage(pageNode.id,  90); setLocalRotation(r?.page?.rotation ?? (v => (v + 90) % 360));        await onDocumentChanged?.(); }) },
            { icon: '↺', title: 'Rotate CCW', onClick: () => withBusy(async () => { const r = await engineApi.rotatePage(pageNode.id, -90); setLocalRotation(r?.page?.rotation ?? (v => (v - 90 + 360) % 360)); await onDocumentChanged?.(); }) },
            null,
            { icon: '✕', title: 'Delete page', danger: true, disabled: totalPages <= 1, onClick: () => { if (!window.confirm(`Delete page ${pageIndex + 1}?`)) return; withBusy(async () => { await engineApi.deletePage(pageNode.id); await onDocumentChanged?.(); }); } },
          ].map((btn, i) =>
            btn === null
              ? <div key={i} className="w-px h-4 bg-white/10 mx-0.5" />
              : <button key={i} title={btn.title} disabled={btn.disabled} onClick={btn.onClick}
                  className={`w-7 h-7 rounded flex items-center justify-center text-sm transition-colors ${(btn as any).danger ? 'text-red-400 hover:bg-red-500/20 disabled:opacity-30' : 'text-gray-400 hover:bg-[#3d4449] hover:text-white disabled:opacity-30'} disabled:cursor-not-allowed`}
                >{btn.icon}</button>
          )}
        </div>
      )}

      <div style={{ position: 'absolute', top: innerY, left: innerX, width: fullDimensions.width, height: fullDimensions.height }}>
        <canvas ref={canvasRef} className="absolute inset-0 pointer-events-none" style={{ width: fullDimensions.width, height: fullDimensions.height }} />

        {cropRect && (
          <div className="absolute inset-0 pointer-events-none z-[8]">
            {[
              { top: 0, left: 0, right: 0, height: cropRect.y * scale },
              { bottom: 0, left: 0, right: 0, top: (cropRect.y + cropRect.height) * scale },
              { top: cropRect.y * scale, left: 0, width: cropRect.x * scale, height: cropRect.height * scale },
              { top: cropRect.y * scale, left: (cropRect.x + cropRect.width) * scale, right: 0, height: cropRect.height * scale },
            ].map((s, i) => <div key={i} className="absolute bg-black/50" style={s} />)}
          </div>
        )}

        <div
          ref={overlayRef}
          className="absolute inset-0 z-10"
          style={{ cursor: CURSORS[activeTool] ?? 'default', userSelect: 'none' }}
          onClick={activeTool === 'addtext' ? (e) => {
            if (transientPos || !overlayRef.current) return;
            const r = overlayRef.current.getBoundingClientRect();
            setTransientPos({ x: (e.clientX - r.left) / scale, y: (e.clientY - r.top) / scale });
          } : handlers.onClick}
          onMouseDown={isDragTool ? handlers.onMouseDown : undefined}
          onMouseMove={isDragTool ? handlers.onMouseMove : undefined}
          onMouseUp={isDragTool ? handlers.onMouseUp : undefined}
          onMouseLeave={isDragTool ? handlers.onMouseLeave : undefined}
        >
          {displayRects.map((rect, i) => (
            <div key={i} className="absolute pointer-events-none" style={{
              left: rect.x * scale, top: rect.y * scale,
              width: rect.width * scale, height: rect.height * scale,
              background: SEL_COLOR[activeTool] ?? 'rgba(74,144,226,0.2)',
              border: activeTool === 'crop' ? '2px dashed #f97316' : 'none', borderRadius: 1,
            }} />
          ))}
        </div>

        {annotations.map(node => (
          <NodeOverlay
            key={node.id} node={node} scale={scale}
            activeTool={activeTool} textProps={textProps}
            onPropsChange={onTextPropsChange}
            onUpdate={handleNodeUpdate}
          />
        ))}

        {transientPos && (
          <TransientTextBox
            initialX={transientPos.x} initialY={transientPos.y}
            scale={scale} textProps={textProps}
            onPropsChange={onTextPropsChange}
            onCommit={handleTextCommit}
            onCancel={() => setTransientPos(null)}
          />
        )}
      </div>

      {cropRect && (
        <div className="absolute z-30 flex gap-2" style={{ bottom: fullDimensions.height - (cropRect.y + cropRect.height) * scale + 10, left: '50%', transform: 'translateX(-50%)' }}>
          <button onClick={() => withBusy(async () => { await engineApi.cropPage(pageNode.id, cropRect.x, cropRect.y, cropRect.width, cropRect.height); clearSelection(); await onDocumentChanged?.(); })}
            className="h-7 px-4 bg-green-500 text-[#0a1f17] text-xs font-semibold rounded-md hover:bg-green-400 transition-colors">✓ Apply</button>
          <button onClick={clearSelection}
            className="h-7 px-3 bg-[#2d3338] text-gray-300 text-xs border border-white/10 rounded-md hover:bg-[#3d4449] transition-colors">Cancel</button>
        </div>
      )}

      <div className="absolute bottom-2 right-2.5 bg-[#1e2327]/70 backdrop-blur-sm text-white text-[10px] font-semibold font-mono px-1.5 py-0.5 rounded-full pointer-events-none z-20">
        {pageIndex + 1}
      </div>

      {busy && (
        <div className="absolute inset-0 bg-black/10 flex items-center justify-center z-50">
          <div className="bg-[#2d3338] text-white text-xs font-semibold px-4 py-2 rounded-lg border border-white/10 shadow-xl">Working…</div>
        </div>
      )}
      <CopyToast visible={showToast} />
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// Canvas
// ══════════════════════════════════════════════════════════════════════════════
export function Canvas({
  pdfDoc, documentState, activeTool = 'select', scale = 1.5,
  textProps = DEFAULT_TEXT_PROPS, onTextPropsChange,
  onAnnotationAdded, onDocumentChanged, onTextSelected, pageRefs,
}: CanvasProps) {
  return (
    <div className="flex-1 bg-[#353a40] overflow-auto flex flex-col items-center pt-8 pb-8 px-4">
      {!documentState ? (
        <div className="flex flex-col items-center justify-center h-full gap-5 select-none">
          <div className="w-16 h-16 bg-[#2d3338] rounded-xl flex items-center justify-center text-3xl border border-white/[0.05] shadow-2xl">📄</div>
          <div className="text-center">
            <div className="text-base font-semibold text-white mb-1">Open a document to begin</div>
            <div className="text-sm text-gray-400">File → Open, or press Ctrl+O</div>
          </div>
          <div className="flex flex-wrap gap-1.5 justify-center max-w-xs">
            {['Highlight · Redact', 'Add Text · Images', 'Reorder · Rotate', 'Read Aloud · Export'].map(f => (
              <span key={f} className="text-[11px] text-gray-500 bg-[#2d3338] border border-white/[0.05] rounded-full px-3 py-1">{f}</span>
            ))}
          </div>
        </div>
      ) : (
        documentState.children?.map((page, i) => (
          <div key={page.id} ref={el => { if (pageRefs) pageRefs.current[i] = el; }}>
            <PageRenderer
              pageNode={page} pdfDoc={pdfDoc!} pageIndex={i}
              totalPages={documentState.children?.length ?? 1}
              scale={scale} activeTool={activeTool}
              textProps={textProps} onTextPropsChange={onTextPropsChange}
              onAnnotationAdded={onAnnotationAdded} onDocumentChanged={onDocumentChanged}
              onTextSelected={onTextSelected}
            />
          </div>
        ))
      )}
    </div>
  );
}