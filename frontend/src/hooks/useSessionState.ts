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
    // Read the current scale from the session to avoid stale closure
    // patchSession uses functional setState internally so this is safe
    const cur = activeSession?.scale ?? 1.0;
    const next = typeof updater === 'function' ? updater(cur) : updater;
    patchSession(activeTabId, { scale: next });
  }, [activeTabId, activeSession?.scale, patchSession]);

  const refreshDocumentState = useCallback(async () => {
    if (!activeTabId) return;
    try {
      const data = await engineApi.getDocumentState(activeTabId);
      if ((data as any)?.node_type === 'document') {
        patchSession(activeTabId, { documentState: data as DocumentState });
      }
    } catch (e) {
      console.error('[useSessionState] refresh failed:', e);
    }
  }, [activeTabId, patchSession]);

  // IntersectionObserver — update activePage as user scrolls
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
  }, [pdfDoc, activeTabId, patchSession]);
  // Note: pdfDoc in deps intentionally triggers re-observation when a new doc loads

  return {
    documentState, pdfDoc, activePage, scale,
    setActivePage, setScale,
    refreshDocumentState,
  };
}