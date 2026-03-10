import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Trash2 } from 'lucide-react';
import { runToSpanStyle, runsToHtml } from '../../utils/textUtils';
import { ResizeHandles, useResizeDrag, type GeoRect } from './ResizeHandles';
import { RichTextEditor } from './RichTextEditor';
import type { TextProps, TextRun } from '../../types/textProps';
import type { ToolId } from '../toolbar/Toolbar';
import type { AnnotationNode } from './types';

interface NodeOverlayProps {
  node:            AnnotationNode;
  scale:           number;
  activeTool?:     ToolId;
  textProps:       TextProps;
  onPropsChange?:  (p: TextProps) => void;
  onUpdate?:       (id: string, updates: Partial<AnnotationNode & { runs: TextRun[] }>) => void;
  onDelete?:       (id: string) => void;
  onRegisterBlur?: (fn: (() => void) | null) => void;
}

// ── Context menu ──────────────────────────────────────────────────────────────

function ContextMenu({ x, y, onDelete, onClose }: {
  x: number; y: number;
  onDelete: () => void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [onClose]);

  return (
    <div
      ref={ref}
      style={{
        position: 'fixed', left: x, top: y, zIndex: 9999,
        backgroundColor: '#1e2428',
        border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 6,
        boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
        padding: 4,
        minWidth: 150,
      }}
      onContextMenu={e => e.preventDefault()}
    >
      <button
        onClick={() => { onDelete(); onClose(); }}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          width: '100%', padding: '6px 10px', border: 'none',
          borderRadius: 4, cursor: 'pointer', textAlign: 'left',
          backgroundColor: 'transparent', color: '#f87171',
          fontSize: '12px', fontFamily: 'inherit',
        }}
        onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'rgba(248,113,113,0.12)')}
        onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
      >
        <Trash2 size={13} />
        Delete annotation
      </button>
    </div>
  );
}

// ── NodeOverlay ───────────────────────────────────────────────────────────────

