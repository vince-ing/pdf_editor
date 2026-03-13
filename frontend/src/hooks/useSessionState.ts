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
  // pageRefs is no longer used here but kept in args if needed elsewhere
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

  // REMOVED: The IntersectionObserver that used to fight with Canvas.tsx 
  // over setting the activePage.

  return {
    documentState, pdfDoc, activePage, scale,
    setActivePage, setScale,
    refreshDocumentState,
  };
}