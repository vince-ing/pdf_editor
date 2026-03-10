// frontend/src/components/canvas/TransientTextBox.tsx

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { type TextProps, type TextRun } from '../../types/textProps';
import { RichTextEditor } from './RichTextEditor';
import { ResizeHandles, useResizeDrag, type GeoRect } from './ResizeHandles';

export interface TransientBoxProps {
  initialX: number; initialY: number;
  initialW?: number; initialH?: number;
  isDrawing?: boolean;
  scale:      number;
  textProps:  TextProps;
  onPropsChange?: (p: TextProps) => void;
  onCommit: (runs: TextRun[], plain: string, x: number, y: number, w: number, h: number) => void;
  onCancel: () => void;
  blurRef?: React.MutableRefObject<(() => void) | null>;
}

export function TransientTextBox({ initialX, initialY, initialW, initialH, isDrawing, scale, textProps, onPropsChange, onCommit, onCancel, blurRef }: TransientBoxProps) {
  const INIT_W = (initialW && initialW > 5) ? initialW : 160;
  const INIT_H = (initialH && initialH > 5) ? initialH : (Math.ceil(textProps.fontSize * 1.2) + 2);
  
  const [geo, setGeo] = useState<GeoRect>({ x: initialX, y: initialY, w: INIT_W, h: INIT_H });
  const [isAuto, setIsAuto] = useState(!(initialW && initialW > 5));
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isDrawing) {
      setGeo({ x: initialX, y: initialY, w: initialW ?? 0, h: initialH ?? 0 });
    }
  }, [initialX, initialY, initialW, initialH, isDrawing]);

  const startMove = useCallback((e: React.PointerEvent) => {
    if ((e.target as HTMLElement).isContentEditable) return;
    e.preventDefault(); e.stopPropagation();
    const sx = e.clientX, sy = e.clientY, ox = geo.x, oy = geo.y;
    const onMove = (ev: PointerEvent) => setGeo(g => ({ ...g, x: ox + (ev.clientX - sx) / scale, y: oy + (ev.clientY - sy) / scale }));
    const onUp   = () => { window.removeEventListener('pointermove', onMove); window.removeEventListener('pointerup', onUp); };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  }, [geo.x, geo.y, scale]);

  const handleAutoResize = useCallback((newGeo: GeoRect) => {
    setIsAuto(false);
    setGeo(newGeo);
  }, []);
  
  const handleResize = useResizeDrag(scale, handleAutoResize);

  const geoRef = useRef(geo);
  useEffect(() => { geoRef.current = geo; }, [geo]);

  // MUST be below all hooks
  if (isDrawing) {
    return (
      <div
        style={{
          position: 'absolute',
          left: geo.x * scale, top: geo.y * scale,
          width: geo.w * scale, height: geo.h * scale,
          zIndex: 60, boxSizing: 'border-box',
          border: '1.5px dashed #4a90e2',
          backgroundColor: 'rgba(74, 144, 226, 0.1)',
          pointerEvents: 'none'
        }}
      />
    );
  }

  return (
    <div
      ref={boxRef}
      style={{
        position: 'absolute',
        left: geo.x * scale, top: geo.y * scale,
        width: geo.w * scale,
        minHeight: geo.h * scale,
        height: isAuto ? 'fit-content' : geo.h * scale,
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
          let finalW = g.w;
          let finalH = g.h;
          if (boxRef.current) {
            finalW = boxRef.current.offsetWidth / scale;
            finalH = boxRef.current.offsetHeight / scale;
          }
          onCommit(runs, plain, g.x, g.y, finalW, finalH);
        }}
        onCancel={onCancel}
      />
      <ResizeHandles geo={geo} scale={scale} onResize={handleResize} />
    </div>
  );
}