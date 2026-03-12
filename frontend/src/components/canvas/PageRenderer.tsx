// frontend/src/components/canvas/PageRenderer.tsx
// (Add onZoom to props and pass to InteractionLayer)
// ... Keep existing imports
import React, { useRef, useEffect, useState, useCallback } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import { engineApi } from '../../api/client';
import { usePdfCanvas } from '../../hooks/usePdfCanvas';
import { usePageChars } from '../../hooks/usePageChars';
import { useDragSelection } from '../../hooks/useDragSelection';
import { usePageActions } from '../../hooks/usePageActions';

import type { TextProps } from '../../types/textProps';
import type { ToolId } from '../toolbar/Toolbar';
import type { PageNode, AnnotationNode } from './types';

import { InteractionLayer } from './InteractionLayer';
import { textTool } from '../../core/tools/TextTool';
import { TransientTextBox } from './TransientTextBox';
import { NodeOverlay } from './NodeOverlay';
import { CopyToast } from './CopyToast';
import { PageControls } from './PageControls';
import { LiveDrawLayer } from './LiveDrawLayer';

const CURSORS: Partial<Record<ToolId, string>> = {
  hand: 'grab', select: 'default', zoom: 'zoom-in',
  addtext: 'crosshair', edittext: 'text',
  highlight: 'crosshair', redact: 'crosshair', crop: 'crosshair', underline: 'crosshair',
};

const SEL_COLOR: Partial<Record<ToolId, string>> = {
  highlight: 'rgba(245,158,11,0.25)', redact: 'rgba(239,68,68,0.25)',
  select: 'rgba(74,144,226,0.2)', crop: 'rgba(0,0,0,0)', underline: 'rgba(255,255,255,0.1)',
};

export interface PageRendererProps {
  pageNode: PageNode;
  pdfDoc: pdfjsLib.PDFDocumentProxy;
  pageIndex: number;
  totalPages: number;
  scale: number;
  activeTool: ToolId;
  textProps: TextProps;
  sessionId: string;
  highlightColor?: string;
  highlightOpacity?: number;
  onTextPropsChange?: (p: TextProps) => void;
  onAnnotationAdded?: () => Promise<void>;
  onDocumentChanged?: () => Promise<void>;
  onTextSelected?: (text: string) => void;
  containerRef?: React.Ref<HTMLDivElement>;
  searchMatches?: { rects: { x: number; y: number; width: number; height: number }[]; matchIndex: number; isCurrent: boolean }[];
  onZoom?: (delta: number) => void;
}

