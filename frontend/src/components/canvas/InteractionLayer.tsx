import React from 'react';
import { toolManager } from '../../core/tools/ToolManager';
import { InteractionContext } from '../../core/tools/BaseTool';
import { useActiveTool } from '../../hooks/useActiveTool';

interface InteractionLayerProps {
  scale: number;
  pageId: string;
  cursor: string;
  onPointerDownCapture?: () => void;
}

export const InteractionLayer: React.FC<InteractionLayerProps> = ({ scale, pageId, cursor, onPointerDownCapture }) => {
  const activeToolId = useActiveTool();
  const activeTool = toolManager.getActiveTool();

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
        activeTool.onPointerDown?.(createContext(e));
      }}
      onPointerMove={(e) => {
        activeTool.onPointerMove?.(createContext(e));
      }}
      onPointerUp={(e) => {
        if (e.currentTarget.hasPointerCapture(e.pointerId)) {
            e.currentTarget.releasePointerCapture(e.pointerId);
        }
        activeTool.onPointerUp?.(createContext(e));
      }}
      onPointerLeave={(e) => {
        activeTool.onPointerLeave?.(createContext(e));
      }}
    />
  );
};