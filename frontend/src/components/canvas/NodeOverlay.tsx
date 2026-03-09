import React, { useState, useEffect, useRef, useCallback } from 'react';
import { runToSpanStyle, runsToHtml } from '../../utils/textUtils';
import { ResizeHandles, useResizeDrag, type GeoRect } from './ResizeHandles';
import { RichTextEditor } from './RichTextEditor';
import type { TextProps, TextRun } from '../../types/textProps';
import type { ToolId } from '../toolbar/Toolbar';
import type { AnnotationNode } from './types';

interface NodeOverlayProps {
  node:          AnnotationNode;
  scale:         number;
  activeTool?:   ToolId;
  textProps:     TextProps;
  onPropsChange?:(p: TextProps) => void;
  onUpdate?:     (id: string, updates: Partial<AnnotationNode & { runs: TextRun[] }>) => void;
  onRegisterBlur?:(fn: (() => void) | null) => void;
}

export function NodeOverlay({ node, scale, activeTool, textProps, onPropsChange, onUpdate, onRegisterBlur }: NodeOverlayProps) {
  const isTextTool = activeTool === 'select' || activeTool === 'addtext' || activeTool === 'edittext';
  const isEditable = node.node_type === 'text' && isTextTool;

  const [geo, setGeo]        = useState<GeoRect>({ x: node.bbox?.x ?? 0, y: node.bbox?.y ?? 0, w: node.bbox?.width ?? 100, h: node.bbox?.height ?? 30 });
  const [isEditing, setEdit] = useState(false);
  const [editKey, setEditKey]= useState(0); 
  const dragging             = useRef(false);
  const nodeBlurRef          = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (!dragging.current && node.bbox)
      setGeo({ x: node.bbox.x, y: node.bbox.y, w: node.bbox.width, h: node.bbox.height });
  }, [node.bbox]);

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

  const storedRuns: TextRun[] = node.runs && node.runs.length > 0
    ? node.runs
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
          blurRef={nodeBlurRef}
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