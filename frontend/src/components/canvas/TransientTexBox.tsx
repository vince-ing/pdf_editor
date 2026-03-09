import React, { useState, useCallback, useRef, useEffect } from 'react';
import { type TextProps, type TextRun } from '../../types/textProps';
import { RichTextEditor } from './RichTextEditor';
import { ResizeHandles, useResizeDrag, type GeoRect } from './ResizeHandles';

export interface TransientBoxProps {
  initialX: number; initialY: number;
  scale:      number;
  textProps:  TextProps;
  onPropsChange?: (p: TextProps) => void;
  onCommit: (runs: TextRun[], plain: string, x: number, y: number, w: number, h: number) => void;
  onCancel: () => void;
  blurRef?: React.MutableRefObject<(() => void) | null>;
}

export function TransientTextBox({ initialX, initialY, scale, textProps, onPropsChange, onCommit, onCancel, blurRef }: TransientBoxProps) {
  const INIT_W = 160;
  const INIT_H = Math.ceil(textProps.fontSize * 1.2) + 2;
  const [geo, setGeo] = useState<GeoRect>({ x: initialX, y: initialY, w: INIT_W, h: INIT_H });

  const startMove = useCallback((e: React.PointerEvent) => {
    if ((e.target as HTMLElement).isContentEditable) return;
    e.preventDefault(); e.stopPropagation();
    const sx = e.clientX, sy = e.clientY, ox = geo.x, oy = geo.y;
    const onMove = (ev: PointerEvent) => setGeo(g => ({ ...g, x: ox + (ev.clientX - sx) / scale, y: oy + (ev.clientY - sy) / scale }));
    const onUp   = () => { window.removeEventListener('pointermove', onMove); window.removeEventListener('pointerup', onUp); };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  }, [geo.x, geo.y, scale]);

  const handleResize = useResizeDrag(scale, setGeo);

  const geoRef = useRef(geo);
  useEffect(() => { geoRef.current = geo; }, [geo]);

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
        blurRef={blurRef}
        onCommit={(runs, plain) => {
          const g = geoRef.current;
          onCommit(runs, plain, g.x, g.y, g.w, g.h);
        }}
        onCancel={onCancel}
      />
      <ResizeHandles geo={geo} scale={scale} onResize={handleResize} />
    </div>
  );
}