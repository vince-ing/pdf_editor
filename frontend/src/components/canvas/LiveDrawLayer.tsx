// frontend/src/components/canvas/LiveDrawLayer.tsx
import React, { useEffect, useState } from 'react';

export function LiveDrawLayer({ pageId, scale }: { pageId: string, scale: number }) {
  const [pathData, setPathData] = useState<{ path: {x: number, y: number}[], color: string, thickness: number } | null>(null);

  useEffect(() => {
    const handleUpdate = (e: CustomEvent) => {
      if (e.detail.pageId === pageId) {
        if (e.detail.path.length === 0) {
          setPathData(null);
        } else {
          setPathData({ path: e.detail.path, color: e.detail.color, thickness: e.detail.thickness });
        }
      }
    };
    
    window.addEventListener('draw-update' as any, handleUpdate);
    return () => window.removeEventListener('draw-update' as any, handleUpdate);
  }, [pageId]);

  if (!pathData || pathData.path.length < 2) return null;

  const d = `M ${pathData.path[0].x * scale} ${pathData.path[0].y * scale} ` + 
            pathData.path.slice(1).map(p => `L ${p.x * scale} ${p.y * scale}`).join(' ');

  return (
    <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 25 }}>
      <path 
        d={d}
        stroke={pathData.color}
        strokeWidth={pathData.thickness * scale}
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}