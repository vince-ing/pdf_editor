// frontend/src/components/canvas/PageRenderer/SelectionLayer.tsx
// Renders:
//   1. Live/committed drag selection rectangles
//   2. Crop shadow overlay (the four darkened regions outside the crop rect)
//   3. Crop action buttons (Apply / Cancel)

import React from 'react';
import type { ToolId } from '../../toolbar/Toolbar';
import { engineApi } from '../../../api/client';

const SEL_COLOR: Partial<Record<ToolId, string>> = {
  highlight: 'rgba(245,158,11,0.25)',
  redact:    'rgba(239,68,68,0.25)',
  select:    'rgba(74,144,226,0.2)',
  crop:      'rgba(0,0,0,0)',
  underline: 'rgba(255,255,255,0.1)',
};

interface Rect { x: number; y: number; width: number; height: number }

interface SelectionLayerProps {
  activeTool:      ToolId;
  scale:           number;
  displayRects:    Rect[];
  cropRect:        Rect | null;
  fullHeight:      number;
  highlightColor?: string;
  highlightOpacity?: number;
  // crop actions
  pageId:          string;
  sessionId:       string;
  withBusy:        (fn: () => Promise<void>) => Promise<void>;
  clearSelection:  () => void;
  onDocumentChanged?: () => Promise<void>;
}

export function SelectionLayer({
  activeTool, scale, displayRects, cropRect, fullHeight,
  highlightColor, highlightOpacity,
  pageId, sessionId, withBusy, clearSelection, onDocumentChanged,
}: SelectionLayerProps) {
  return (
    <>
      {/* ── Crop shadow ─────────────────────────────────────────────── */}
      {cropRect && (
        <div className="absolute inset-0 pointer-events-none z-[8]">
          {[
            { top: 0, left: 0, right: 0, height: cropRect.y * scale },
            { bottom: 0, left: 0, right: 0, top: (cropRect.y + cropRect.height) * scale },
            { top: cropRect.y * scale, left: 0, width: cropRect.x * scale, height: cropRect.height * scale },
            { top: cropRect.y * scale, left: (cropRect.x + cropRect.width) * scale, right: 0, height: cropRect.height * scale },
          ].map((s, i) => (
            <div key={i} className="absolute bg-black/50" style={s} />
          ))}
        </div>
      )}

      {/* ── Drag selection rects ────────────────────────────────────── */}
      {displayRects.map((rect, i) => {
        let bg = SEL_COLOR[activeTool] ?? 'rgba(74,144,226,0.2)';
        if (activeTool === 'highlight' && highlightColor) {
          const hex = highlightColor.replace('#', '');
          if (hex.length === 6) {
            const r = parseInt(hex.substring(0, 2), 16);
            const g = parseInt(hex.substring(2, 4), 16);
            const b = parseInt(hex.substring(4, 6), 16);
            bg = `rgba(${r}, ${g}, ${b}, ${highlightOpacity ?? 0.45})`;
          }
        }
        return (
          <div
            key={i}
            className="absolute pointer-events-none z-10"
            style={{
              left:       rect.x     * scale,
              top:        rect.y     * scale,
              width:      rect.width * scale,
              height:     rect.height * scale,
              background: bg,
              border:     activeTool === 'crop' ? '2px dashed #f97316' : 'none',
              borderRadius: 1,
            }}
          />
        );
      })}

      {/* ── Crop action buttons ─────────────────────────────────────── */}
      {cropRect && (
        <div
          className="absolute z-30 flex gap-2"
          style={{
            bottom:    fullHeight - (cropRect.y + cropRect.height) * scale + 10,
            left:      '50%',
            transform: 'translateX(-50%)',
          }}
        >
          <button
            onClick={() => withBusy(async () => {
              await engineApi.cropPage(
                pageId, cropRect.x, cropRect.y, cropRect.width, cropRect.height, sessionId,
              );
              clearSelection();
              await onDocumentChanged?.();
            })}
            className="h-7 px-4 bg-green-500 text-[#0a1f17] text-xs font-semibold rounded-md hover:bg-green-400 transition-colors"
          >
            ✓ Apply
          </button>
          <button
            onClick={clearSelection}
            className="h-7 px-3 bg-[#2d3338] text-gray-300 text-xs border border-white/10 rounded-md hover:bg-[#3d4449] transition-colors"
          >
            Cancel
          </button>
        </div>
      )}
    </>
  );
}