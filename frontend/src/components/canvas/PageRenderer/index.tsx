// frontend/src/components/canvas/PageRenderer/index.tsx
//
// Thin orchestrator. Responsibilities:
//   - Calls hooks (usePdfCanvas, usePageChars, usePageActions, useDragSelection)
//   - Computes crop box layout (outerW/H, innerX/Y)
//   - Owns localRotation, busy, showToast (cross-cutting state)
//   - Composes sub-components; passes them only what they need

import React, { useRef, useEffect, useState, useCallback } from 'react';
import * as pdfjsLib from 'pdfjs-dist';

import { usePdfCanvas }    from '../../../hooks/usePdfCanvas';
import { usePageChars }    from '../../../hooks/usePageChars';
import { usePageActions }  from '../../../hooks/usePageActions';
import { useDragSelection } from '../../../hooks/useDragSelection';
import { textTool }        from '../../../core/tools/TextTool';

import { PageCanvas }      from './PageCanvas';
import { SearchLayer }     from './SearchLayer';
import { SelectionLayer }  from './SelectionLayer';
import { AnnotationLayer } from './AnnotationLayer';
import { PageChrome }      from './PageChrome';
import { InteractionLayer } from '../InteractionLayer';
import { LiveDrawLayer }   from '../LiveDrawLayer';

import type { TextProps }    from '../../../types/textProps';
import type { ToolId }       from '../../toolbar/Toolbar';
import type { PageNode, AnnotationNode } from '../types';
import type { SearchMatch }  from './SearchLayer';

export interface PageRendererProps {
  pageNode:          PageNode;
  pdfDoc:            pdfjsLib.PDFDocumentProxy;
  pageIndex:         number;
  totalPages:        number;
  scale:             number;
  activeTool:        ToolId;
  textProps:         TextProps;
  sessionId:         string;
  highlightColor?:   string;
  highlightOpacity?: number;
  onTextPropsChange?:  (p: TextProps) => void;
  onAnnotationAdded?:  () => Promise<void>;
  onDocumentChanged?:  () => Promise<void>;
  onTextSelected?:     (text: string) => void;
  containerRef?:       React.Ref<HTMLDivElement>;
  searchMatches?:      SearchMatch[];
  onZoom?:             (delta: number) => void;
}

