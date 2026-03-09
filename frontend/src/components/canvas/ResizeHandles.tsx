import React, { useCallback } from 'react';

export type GeoRect = { x: number; y: number; w: number; h: number };

export type HandleDef = { id: string; cursor: string; tx: number; ty: number; dx: 1|0|-1; dy: 1|0|-1 };
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

export function useResizeDrag(scale: number, onUpdate: (g: GeoRect) => void) {
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

export function ResizeHandles({ geo, scale, onResize }: {
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