export function NodeOverlay({ node, scale, activeTool, textProps, onPropsChange, onUpdate, onDelete, onRegisterBlur }: NodeOverlayProps) {
  const isTextTool = activeTool === 'select' || activeTool === 'addtext' || activeTool === 'edittext';
  const isEditable = node.node_type === 'text' && isTextTool;

  const [geo, setGeo]        = useState<GeoRect>({ x: node.bbox?.x ?? 0, y: node.bbox?.y ?? 0, w: node.bbox?.width ?? 100, h: node.bbox?.height ?? 30 });
  const [isEditing, setEdit] = useState(false);
  const [editKey, setEditKey]= useState(0);
  const [focused,  setFocused] = useState(false);
  const [ctxMenu,  setCtxMenu] = useState<{ x: number; y: number } | null>(null);
  const dragging             = useRef(false);
  const nodeBlurRef          = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (!dragging.current && node.bbox)
      setGeo({ x: node.bbox.x, y: node.bbox.y, w: node.bbox.width, h: node.bbox.height });
  }, [node.bbox]);

  useEffect(() => {
    if (isEditable && !isEditing && onPropsChange && node.runs && node.runs.length > 0) {
      const first = node.runs[0] as any;
      onPropsChange({
        fontFamily: first.fontFamily ?? first.font_family ?? node.font_family ?? 'Helvetica',
        fontSize:   first.fontSize   ?? first.font_size   ?? node.font_size   ?? 12,
        color:      first.color      ?? node.color       ?? '#000000',
        isBold:     first.bold       ?? node.bold        ?? false,
        isItalic:   first.italic     ?? node.italic      ?? false,
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEditable]);

  useEffect(() => {
    if (isEditing) {
      onRegisterBlur?.(() => nodeBlurRef.current?.());
    } else {
      onRegisterBlur?.(null);
    }
    return () => { onRegisterBlur?.(null); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEditing]);

  useEffect(() => {
    if (isEditing && !isEditable) {
      nodeBlurRef.current?.();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTool]);

  // Delete/Backspace when focused but not actively editing text
  useEffect(() => {
    if (!focused || isEditing) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Delete' || e.key === 'Backspace') {
        e.preventDefault();
        onDelete?.(node.id);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [focused, isEditing, node.id, onDelete]);

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setCtxMenu({ x: e.clientX, y: e.clientY });
  }, []);

  const startMove = useCallback((e: React.PointerEvent) => {
    if (!isEditable || isEditing) return;
    e.preventDefault(); e.stopPropagation();
    setFocused(true);
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

  if (node.node_type === 'highlight') {
    if (!node.bbox) return null;
    const s: React.CSSProperties = {
      position: 'absolute', zIndex: 20, borderRadius: 1,
      left: node.bbox.x * scale, top: node.bbox.y * scale,
      width: node.bbox.width * scale, height: node.bbox.height * scale,
      cursor: 'context-menu',
    };
    const fill = node.color === '#000000'
      ? <div style={{ ...s, background: '#000', pointerEvents: 'auto' }} onContextMenu={handleContextMenu} />
      : <div style={{ ...s, background: node.color ?? '#f59e0b', opacity: node.opacity ?? 0.42, mixBlendMode: 'multiply', pointerEvents: 'auto' }} onContextMenu={handleContextMenu} />;

    return (
      <>
        {fill}
        {ctxMenu && (
          <ContextMenu
            x={ctxMenu.x} y={ctxMenu.y}
            onDelete={() => onDelete?.(node.id)}
            onClose={() => setCtxMenu(null)}
          />
        )}
      </>
    );
  }
  if (node.node_type !== 'text' || !node.bbox) return null;

  const pw = Math.max(geo.w * scale, 10), ph = Math.max(geo.h * scale, 10);

  const storedRuns: TextRun[] = node.runs && node.runs.length > 0
    ? node.runs.map((r: any) => ({
        text: r.text,
        bold: r.bold ?? false,
        italic: r.italic ?? false,
        fontFamily: r.fontFamily ?? r.font_family ?? 'Helvetica',
        fontSize: r.fontSize ?? r.font_size ?? 12,
        color: r.color ?? '#000000'
      }))
    : node.text_content
      ? [{ text: node.text_content, bold: node.bold ?? false, italic: node.italic ?? false,
           fontFamily: node.font_family ?? 'Helvetica', fontSize: node.font_size ?? 12, color: node.color ?? '#000000' }]
      : [];

  const displayContent = storedRuns.length > 0 ? (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', lineHeight: 1.2, wordBreak: 'break-word', whiteSpace: 'pre-wrap' }}>
      {storedRuns.map((run, i) => (
        <span key={i} style={runToSpanStyle(run, scale)}>{run.text}</span>
      ))}
    </div>
  ) : null;

  return (
    <>
      <div
        tabIndex={isEditable ? 0 : -1}
        style={{
          position: 'absolute', zIndex: 20,
          left: geo.x * scale, top: geo.y * scale,
          width: pw, height: ph, boxSizing: 'border-box',
          outline: isEditable && !isEditing
            ? (focused ? '1.5px dashed rgba(74,144,226,0.8)' : '1.5px dashed rgba(74,144,226,0.45)')
            : 'none',
          outlineOffset: '1px',
          cursor: isEditable ? (isEditing ? 'text' : 'grab') : 'default',
        }}
        onPointerDown={isEditable ? startMove : undefined}
        onDoubleClick={isEditable ? () => { setEdit(true); setEditKey(k => k + 1); } : undefined}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        onContextMenu={handleContextMenu}
      >
        {isEditing ? (
          <RichTextEditor
            key={editKey}
            initialHtml={runsToHtml(storedRuns, textProps, scale)}
            scale={scale}
            textProps={textProps}
            isTransient={false}
            onPropsChange={onPropsChange}
            blurRef={nodeBlurRef}
            onCommit={commitEdit}
            onCancel={() => setEdit(false)}
          />
        ) : displayContent}

        {isEditable && !isEditing && (
          <ResizeHandles geo={geo} scale={scale} onResize={handleResize} />
        )}
      </div>

      {ctxMenu && (
        <ContextMenu
          x={ctxMenu.x} y={ctxMenu.y}
          onDelete={() => onDelete?.(node.id)}
          onClose={() => setCtxMenu(null)}
        />
      )}
    </>
  );
}