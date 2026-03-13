// frontend/src/components/canvas/Canvas.tsx
import React, { useRef, useEffect, useState } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import { DEFAULT_TEXT_PROPS, type TextProps } from '../../types/textProps';
import { PageRenderer } from './PageRenderer';
import { PageErrorBoundary } from './PageErrorBoundary';
import type { ToolId } from '../toolbar/Toolbar';
import type { DocumentState } from './types';
import { useTheme } from '../../theme';
import type { PageMatchMap } from '../../hooks/useSearchState';

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
// Renders a placeholder until the page scrolls near the viewport, then mounts
// the real PageRenderer.
//
// IMPORTANT: We must NOT permanently commit `visible = true` until pdfDoc is
// confirmed non-null. If the IntersectionObserver fires while pdfDoc is still
// null (which happens on page 1 because the observer fires synchronously during
// the React commit phase, before the async tab-load has finished batching
// pdfDoc + documentState into the same render), PageRenderer mounts with
// pdfDoc=null, usePdfCanvas bails out immediately, and since we already
// disconnected the observer the page is permanently blank.
//
// Fix: split into two phases:
//   triggered  — observer fired (page is/was in viewport)
//   visible    — triggered AND pdfDoc is ready → safe to mount PageRenderer

interface LazyPageProps {
  pdfDocReady:     boolean;
  estimatedHeight: number;
  children:        (visible: boolean) => React.ReactNode;
}

function LazyPage({ pdfDocReady, estimatedHeight, children }: LazyPageProps) {
  const sentinelRef = useRef<HTMLDivElement>(null);
  const [triggered, setTriggered] = useState(false);
  const [visible,   setVisible]   = useState(false);

  // Phase 1: observe proximity to viewport
  useEffect(() => {
    if (visible) return;
    const el = sentinelRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setTriggered(true);
          observer.disconnect();
        }
      },
      { rootMargin: '100% 0px', threshold: 0 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [visible]);

  // Phase 2: only go visible once BOTH triggered AND pdfDoc arrived.
  useEffect(() => {
    if (triggered && pdfDocReady) setVisible(true);
  }, [triggered, pdfDocReady]);

  return (
    <div ref={sentinelRef} style={{ minHeight: visible ? undefined : estimatedHeight }}>
      {children(visible)}
    </div>
  );
}

export function Canvas({
  pdfDoc, documentState, activeTool = 'select', scale = 1.5, sessionId,
  textProps = DEFAULT_TEXT_PROPS, highlightColor, highlightOpacity, onTextPropsChange,
  onAnnotationAdded, onDocumentChanged, onTextSelected, pageRefs,
  canvasScrollRef,
  pageMatchMap = {},
  onZoom,
}: CanvasProps) {
  const { theme: t } = useTheme();
  const pdfDocReady    = !!pdfDoc;
  const approxPageHeight = 792 * scale;

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
            <LazyPage pdfDocReady={pdfDocReady} estimatedHeight={approxPageHeight}>
              {(visible) => (
                <div ref={el => { if (pageRefs) pageRefs.current[i] = el; }}>
                  {visible && (
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
                </div>
              )}
            </LazyPage>
          </PageErrorBoundary>
        ))
      )}
    </div>
  );
}