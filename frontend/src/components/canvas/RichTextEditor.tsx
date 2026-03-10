import React, { useRef, useEffect, useCallback } from 'react';
import { FONT_TO_CSS, type TextProps, type TextRun } from '../../types/textProps';
import { domToRuns, runsToPlainText, applyStyleToSelection } from '../../utils/textUtils';

export interface RichTextEditorProps {
  initialHtml:   string;
  scale:         number;
  textProps:     TextProps;
  isTransient:   boolean;
  onCommit:      (runs: TextRun[], plainText: string) => void;
  onCancel:      () => void;
  onPropsChange?:(p: TextProps) => void;
  blurRef?:      React.MutableRefObject<(() => void) | null>;
}

const RIGHT_PANEL_ID = 'text-props-panel';

export function RichTextEditor({
  initialHtml, scale, textProps, isTransient, onCommit, onCancel, onPropsChange, blurRef,
}: RichTextEditorProps) {
  const editorRef     = useRef<HTMLDivElement>(null);
  const textPropsRef  = useRef(textProps);
  useEffect(() => { textPropsRef.current = textProps; }, [textProps]);

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
  }, []);

  const pendingStyle = useRef<Partial<{ bold: boolean; italic: boolean; fontFamily: string; fontSize: number; color: string }>>({});
  const savedRange = useRef<Range | null>(null);
  const prevProps = useRef(textProps);

  useEffect(() => {
    const p = textProps, pp = prevProps.current;
    const changes: typeof pendingStyle.current = {};
    if (p.isBold !== pp.isBold && p.isBold !== 'mixed') changes.bold = p.isBold as boolean;
    if (p.isItalic !== pp.isItalic && p.isItalic !== 'mixed') changes.italic = p.isItalic as boolean;
    if (p.fontFamily !== pp.fontFamily && p.fontFamily !== '') changes.fontFamily = p.fontFamily;
    if (p.fontSize !== pp.fontSize && p.fontSize !== '') changes.fontSize = p.fontSize as number;
    if (p.color !== pp.color && p.color !== '') changes.color = p.color;
    prevProps.current = p;

    if (!Object.keys(changes).length || !editorRef.current) return;

    const sel = window.getSelection();
    const rangeToUse = savedRange.current;
    const liveNonCollapsed = sel && !sel.isCollapsed && sel.rangeCount > 0 &&
      editorRef.current.contains(sel.anchorNode);
    const hasSelection = rangeToUse || liveNonCollapsed;

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

  useEffect(() => {
    if (blurRef) blurRef.current = () => editorRef.current?.blur();
    return () => { if (blurRef) blurRef.current = null; };
  }, []);

  const handleBlur = useCallback((e: React.FocusEvent) => {
    const relatedTarget = e.relatedTarget as HTMLElement | null;
    if (relatedTarget && document.getElementById(RIGHT_PANEL_ID)?.contains(relatedTarget)) {
      setTimeout(() => editorRef.current?.focus(), 0);
      return;
    }
    commit();
  }, [commit]);

  const reflectSelection = useCallback(() => {
    if (!onPropsChange || !editorRef.current) return;
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return;
    if (!editorRef.current.contains(sel.anchorNode)) return;

    const range = sel.getRangeAt(0);
    savedRange.current = range.cloneRange();

    let spans: HTMLElement[] = [];
    if (sel.isCollapsed) {
      const anchor = sel.anchorNode?.parentElement?.closest('[data-run]') as HTMLElement | null;
      if (anchor) spans.push(anchor);
    } else {
      const fragment = range.cloneContents();
      spans = Array.from(fragment.querySelectorAll('[data-run]')) as HTMLElement[];
      const startAnchor = range.startContainer.parentElement?.closest('[data-run]') as HTMLElement | null;
      if (startAnchor && !spans.find(s => s.outerHTML === startAnchor.outerHTML)) {
        spans.unshift(startAnchor);
      }
    }

    if (spans.length === 0) return;

    let isBold: boolean | 'mixed' = spans[0].dataset.bold === 'true';
    let isItalic: boolean | 'mixed' = spans[0].dataset.italic === 'true';
    let fontFamily = spans[0].dataset.fontFamily ?? textPropsRef.current.fontFamily;
    let fontSize: number | '' = parseFloat(spans[0].dataset.fontSize ?? String(textPropsRef.current.fontSize));
    let color = spans[0].dataset.color ?? textPropsRef.current.color;

    for (let i = 1; i < spans.length; i++) {
      const s = spans[i];
      if ((s.dataset.bold === 'true') !== isBold) isBold = 'mixed';
      if ((s.dataset.italic === 'true') !== isItalic) isItalic = 'mixed';
      if ((s.dataset.fontFamily ?? textPropsRef.current.fontFamily) !== fontFamily) fontFamily = '';
      if (parseFloat(s.dataset.fontSize ?? String(textPropsRef.current.fontSize)) !== fontSize) fontSize = '';
      if ((s.dataset.color ?? textPropsRef.current.color) !== color) color = '';
    }

    onPropsChange({
      fontFamily, fontSize, color, isBold, isItalic
    });
  }, [onPropsChange]);

  const makeStyledSpan = useCallback((): HTMLSpanElement => {
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
      fontFamily:  cssFont,
      fontWeight:  bold   ? 'bold'   : 'normal',
      fontStyle:   italic ? 'italic' : 'normal',
      fontSize:    `${fontSize * scale}px`,
      color,
      lineHeight:  '1.2',
      whiteSpace:  'pre-wrap',
    });
    pendingStyle.current = {}; 
    return span;
  }, [scale]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { e.preventDefault(); onCancel(); return; }
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); commit(); return; }

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

    if (Object.keys(pendingStyle.current).length > 0 && !e.ctrlKey && !e.metaKey && !e.altKey && e.key.length === 1) {
      e.preventDefault();
      const sel = window.getSelection();
      if (!sel || sel.rangeCount === 0) return;
      const range = sel.getRangeAt(0);
      if (!sel.isCollapsed) range.deleteContents();

      const span = makeStyledSpan();
      const textNode = document.createTextNode(e.key);
      span.appendChild(textNode);
      range.insertNode(span);

      const newRange = document.createRange();
      newRange.setStartAfter(textNode);
      newRange.collapse(true);
      sel.removeAllRanges();
      sel.addRange(newRange);
    }
  };

  const handleInput = useCallback(() => {
    const editor = editorRef.current;
    if (!editor) return;
    const sel = window.getSelection();
    const cursorNode   = sel?.anchorNode ?? null;
    const cursorOffset = sel?.anchorOffset ?? 0;

    let wrapped: Node | null = null;

    const walkAndWrap = (node: Node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        const parentRun = (node.parentElement as HTMLElement | null)?.closest('[data-run]');
        if (parentRun && editor.contains(parentRun)) return;

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
        return;
      }

      if ((node as HTMLElement).dataset?.run) return;
      node.childNodes.forEach(walkAndWrap);
    };

    editor.childNodes.forEach(walkAndWrap);

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