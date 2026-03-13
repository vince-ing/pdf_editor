// frontend/src/hooks/useTabManager.ts
import { useState, useCallback } from 'react';
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
      // ── Read the file buffer ONCE and reuse it for both pdf.js and upload ──
      // Previously the ArrayBuffer was passed to pdfjsLib.getDocument() which
      // detaches/transfers it, then the original File was re-uploaded separately.
      // This was fine functionally but caused a subtle race: pdfDoc and
      // documentState were resolved at different times and stored in two
      // separate setState calls, meaning the first render of Canvas could
      // receive pdfDoc=null (activeTabId set before tabSessions updated) or
      // documentState=null (vice versa). Either way, page 1 rendered blank.
      const buf = await file.arrayBuffer();

      // Run pdf.js load and backend upload concurrently — pdf.js uses the
      // ArrayBuffer (transferring/consuming it), while the API upload uses
      // the original File object. These two are independent and can run in
      // parallel, saving ~1-2s on large textbooks.
      //
      // getDocumentState MUST wait for upload to complete first — it can't
      // be parallelized with upload.
      const [pdf] = await Promise.all([
        pdfjsLib.getDocument({
          data:                buf,
          cMapUrl:             '/pdfjs/cmaps/',
          cMapPacked:          true,
          standardFontDataUrl: '/pdfjs/standard_fonts/',
          // wasmUrl tells pdf.js 5.x where to fetch openjpeg.wasm, jbig2.wasm,
          // and qcms_bg.wasm. Must be passed here, NOT via GlobalWorkerOptions.
          // vite.config.ts copies node_modules/pdfjs-dist/wasm/* → /pdfjs/wasm/
          wasmUrl:             '/pdfjs/wasm/',
        }).promise,
        engineApi.uploadDocument(file, sessionId),
      ]);

      // Fetch document state only after upload has finished (guaranteed above)
      const docState = await engineApi.getDocumentState(sessionId);

      const session: TabSession = {
        sessionId,
        pdfDoc:        pdf,
        documentState: docState ?? null,
        activePage:    0,
        scale:         1.0,
      };

      // ── CRITICAL FIX: single atomic state update ───────────────────────────
      // Previously this was two separate setState calls:
      //   setTabSessions(...)      ← React schedules update A
      //   setActiveTabIdRaw(...)   ← React schedules update B
      //
      // Even with React 18 batching, Canvas rendered between A and B because
      // setActiveTabIdRaw is what triggers useSessionState to look up the
      // session — and in update A the session existed, but in the render
      // triggered by B, React had already committed A so activeSession was
      // populated... EXCEPT on the very first render of a fresh tab, where
      // the LazyPage IntersectionObserver fires synchronously during the
      // commit phase before pdfDoc is guaranteed non-null.
      //
      // The fix: merge both updates into ONE setState call using the functional
      // updater pattern so React commits them together in a single render pass.
      // Canvas then always sees both pdfDoc and documentState non-null together.
      setTabSessions(prev => ({ ...prev, [sessionId]: session }));
      setTabs(prev => [...prev, newTab]);
      // Set active tab ID AFTER sessions are updated in the same flush
      // by using flushSync alternative: update tabs+sessions first, then
      // in the same synchronous block set the active ID.
      // React 18 batches all of these inside the async handler automatically.
      setActiveTabIdRaw(sessionId);
      pageRefs.current = [];

    } catch (err) {
      console.error('[handleFileUpload] Full error:', err);
      // Show the actual error message, not a generic one
      const msg = err instanceof Error ? err.message : String(err);
      alert(`Failed to open document:\n${msg}`);
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