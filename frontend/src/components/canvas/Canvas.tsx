// frontend/src/components/canvas/Canvas.tsx
import React, { useRef, useEffect, useState, useImperativeHandle, forwardRef, useCallback } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import { DEFAULT_TEXT_PROPS, type TextProps } from '../../types/textProps';
import { PageRenderer } from './PageRenderer';
import { PageErrorBoundary } from './PageErrorBoundary';
import type { ToolId } from '../toolbar/Toolbar';
import type { DocumentState } from './types';
import { useTheme } from '../../theme';
import type { PageMatchMap } from '../../hooks/useSearchState';

export interface CanvasHandle {
  // Call this instead of pageRefs.current[i]?.scrollIntoView() when jumping
  // from the thumbnail sidebar. It force-renders the target page first so
  // scrollIntoView lands on a real element with correct height.
  jumpToPage: (index: number) => void;
}

export interface CanvasProps {
  pdfDoc?: pdfjsLib.PDFDocumentProxy | null; documentState?: DocumentState | null;
  activeTool: ToolId; scale: number; sessionId: string;
  textProps?: TextProps; highlightColor?: string; highlightOpacity?: number;
  onTextPropsChange?: (p: TextProps) => void; onAnnotationAdded?: () => Promise<void>;
  onDocumentChanged?: () => Promise<void>; onTextSelected?: (text: string) => void;
  pageRefs?: React.MutableRefObject<(HTMLDivElement | null)[]>;
  canvasScrollRef?: React.MutableRefObject<HTMLDivElement | null>;
  pageMatchMap?: PageMatchMap;
  onZoom?: (delta: number) => void;
}

// ── LazyPage ──────────────────────────────────────────────────────────────────
// Each page starts hidden (placeholder div with estimated height).
// It becomes visible when EITHER:
//   (a) it scrolls within 1 viewport of the scroll container, OR
//   (b) forceVisible=true is set externally (thumbnail jump)
//
// The two-phase triggered/visible split ensures we never render with pdfDoc=null.

interface LazyPageProps {
  pdfDocReady:   boolean;
  estimatedHeight: number;
  forceVisible:  boolean;
  outerRef?:     React.Ref<HTMLDivElement>;   // ref on the sentinel — used for scroll targeting
  children:      (visible: boolean) => React.ReactNode;
}

function LazyPage({ pdfDocReady, estimatedHeight, forceVisible, outerRef, children }: LazyPageProps) {
  const sentinelRef = useRef<HTMLDivElement>(null);
  const [triggered, setTriggered] = useState(false);
  const [visible,   setVisible]   = useState(false);

  // Phase 1a: intersection observer — fires when page scrolls near viewport
  useEffect(() => {
    if (visible) return;
    const el = sentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setTriggered(true); observer.disconnect(); } },
      { rootMargin: '100% 0px', threshold: 0 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [visible]);

  // Phase 1b: forceVisible — thumbnail jump bypasses the scroll requirement
  useEffect(() => {
    if (forceVisible) setTriggered(true);
  }, [forceVisible]);

  // Phase 2: only go visible once triggered AND pdfDoc is ready
  useEffect(() => {
    if (triggered && pdfDocReady) setVisible(true);
  }, [triggered, pdfDocReady]);

  // Merge the internal sentinel ref with the external outerRef
  const setRefs = (el: HTMLDivElement | null) => {
    (sentinelRef as React.MutableRefObject<HTMLDivElement | null>).current = el;
    if (typeof outerRef === 'function') outerRef(el);
    else if (outerRef) (outerRef as React.MutableRefObject<HTMLDivElement | null>).current = el;
  };

  return (
    <div ref={setRefs} style={{ minHeight: visible ? undefined : estimatedHeight }}>
      {children(visible)}
    </div>
  );
}
// ──────────────────────────────────────────────────────────────────────────────