export function PageRenderer({
  pageNode, pdfDoc, pageIndex, totalPages, scale, activeTool, textProps, sessionId,
  highlightColor, highlightOpacity, onTextPropsChange,
  onAnnotationAdded, onDocumentChanged, onTextSelected,
  containerRef, searchMatches = [], onZoom,
}: PageRendererProps) {

  // ── Cross-cutting state ────────────────────────────────────────────────────
  const clearSelRef            = useRef<(() => void) | null>(null);
  const activeNodeBlurRef      = useRef<(() => void) | null>(null);
  const clearTransientPosRef   = useRef<(() => void) | null>(null);
  const busyRef                = useRef(false);
  const toastTimer             = useRef<ReturnType<typeof setTimeout>>();

  const [annotations,   setAnnotations]  = useState<AnnotationNode[]>(pageNode.children ?? []);
  const [localRotation, setLocalRotation] = useState(pageNode.rotation ?? 0);
  const [busy,          setBusy]          = useState(false);
  const [showToast,     setShowToast]     = useState(false);

  useEffect(() => { setAnnotations(pageNode.children ?? []); }, [pageNode.children]);
  useEffect(() => {
    if (typeof pageNode.rotation === 'number') setLocalRotation(pageNode.rotation);
  }, [pageNode.rotation, pageNode.id]);

  // ── Hooks ──────────────────────────────────────────────────────────────────
  const { canvasRef, fullDimensions } = usePdfCanvas({
    pdfDoc, pageNode, pageIndex, scale, localRotation,
  });

  const { pageChars } = usePageChars({
    pageNodeId: pageNode.id, localRotation, sessionId, metadata: pageNode.metadata,
  });

  const withBusy = useCallback(async (fn: () => Promise<void>) => {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true);
    try { await fn(); } finally { busyRef.current = false; setBusy(false); }
  }, []);

  const toast = useCallback(() => {
    setShowToast(true);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setShowToast(false), 2000);
  }, []);

  const { handleNodeUpdate, handleAction, handleTextCommit, handleNodeDelete } = usePageActions({
    pageNode, pageChars, activeTool, textProps, sessionId,
    setAnnotations,
    setTransientPos: (v) => { if (v === null) clearTransientPosRef.current?.(); },
    highlightColor, highlightOpacity,
    onAnnotationAdded, onTextSelected, clearSelRef, toast,
    textToolNotifyCommitted: () => textTool.notifyCommitted(),
  });

  const { liveRects, committedRects, clearSelection } = useDragSelection({
    pageId: pageNode.id, pageChars, activeTool, metadata: pageNode.metadata,
    onAction: handleAction,
  });

  useEffect(() => { clearSelRef.current = clearSelection; }, [clearSelection]);

  // ── Derived layout values ──────────────────────────────────────────────────
  const displayRects = liveRects.length > 0 ? liveRects : committedRects;
  const cropRect     = activeTool === 'crop' ? (committedRects[0] ?? null) : null;

  const cropBox   = pageNode.crop_box;
  const isCropped = cropBox && typeof cropBox.width === 'number';
  const outerW    = isCropped ? cropBox!.width  * scale : fullDimensions.width;
  const outerH    = isCropped ? cropBox!.height * scale : fullDimensions.height;
  const innerX    = isCropped ? -(cropBox!.x * scale) : 0;
  const innerY    = isCropped ? -(cropBox!.y * scale) : 0;

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <PageChrome
      pageId={pageNode.id}
      pageIndex={pageIndex}
      totalPages={totalPages}
      sessionId={sessionId}
      busy={busy}
      showToast={showToast}
      cropActive={!!cropRect}
      setLocalRotation={setLocalRotation}
      onDocumentChanged={onDocumentChanged}
      withBusy={withBusy}
    >
      {/* Outer crop wrapper — clips to cropBox dimensions if active */}
      <div
        ref={containerRef as React.Ref<HTMLDivElement>}
        style={{ width: outerW, height: outerH }}
        className={isCropped ? 'overflow-hidden' : ''}
      >
        {/* Inner layer — positioned to hide cropped-off area */}
        <div
          style={{
            position: 'absolute',
            top:    innerY,
            left:   innerX,
            width:  fullDimensions.width,
            height: fullDimensions.height,
          }}
        >
          <PageCanvas
            canvasRef={canvasRef}
            width={fullDimensions.width}
            height={fullDimensions.height}
          />

          <SearchLayer matches={searchMatches} scale={scale} />

          <SelectionLayer
            activeTool={activeTool}
            scale={scale}
            displayRects={displayRects}
            cropRect={cropRect}
            fullHeight={fullDimensions.height}
            highlightColor={highlightColor}
            highlightOpacity={highlightOpacity}
            pageId={pageNode.id}
            sessionId={sessionId}
            withBusy={withBusy}
            clearSelection={clearSelection}
            onDocumentChanged={onDocumentChanged}
          />

          <InteractionLayer
            scale={scale}
            pageId={pageNode.id}
            cursor={CURSORS[activeTool] ?? 'default'}
            onPointerDownCapture={() => activeNodeBlurRef.current?.()}
            onZoom={onZoom}
          />

          <LiveDrawLayer pageId={pageNode.id} scale={scale} />

          <AnnotationLayer
            pageNode={pageNode}
            annotations={annotations}
            scale={scale}
            activeTool={activeTool}
            textProps={textProps}
            onTextPropsChange={onTextPropsChange}
            onNodeUpdate={handleNodeUpdate}
            onNodeDelete={handleNodeDelete}
            onRegisterActiveBlur={fn => { activeNodeBlurRef.current = fn; }}
            onRegisterClearTransient={fn => { clearTransientPosRef.current = fn; }}
            onTextCommit={handleTextCommit}
          />
        </div>
      </div>
    </PageChrome>
  );
}

const CURSORS: Partial<Record<ToolId, string>> = {
  hand:      'grab',
  select:    'default',
  zoom:      'zoom-in',
  addtext:   'crosshair',
  edittext:  'text',
  highlight: 'crosshair',
  redact:    'crosshair',
  crop:      'crosshair',
  underline: 'crosshair',
};