// frontend/src/hooks/useEditorState.ts
import { useState, useEffect, useCallback, useRef } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import { engineApi } from '../api/client';
import { useTts } from './useTts';
import { buildMenuDefs } from '../constants/menuDefs';
import { DEFAULT_TEXT_PROPS, type TextProps } from '../types/textProps';
import { toolManager } from '../core/tools/ToolManager';
import { useTheme } from '../theme';  // ← NEW
import { THEMES, type ThemeId } from '../theme/themes';  // ← NEW

import type { ToolId } from '../constants/tools';
import type { SidebarView } from '../components/layout/LeftSidebar';
import type { FileTab } from '../components/layout/TopBar';
import type { DocumentState } from '../components/canvas/types';

// ── Per-tab session state ─────────────────────────────────────────────────────

interface TabSession {
  sessionId: string;
  pdfDoc:    pdfjsLib.PDFDocumentProxy | null;
  documentState: DocumentState | null;
  activePage: number;
  scale: number;
}

function makeSession(sessionId: string): TabSession {
  return { sessionId, pdfDoc: null, documentState: null, activePage: 0, scale: 1.0 };
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useEditorState() {
  // Tab list
  const [tabs,        setTabs]        = useState<FileTab[]>([]);
  const [activeTabId, setActiveTabIdRaw] = useState<string | null>(null);

  // Per-tab sessions map
  const [tabSessions, setTabSessions] = useState<Record<string, TabSession>>({});

  // Shared UI state (not per-tab)
  const [activeTool,       setActiveToolState]  = useState<ToolId>('hand');
  const [sidebarView,      setSidebarView]      = useState<SidebarView>('pages');
  const [showThumbnails,   setShowThumbnails]   = useState(true);
  const [rightPanelOpen,   setRightPanelOpen]   = useState(true);
  const [lastSelectedText, setLastSelectedText] = useState('');
  const [textProps,        setTextProps]        = useState<TextProps>(DEFAULT_TEXT_PROPS);
  const [highlightColor,   setHighlightColor]   = useState('#f59e0b');
  const [highlightOpacity, setHighlightOpacity] = useState(0.45);
  const [loading,          setLoading]          = useState(false);

  // ── Theme ─────────────────────────────────────────────────────────────────
  const { themeId, setTheme } = useTheme();  // ← NEW

  const fileInputRef = useRef<HTMLInputElement>(null);
  const pageRefs     = useRef<(HTMLDivElement | null)[]>([]);
  const { tts, speak, stop: ttsStop, pauseResume, setSpeed } = useTts();

  // ── Active session helpers ──────────────────────────────────────────────────

  const activeSession: TabSession | null = activeTabId ? (tabSessions[activeTabId] ?? null) : null;

  const patchSession = useCallback((tabId: string, patch: Partial<TabSession>) => {
    setTabSessions(prev => ({
      ...prev,
      [tabId]: { ...prev[tabId], ...patch },
    }));
  }, []);

  const documentState = activeSession?.documentState ?? null;
  const pdfDoc        = activeSession?.pdfDoc        ?? null;
  const activePage    = activeSession?.activePage    ?? 0;
  const scale         = activeSession?.scale         ?? 1.0;

  const setDocumentState = useCallback((ds: DocumentState | null) => {
    if (activeTabId) patchSession(activeTabId, { documentState: ds });
  }, [activeTabId, patchSession]);

  const setPdfDoc = useCallback((doc: pdfjsLib.PDFDocumentProxy | null) => {
    if (activeTabId) patchSession(activeTabId, { pdfDoc: doc });
  }, [activeTabId, patchSession]);

  const setActivePage = useCallback((page: number) => {
    if (activeTabId) patchSession(activeTabId, { activePage: page });
  }, [activeTabId, patchSession]);

  const setScale = useCallback((updater: number | ((prev: number) => number)) => {
    if (!activeTabId) return;
    setTabSessions(prev => {
      const cur = prev[activeTabId]?.scale ?? 1.0;
      const next = typeof updater === 'function' ? updater(cur) : updater;
      return { ...prev, [activeTabId]: { ...prev[activeTabId], scale: next } };
    });
  }, [activeTabId]);

  // ── Tab switching ───────────────────────────────────────────────────────────

  const setActiveTabId = useCallback((id: string | null) => {
    setActiveTabIdRaw(id);
    pageRefs.current = [];
  }, []);

  // ── Tool sync ───────────────────────────────────────────────────────────────

  const setActiveTool = useCallback((id: ToolId) => {
    setActiveToolState(id);
    toolManager.setActiveTool(id);
  }, []);

  // ── Refresh document state for active tab ──────────────────────────────────

  const refreshDocumentState = useCallback(async () => {
    if (!activeTabId) return;
    try {
      const data = await engineApi.getDocumentState(activeTabId);
      if ((data as any)?.node_type === 'document') {
        patchSession(activeTabId, { documentState: data as DocumentState });
      }
    } catch (e) { console.error(e); }
  }, [activeTabId, patchSession]);

  // ── IntersectionObserver ───────────────────────────────────────────────────

  useEffect(() => {
    if (!documentState || !activeTabId) return;
    const observers: IntersectionObserver[] = [];
    pageRefs.current.forEach((el, i) => {
      if (!el) return;
      const obs = new IntersectionObserver(
        ([e]) => { if (e.isIntersecting) patchSession(activeTabId, { activePage: i }); },
        { threshold: 0.4 },
      );
      obs.observe(el);
      observers.push(obs);
    });
    return () => observers.forEach(o => o.disconnect());
  }, [pdfDoc, activeTabId, patchSession]);

  // ── File upload ─────────────────────────────────────────────────────────────

  const openFileDialog = useCallback(() => fileInputRef.current?.click(), []);

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
      const data = await engineApi.getDocumentState(sessionId);

      const session: TabSession = {
        sessionId,
        pdfDoc: pdf,
        documentState: (data as any)?.node_type === 'document' ? (data as DocumentState) : null,
        activePage: 0,
        scale: 1.0,
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
  }, []);

  // ── Tab close ───────────────────────────────────────────────────────────────

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
  }, []);

  // ── Export ──────────────────────────────────────────────────────────────────

  const handleExportPdf = useCallback(async () => {
    if (!documentState || !activeTabId) return;
    try {
      const res = await fetch('http://localhost:8000/api/document/download', {
        headers: { 'X-Session-Id': activeTabId },
      });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = Object.assign(document.createElement('a'), { href: url, download: `edited_${documentState.file_name}` });
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) { alert('Export failed: ' + err.message); }
  }, [documentState, activeTabId]);

  // ── Undo / Redo ─────────────────────────────────────────────────────────────

  const handleUndo = useCallback(async () => {
    if (!activeTabId) return;
    try { await engineApi.undo(activeTabId); await refreshDocumentState(); } catch { alert('Nothing to undo!'); }
  }, [activeTabId, refreshDocumentState]);

  const handleRedo = useCallback(async () => {
    if (!activeTabId) return;
    try { await engineApi.redo(activeTabId); await refreshDocumentState(); } catch { alert('Nothing to redo!'); }
  }, [activeTabId, refreshDocumentState]);

  // ── TTS ─────────────────────────────────────────────────────────────────────

  const handleReadPage = useCallback(async () => {
    if (!documentState || !pdfDoc) return alert('Open a document first.');
    const pageNode = documentState.children?.[activePage];
    if (!pageNode || !activeTabId) return;
    try {
      const chars = await engineApi.getPageChars(pageNode.id, activeTabId);
      const text = chars.map((c: { text: string }) => c.text).join('');
      if (!text.trim()) return alert('No readable text found. Try OCR first.');
      await speak(text, `Reading page ${activePage + 1}`);
    } catch (err: any) { alert('TTS failed: ' + err.message); }
  }, [documentState, pdfDoc, activePage, activeTabId, speak]);

  const handleReadSelection = useCallback(async () => {
    if (!lastSelectedText?.trim()) return alert('Select text first using the Select tool.');
    await speak(lastSelectedText.trim(), 'Reading selection');
  }, [lastSelectedText, speak]);

  // ── Zoom ────────────────────────────────────────────────────────────────────

  const zoomIn    = useCallback(() => setScale(s => Math.min(+(s + 0.25).toFixed(2), 4.0)), [setScale]);
  const zoomOut   = useCallback(() => setScale(s => Math.max(+(s - 0.25).toFixed(2), 0.25)), [setScale]);
  const zoomReset = useCallback(() => setScale(1.0), [setScale]);

  // ── Keyboard shortcuts ──────────────────────────────────────────────────────

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey) {
        if (e.key === 'z') { e.preventDefault(); handleUndo(); }
        if (e.key === 'y') { e.preventDefault(); handleRedo(); }
        if (e.key === 'o') { e.preventDefault(); openFileDialog(); }
        if (e.key === '=') { e.preventDefault(); zoomIn(); }
        if (e.key === '-') { e.preventDefault(); zoomOut(); }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handleUndo, handleRedo, openFileDialog, zoomIn, zoomOut]);

  // ── Menus (theme submenu injected here) ────────────────────────────────────

  const menus = buildMenuDefs({
    openFileDialog, handleExportPdf, handleUndo, handleRedo,
    handleReadPage, handleReadSelection, ttsStop,
    setShowThumbnails, setRightPanelOpen,
    zoomIn, zoomOut, zoomReset, documentState,
    // ↓ NEW — pass theme state into menu builder
    themeId, setTheme,
  });

  const pageCount = documentState?.children?.length ?? 0;

  return {
    // Tab management
    tabs, setTabs,
    activeTabId, setActiveTabId,
    handleTabClose,

    // Active session state
    documentState, setDocumentState,
    pdfDoc, setPdfDoc,
    activePage, setActivePage,
    scale,

    // Shared UI
    loading,
    activeTool, setActiveTool,
    sidebarView, setSidebarView,
    showThumbnails, setShowThumbnails,
    rightPanelOpen, setRightPanelOpen,
    lastSelectedText, setLastSelectedText,
    textProps, setTextProps,
    highlightColor, setHighlightColor,
    highlightOpacity, setHighlightOpacity,

    // Theme — NEW
    themeId, setTheme,

    // Refs
    fileInputRef, pageRefs,

    // TTS
    tts, ttsStop, pauseResume, setSpeed,

    // Actions
    handleFileUpload, handleUndo, handleRedo,
    handleReadPage, handleReadSelection,
    zoomIn, zoomOut, zoomReset, openFileDialog,
    refreshDocumentState,
    menus, pageCount,
  };
}