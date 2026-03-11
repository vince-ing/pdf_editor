// frontend/src/components/canvas/InteractionLayer.tsx
import React, { useRef } from 'react';
import { toolManager } from '../../core/tools/ToolManager';
import { InteractionContext } from '../../core/tools/BaseTool';
import { useActiveTool } from '../../hooks/useActiveTool';
import { useEditorState } from '../../hooks/useEditorState'; // You will need to pass setScale down from App -> Canvas -> PageRenderer -> InteractionLayer if you want strict pure components, but we can hook into window events for zoom.

interface InteractionLayerProps {
  scale: number;
  pageId: string;
  cursor: string;
  onPointerDownCapture?: () => void;
  onZoom?: (delta: number) => void; // New prop to handle zoom
}

export const InteractionLayer: React.FC<InteractionLayerProps> = ({ scale, pageId, cursor, onPointerDownCapture, onZoom }) => {
  const activeToolId = useActiveTool();
  const activeTool = toolManager.getActiveTool();
  
  // Track multi-touch for pinch-to-zoom
  const pointers = useRef<Map<number, { x: number, y: number }>>(new Map());
  const initialPinchDist = useRef<number | null>(null);

  if (!activeTool) return null;

  const createContext = (e: React.PointerEvent<HTMLDivElement>): InteractionContext => {
    const rect = e.currentTarget.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left) / scale,
      y: (e.clientY - rect.top) / scale,
      originalEvent: e,
      scale,
      pageId
    };
  };

  return (
    <div
      className="absolute inset-0 z-20 touch-none"
      style={{ cursor, userSelect: 'none' }}
      onPointerDown={(e) => {
        onPointerDownCapture?.();
        e.currentTarget.setPointerCapture(e.pointerId);
        
        pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
        
        if (pointers.current.size === 2) {
            const pts = Array.from(pointers.current.values());
            initialPinchDist.current = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
            // Cancel any active drawing/dragging if we switch to a pinch gesture
            if (activeTool.onDeactivate) activeTool.onDeactivate();
        } else if (pointers.current.size === 1) {
            activeTool.onPointerDown?.(createContext(e));
        }
      }}
      onPointerMove={(e) => {
        if (pointers.current.has(e.pointerId)) {
            pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
        }
        
        if (pointers.current.size === 2 && initialPinchDist.current !== null && onZoom) {
            // Handle pinch zoom
            const pts = Array.from(pointers.current.values());
            const currentDist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
            
            // Calculate scale delta based on pinch distance change
            const delta = currentDist - initialPinchDist.current;
            
            // Only trigger zoom if the pinch moved significantly (prevent jitter)
            if (Math.abs(delta) > 20) {
               // Negative delta means pinch in (zoom out), positive means pinch out (zoom in)
               onZoom(delta > 0 ? 0.05 : -0.05); 
               // Reset the initial distance to the new current distance so it zooms continuously as you drag
               initialPinchDist.current = currentDist;
            }
        } else if (pointers.current.size === 1) {
            // Standard single pointer move
            activeTool.onPointerMove?.(createContext(e));
        }
      }}
      onPointerUp={(e) => {
        if (e.currentTarget.hasPointerCapture(e.pointerId)) {
            e.currentTarget.releasePointerCapture(e.pointerId);
        }
        pointers.current.delete(e.pointerId);
        if (pointers.current.size < 2) {
             initialPinchDist.current = null;
        }
        
        // Only fire pointerUp for the tool if we weren't just pinching
        if (pointers.current.size === 0 && initialPinchDist.current === null) {
            activeTool.onPointerUp?.(createContext(e));
        }
      }}
      onPointerLeave={(e) => {
        pointers.current.delete(e.pointerId);
        if (pointers.current.size < 2) {
             initialPinchDist.current = null;
        }
        activeTool.onPointerLeave?.(createContext(e));
      }}
    />
  );
};