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
  onActivePageChange?: (pageIndex: number) => void;
}

// ── LazyPage ──────────────────────────────────────────────────────────────────
interface LazyPageProps {
  pdfDocReady:   boolean;
  estimatedHeight: number;
  forceVisible:  boolean;
  outerRef?:     React.Ref<HTMLDivElement>;
  children:      (visible: boolean) => React.ReactNode;
}

function LazyPage({ pdfDocReady, estimatedHeight, forceVisible, outerRef, children }: LazyPageProps) {
  const sentinelRef = useRef<HTMLDivElement>(null);
  const [triggered, setTriggered] = useState(false);
  const [visible,   setVisible]   = useState(false);

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

  useEffect(() => {
    if (forceVisible) setTriggered(true);
  }, [forceVisible]);

  useEffect(() => {
    if (triggered && pdfDocReady) setVisible(true);
  }, [triggered, pdfDocReady]);

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
  onActivePageChange,
}, ref) {
  const { theme: t } = useTheme();
  const pdfDocReady      = !!pdfDoc;
  const approxPageHeight = 792 * scale;

  const [forcedPages, setForcedPages] = useState<Set<number>>(new Set());

  useImperativeHandle(ref, () => ({
    jumpToPage: (index: number) => {
      if (!pdfDocReady) return;

      const alreadyRendered = forcedPages.has(index);

      setForcedPages(prev => {
        if (prev.has(index)) return prev;
        const next = new Set(prev);
        next.add(index);
        return next;
      });

      const delay = alreadyRendered ? 0 : 300;

      setTimeout(() => {
        const el = pageRefs?.current[index];
        const container = canvasScrollRef?.current;
        if (!el || !container) return;

        const elRect        = el.getBoundingClientRect();
        const containerRect = container.getBoundingClientRect();
        const scrollTarget  = container.scrollTop + elRect.top - containerRect.top;

        container.scrollTop = Math.max(0, scrollTarget);
      }, delay);
    },
  }), [pdfDocReady, pageRefs, canvasScrollRef, forcedPages]);

  useEffect(() => { setForcedPages(new Set()); }, [sessionId]);

  // ── Per-Session Semantic Scroll Anchoring ───────────────────────────────
  type ScrollState = { index: number; offset: number };
  const scrollPositions   = useRef<Record<string, ScrollState>>({});
  const lastActiveRef     = useRef<number>(-1);
  const isRestoringScroll = useRef<boolean>(false); 

  // 1. Restore semantic scroll position when switching tabs
  useEffect(() => {
    const container = canvasScrollRef?.current;
    if (!container || !pageRefs?.current) return;

    isRestoringScroll.current = true;
    const pos = scrollPositions.current[sessionId];

    if (!pos) {
      container.scrollTop = 0;
      const timer = setTimeout(() => { isRestoringScroll.current = false; }, 50);
      return () => clearTimeout(timer);
    }

    // Force the target page to bypass LazyPage observer so it gets actual height ASAP
    setForcedPages(prev => {
      if (prev.has(pos.index)) return prev;
      const next = new Set(prev);
      next.add(pos.index);
      return next;
    });

    const anchorScroll = () => {
      const el = pageRefs.current?.[pos.index];
      if (!el) return;
      
      const elRect = el.getBoundingClientRect();
      const containerRect = container.getBoundingClientRect();
      
      // Calculate how far the top of the page is from the top of the container
      const currentOffset = elRect.top - containerRect.top;
      const diff = currentOffset - pos.offset;
      
      // If the page has shifted from its saved relative position, adjust the scroll
      if (Math.abs(diff) > 1) {
        container.scrollTop += diff;
      }
    };

    anchorScroll();
    
    // As LazyPages spin up, the DOM shifts. We use ResizeObserver to re-anchor 
    // the target page firmly in place until things settle.
    const resizeObserver = new ResizeObserver(() => {
      anchorScroll();
    });

    if (container.firstElementChild) {
      resizeObserver.observe(container.firstElementChild);
    }

    const timer = setTimeout(() => {
      resizeObserver.disconnect();
      // Give passive scroll events an extra tick to clear out before unlocking
      setTimeout(() => {
        isRestoringScroll.current = false;
      }, 50);
    }, 400);

    return () => {
      resizeObserver.disconnect();
      clearTimeout(timer);
      isRestoringScroll.current = false;
    };
  }, [sessionId, canvasScrollRef, pageRefs]);

  // 2. Track scroll continuously to update active page & save scroll position
  useEffect(() => {
    const container = canvasScrollRef?.current;
    if (!container || !pageRefs?.current || !onActivePageChange) return;

    let ticking = false;

    const handleScroll = () => {
      // Ignore transient scroll events generated during tab transitions
      if (isRestoringScroll.current) return;

      if (!ticking) {
        window.requestAnimationFrame(() => {
          if (isRestoringScroll.current) {
            ticking = false;
            return;
          }

          const containerRect = container.getBoundingClientRect();
          const targetY = containerRect.top + containerRect.height / 3;

          let bestIndex = -1;
          let minDistance = Infinity;

          for (let i = 0; i < pageRefs.current.length; i++) {
            const el = pageRefs.current[i];
            if (!el) continue;
            
            const rect = el.getBoundingClientRect();

            if (rect.top <= targetY && rect.bottom >= targetY) {
               bestIndex = i;
               break;
            }

            const dist = Math.abs(rect.top - targetY);
            if (dist < minDistance) {
              minDistance = dist;
              bestIndex = i;
            }
          }

          if (bestIndex !== -1) {
            // Save semantic offset: exactly where the active page is on screen
            const activeEl = pageRefs.current[bestIndex];
            if (activeEl) {
              const activeRect = activeEl.getBoundingClientRect();
              const offset = activeRect.top - containerRect.top;
              scrollPositions.current[sessionId] = { index: bestIndex, offset };
            }

            // Report the new active page to the app if it changed
            if (bestIndex !== lastActiveRef.current) {
              lastActiveRef.current = bestIndex;
              onActivePageChange(bestIndex);
            }
          }
          ticking = false;
        });
        ticking = true;
      }
    };

    container.addEventListener('scroll', handleScroll, { passive: true });
    
    if (!isRestoringScroll.current) handleScroll();

    return () => container.removeEventListener('scroll', handleScroll);
  }, [canvasScrollRef, pageRefs, onActivePageChange, sessionId, documentState?.children?.length]);

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