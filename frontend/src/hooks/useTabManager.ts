// frontend/src/hooks/useTabManager.ts
import { useState, useCallback, useRef } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import { engineApi } from '../api/client';
import type { FileTab } from '../components/layout/TopBar';
import type { DocumentState } from '../components/canvas/types';

export interface TabSession {
  sessionId:     string;
  pdfDoc:        pdfjsLib.PDFDocumentProxy | null;
  documentState: DocumentState | null;
  activePage:    number;
  scale:         number;
}

export function makeSession(sessionId: string): TabSession {
  return { sessionId, pdfDoc: null, documentState: null, activePage: 0, scale: 1.0 };
}

export function useTabManager(
  fileInputRef: React.RefObject<HTMLInputElement>,
  pageRefs: React.MutableRefObject<(HTMLDivElement | null)[]>,
) {
  const [tabs,          setTabs]          = useState<FileTab[]>([]);
  const [activeTabId,   setActiveTabIdRaw] = useState<string | null>(null);
  const [tabSessions,   setTabSessions]   = useState<Record<string, TabSession>>({});
  const [loading,       setLoading]       = useState(false);

  const openFileDialog = useCallback(() => {
    fileInputRef.current?.click();
  }, [fileInputRef]);

  const setActiveTabId = useCallback((id: string | null) => {
    setActiveTabIdRaw(id);
    pageRefs.current = [];
  }, [pageRefs]);

  const handleFileUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);

    const sessionId = `${file.name}-${Date.now()}`;
    const newTab: FileTab = { id: sessionId, name: file.name, fullName: file.name, modified: false };

    try {
      const buf = await file.arrayBuffer();
      const pdf = await pdfjsLib.getDocument({ data: buf }).promise;

      await engineApi.uploadDocument(file, sessionId);
      // getDocumentState already normalizes — returns DocumentState | null
      const documentState = await engineApi.getDocumentState(sessionId);

      const session: TabSession = {
        sessionId,
        pdfDoc:        pdf,
        documentState: documentState ?? null,
        activePage:    0,
        scale:         1.0,
      };

      setTabSessions(prev => ({ ...prev, [sessionId]: session }));
      setTabs(prev => [...prev, newTab]);
      setActiveTabIdRaw(sessionId);
      pageRefs.current = [];
    } catch (err) {
      console.error(err);
      alert('Failed to open document.');
    } finally {
      setLoading(false);
      e.target.value = '';
    }
  }, [pageRefs]);

  const handleTabClose = useCallback(async (id: string) => {
    try { await engineApi.closeSession(id); } catch { /* ignore */ }

    setTabs(prev => {
      const remaining = prev.filter(x => x.id !== id);
      setActiveTabIdRaw(cur => {
        if (cur !== id) return cur;
        const idx = prev.findIndex(x => x.id === id);
        const next = remaining[Math.min(idx, remaining.length - 1)];
        pageRefs.current = [];
        return next?.id ?? null;
      });
      return remaining;
    });

    setTabSessions(prev => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  }, [pageRefs]);

  const patchSession = useCallback((tabId: string, patch: Partial<TabSession>) => {
    setTabSessions(prev => ({
      ...prev,
      [tabId]: { ...prev[tabId], ...patch },
    }));
  }, []);

  const activeSession = activeTabId ? (tabSessions[activeTabId] ?? null) : null;

  return {
    tabs, setTabs,
    activeTabId, setActiveTabId,
    activeSession, tabSessions,
    loading,
    openFileDialog, handleFileUpload, handleTabClose,
    patchSession,
  };
}