export function PageRenderer({
  pageNode, pdfDoc, pageIndex, totalPages, scale, activeTool, textProps, sessionId,
  highlightColor, highlightOpacity, onTextPropsChange,
  onAnnotationAdded, onDocumentChanged, onTextSelected, containerRef,
  searchMatches = [],
  onZoom
}: PageRendererProps) {
  const clearSelRef = useRef<(() => void) | null>(null);
  const toastTimer  = useRef<ReturnType<typeof setTimeout>>();
  const busyRef     = useRef(false);

  const transientBlurRef    = useRef<(() => void) | null>(null);
  const activeNodeBlurRef   = useRef<(() => void) | null>(null);

  const [annotations,    setAnnotations]   = useState<AnnotationNode[]>(pageNode.children ?? []);
  const [hovered,        setHovered]       = useState(false);
  const [busy,           setBusy]          = useState(false);
  const [localRotation,  setLocalRotation] = useState(pageNode.rotation ?? 0);
  const [showToast,      setShowToast]     = useState(false);
  const [showCtrl,       setShowCtrl]      = useState(false);
  const [transientPos,   setTransientPos]  = useState<{ x: number; y: number; w?: number; h?: number; isDrawing?: boolean } | null>(null);

  useEffect(() => { setAnnotations(pageNode.children ?? []); }, [pageNode.children]);
  useEffect(() => { if (typeof pageNode.rotation === 'number') setLocalRotation(pageNode.rotation); }, [pageNode.rotation, pageNode.id]);

  useEffect(() => {
    const unsubPos = textTool.onPositionStateChange((pos) => {
      if (!pos) {
        setTransientPos(null);
      } else if (pos.pageId === pageNode.id) {
        setTransientPos({ x: pos.x, y: pos.y, w: pos.w, h: pos.h, isDrawing: pos.isDrawing });
      }
    });
    const unsubCommit = textTool.onCommitRequest(() => transientBlurRef.current?.());
    return () => { unsubPos(); unsubCommit(); };
  }, [pageNode.id]);

  const { canvasRef, fullDimensions } = usePdfCanvas({ pdfDoc, pageNode, pageIndex, scale, localRotation });
  const { pageChars } = usePageChars({ pageNodeId: pageNode.id, localRotation, sessionId, metadata: pageNode.metadata });

  const withBusy = useCallback(async (fn: () => Promise<void>) => {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true);
    try { await fn(); } finally { busyRef.current = false; setBusy(false); }
  }, []);

  const toast = useCallback(() => {
    setShowToast(true); clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setShowToast(false), 2000);
  }, []);

  const { handleNodeUpdate, handleAction, handleTextCommit, handleNodeDelete } = usePageActions({
    pageNode, pageChars, activeTool, textProps, sessionId, setAnnotations, setTransientPos,
    highlightColor, highlightOpacity,
    onAnnotationAdded, onTextSelected, clearSelRef, toast,
    textToolNotifyCommitted: () => textTool.notifyCommitted()
  });

  const { liveRects, committedRects, clearSelection } = useDragSelection({
    pageId: pageNode.id, pageChars, activeTool, metadata: pageNode.metadata, onAction: handleAction
  });
  
  useEffect(() => { clearSelRef.current = clearSelection; }, [clearSelection]);

  const displayRects = liveRects.length > 0 ? liveRects : committedRects;
  const cropRect = activeTool === 'crop' && committedRects[0];

  const cropBox   = pageNode.crop_box;
  const isCropped = cropBox && typeof cropBox.width === 'number';
  const outerW = isCropped ? cropBox!.width  * scale : fullDimensions.width;
  const outerH = isCropped ? cropBox!.height * scale : fullDimensions.height;
  const innerX = isCropped ? -(cropBox!.x    * scale) : 0;
  const innerY = isCropped ? -(cropBox!.y    * scale) : 0;

  return (
    <div
      ref={containerRef as React.Ref<HTMLDivElement>}
      style={{ width: outerW, height: outerH, opacity: busy ? 0.75 : 1 }}
      className={`relative bg-white flex-shrink-0 mx-auto mb-6 transition-shadow rounded-sm ${hovered ? 'shadow-2xl' : 'shadow-xl'} ${isCropped ? 'overflow-hidden' : ''}`}
      onMouseEnter={() => { setHovered(true);  setShowCtrl(true);  }}
      onMouseLeave={() => { setHovered(false); setShowCtrl(false); }}
    >
      {showCtrl && !cropRect && (
        <PageControls
          pageId={pageNode.id} pageIndex={pageIndex} totalPages={totalPages}
          sessionId={sessionId}
          withBusy={withBusy} onDocumentChanged={onDocumentChanged} setLocalRotation={setLocalRotation}
        />
      )}

      <div style={{ position: 'absolute', top: innerY, left: innerX, width: fullDimensions.width, height: fullDimensions.height }}>
        <canvas ref={canvasRef} className="absolute inset-0 pointer-events-none" style={{ width: fullDimensions.width, height: fullDimensions.height }} />

        {/* ── Search match highlights ─────────────────────────────────── */}
        {searchMatches.map((match, mi) =>
          match.rects.map((rect, ri) => (
            <div
              key={`search-${mi}-${ri}`}
              className="absolute pointer-events-none"
              style={{
                left:            rect.x      * scale,
                top:             rect.y      * scale,
                width:           rect.width  * scale,
                height:          rect.height * scale,
                backgroundColor: match.isCurrent
                  ? 'rgba(250, 204, 21, 0.75)'   // yellow  — current match
                  : 'rgba(147, 51, 234, 0.45)',   // purple  — other matches
                mixBlendMode: 'multiply',
                borderRadius: 2,
                zIndex: match.isCurrent ? 16 : 15,
                transition: 'background-color 0.15s',
              }}
            />
          ))
        )}

        {cropRect && (
          <div className="absolute inset-0 pointer-events-none z-[8]">
            {[
              { top: 0, left: 0, right: 0, height: cropRect.y * scale },
              { bottom: 0, left: 0, right: 0, top: (cropRect.y + cropRect.height) * scale },
              { top: cropRect.y * scale, left: 0, width: cropRect.x * scale, height: cropRect.height * scale },
              { top: cropRect.y * scale, left: (cropRect.x + cropRect.width) * scale, right: 0, height: cropRect.height * scale },
            ].map((s, i) => <div key={i} className="absolute bg-black/50" style={s} />)}
          </div>
        )}

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
            <div key={i} className="absolute pointer-events-none z-10" style={{
              left: rect.x * scale, top: rect.y * scale,
              width: rect.width * scale, height: rect.height * scale,
              background: bg,
              border: activeTool === 'crop' ? '2px dashed #f97316' : 'none', borderRadius: 1,
            }} />
          );
        })}

        <InteractionLayer
          scale={scale}
          pageId={pageNode.id}
          cursor={CURSORS[activeTool] ?? 'default'}
          onPointerDownCapture={() => {
            if (activeNodeBlurRef.current) activeNodeBlurRef.current();
          }}
          onZoom={onZoom}
        />

        <LiveDrawLayer pageId={pageNode.id} scale={scale} />

        {/* ── Annotation overlays — rendered exactly once ── */}
        {annotations.map(node => (
          <NodeOverlay
            key={node.id} node={node} scale={scale}
            activeTool={activeTool} textProps={textProps}
            onPropsChange={onTextPropsChange}
            onUpdate={handleNodeUpdate}
            onDelete={handleNodeDelete}
            onRegisterBlur={fn => { activeNodeBlurRef.current = fn; }}
          />
        ))}

        {transientPos && (
          <TransientTextBox
            initialX={transientPos.x} initialY={transientPos.y}
            initialW={transientPos.w} initialH={transientPos.h}
            isDrawing={transientPos.isDrawing}
            scale={scale} textProps={textProps}
            onPropsChange={onTextPropsChange}
            blurRef={transientBlurRef}
            onCommit={handleTextCommit}
            onCancel={() => {
              setTransientPos(null);
              textTool.notifyCommitted();
            }}
          />
        )}
      </div>

      {cropRect && (
        <div className="absolute z-30 flex gap-2" style={{ bottom: fullDimensions.height - (cropRect.y + cropRect.height) * scale + 10, left: '50%', transform: 'translateX(-50%)' }}>
          <button onClick={() => withBusy(async () => { await engineApi.cropPage(pageNode.id, cropRect.x, cropRect.y, cropRect.width, cropRect.height, sessionId); clearSelection(); await onDocumentChanged?.(); })}
            className="h-7 px-4 bg-green-500 text-[#0a1f17] text-xs font-semibold rounded-md hover:bg-green-400 transition-colors">✓ Apply</button>
          <button onClick={clearSelection}
            className="h-7 px-3 bg-[#2d3338] text-gray-300 text-xs border border-white/10 rounded-md hover:bg-[#3d4449] transition-colors">Cancel</button>
        </div>
      )}

      {busy && (
        <div className="absolute inset-0 bg-black/10 flex items-center justify-center z-50">
          <div className="bg-[#2d3338] text-white text-xs font-semibold px-4 py-2 rounded-lg border border-white/10 shadow-xl">Working…</div>
        </div>
      )}
      <CopyToast visible={showToast} />
    </div>
  );
}