// frontend/src/hooks/useSessionState.ts
import { useCallback, useEffect } from 'react';
import { engineApi } from '../api/client';
import type { DocumentState } from '../components/canvas/types';
import type { TabSession } from './useTabManager';

interface UseSessionStateArgs {
  activeTabId:  string | null;
  activeSession: TabSession | null;
  patchSession: (tabId: string, patch: Partial<TabSession>) => void;
  pageRefs:     React.MutableRefObject<(HTMLDivElement | null)[]>;
}

export function useSessionState({
  activeTabId,
  activeSession,
  patchSession,
  pageRefs,
}: UseSessionStateArgs) {

  // Convenient derived values from the active session
  const documentState = activeSession?.documentState ?? null;
  const pdfDoc        = activeSession?.pdfDoc        ?? null;
  const activePage    = activeSession?.activePage    ?? 0;
  const scale         = activeSession?.scale         ?? 1.0;

  const setActivePage = useCallback((page: number) => {
    if (activeTabId) patchSession(activeTabId, { activePage: page });
  }, [activeTabId, patchSession]);

  const setScale = useCallback((updater: number | ((prev: number) => number)) => {
    if (!activeTabId) return;
    const cur = activeSession?.scale ?? 1.0;
    const next = typeof updater === 'function' ? updater(cur) : updater;
    patchSession(activeTabId, { scale: next });
  }, [activeTabId, activeSession?.scale, patchSession]);

  const refreshDocumentState = useCallback(async () => {
    if (!activeTabId) return;
    try {
      const documentState = await engineApi.getDocumentState(activeTabId);
      if (documentState) {
        patchSession(activeTabId, { documentState });
      }
    } catch (e) {
      console.error('[useSessionState] refresh failed:', e);
    }
  }, [activeTabId, patchSession]);

  // IntersectionObserver — update activePage as user scrolls.
  //
  // We depend on `documentState?.children` (the page list) rather than just
  // `pdfDoc` so that the observers are rebuilt whenever pages are added,
  // removed or reordered. Without this, the observer set would reference
  // stale DOM nodes (or miss new pages) after any page-level mutation.
  const pageCount = documentState?.children?.length ?? 0;

  useEffect(() => {
    if (!documentState || !activeTabId) return;
    const observers: IntersectionObserver[] = [];

    pageRefs.current.forEach((el, i) => {
      if (!el) return;
      const obs = new IntersectionObserver(
        ([entry]) => { if (entry.isIntersecting) patchSession(activeTabId, { activePage: i }); },
        { threshold: 0.4 },
      );
      obs.observe(el);
      observers.push(obs);
    });

    return () => observers.forEach(o => o.disconnect());

  // pageCount drives re-observation after page add/remove/reorder.
  // pdfDoc still triggers re-observation when a new document loads.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pdfDoc, activeTabId, pageCount, patchSession]);

  return {
    documentState, pdfDoc, activePage, scale,
    setActivePage, setScale,
    refreshDocumentState,
  };
}