export const Canvas = forwardRef<CanvasHandle, CanvasProps>(function Canvas({
  pdfDoc, documentState, activeTool = 'select', scale = 1.5, sessionId,
  textProps = DEFAULT_TEXT_PROPS, highlightColor, highlightOpacity, onTextPropsChange,
  onAnnotationAdded, onDocumentChanged, onTextSelected, pageRefs,
  canvasScrollRef,
  pageMatchMap = {},
  onZoom,
}, ref) {
  const { theme: t } = useTheme();
  const pdfDocReady      = !!pdfDoc;
  const approxPageHeight = 792 * scale;

  // Tracks which pages have been force-triggered by jumpToPage.
  // Using a Set in state so we can add indices without re-creating all pages.
  const [forcedPages, setForcedPages] = useState<Set<number>>(new Set());

  // Expose jumpToPage to parent (App.tsx / LeftSidebar handler)
  useImperativeHandle(ref, () => ({
    jumpToPage: (index: number) => {
      if (!pdfDocReady) return;

      const alreadyRendered = forcedPages.has(index);

      // Force-render the target page if not yet visible
      setForcedPages(prev => {
        if (prev.has(index)) return prev;
        const next = new Set(prev);
        next.add(index);
        return next;
      });

      // Wait for React to commit + canvas to paint, then scroll instantly.
      // Unrendered pages need longer (300ms) since the canvas must paint first.
      // Already-rendered pages can scroll immediately (0ms / next tick).
      const delay = alreadyRendered ? 0 : 300;

      setTimeout(() => {
        const el = pageRefs?.current[index];
        const container = canvasScrollRef?.current;
        if (!el || !container) return;

        // getBoundingClientRect gives positions relative to the viewport.
        // Subtracting container's top and adding current scrollTop converts
        // that to an offset within the scrollable area — reliable regardless
        // of offsetParent chain (which does not always lead to the container).
        const elRect        = el.getBoundingClientRect();
        const containerRect = container.getBoundingClientRect();
        const scrollTarget  = container.scrollTop + elRect.top - containerRect.top;

        container.scrollTop = Math.max(0, scrollTarget);
      }, delay);
    },
  }), [pdfDocReady, pageRefs, canvasScrollRef, forcedPages]);

  // Reset forced pages when document changes (new tab / new file)
  useEffect(() => { setForcedPages(new Set()); }, [sessionId]);

  return (
    <div
      ref={canvasScrollRef}
      className="overflow-auto scrollbar-thumb-only"
      style={{
        flex: 1, backgroundColor: t.colors.bgHover,
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        paddingTop: 32, paddingBottom: 32, paddingLeft: 16, paddingRight: 16,
        touchAction: 'none',
      }}
    >
      {!documentState ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 20, userSelect: 'none' }}>
          <div style={{ width: 64, height: 64, backgroundColor: t.colors.bgRaised, borderRadius: t.radius.lg, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28, border: `1px solid ${t.colors.border}`, boxShadow: t.shadow.panel }}>📄</div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '15px', fontWeight: 600, color: t.colors.textPrimary, marginBottom: 4, fontFamily: t.fonts.ui }}>Open a document to begin</div>
            <div style={{ fontSize: '13px', color: t.colors.textSecondary, fontFamily: t.fonts.ui }}>File → Open, or press Ctrl+O</div>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'center', maxWidth: 280 }}>
            {['Highlight · Redact', 'Add Text · Images', 'Reorder · Rotate', 'Read Aloud · Export'].map(f => (
              <span key={f} style={{ fontSize: '11px', color: t.colors.textMuted, backgroundColor: t.colors.bgRaised, border: `1px solid ${t.colors.border}`, borderRadius: t.radius.pill, padding: '3px 12px', fontFamily: t.fonts.ui }}>{f}</span>
            ))}
          </div>
        </div>
      ) : (
        documentState.children?.map((page, i) => (
          <PageErrorBoundary key={page.id} pageIndex={i}>
            <LazyPage
              pdfDocReady={pdfDocReady}
              estimatedHeight={approxPageHeight}
              forceVisible={forcedPages.has(i)}
              outerRef={el => { if (pageRefs) pageRefs.current[i] = el; }}
            >
              {(visible) => visible && (
                <PageRenderer
                  pageNode={page}
                  pdfDoc={pdfDoc!}
                  pageIndex={i}
                  totalPages={documentState.children?.length ?? 1}
                  scale={scale}
                  activeTool={activeTool}
                  sessionId={sessionId}
                  textProps={textProps}
                  highlightColor={highlightColor}
                  highlightOpacity={highlightOpacity}
                  onTextPropsChange={onTextPropsChange}
                  onAnnotationAdded={onAnnotationAdded}
                  onDocumentChanged={onDocumentChanged}
                  onTextSelected={onTextSelected}
                  searchMatches={pageMatchMap[page.id] ?? []}
                  onZoom={onZoom}
                />
              )}
            </LazyPage>
          </PageErrorBoundary>
        ))
      )}
    </div>
  );
});