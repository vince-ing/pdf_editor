// frontend/src/hooks/useEditorState.ts
import { useState, useEffect, useCallback, useRef } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import { engineApi } from '../api/client';
import { useTts } from './useTts';
import { buildMenuDefs } from '../constants/menuDefs';
import { DEFAULT_TEXT_PROPS, type TextProps } from '../types/textProps';
import { toolManager } from '../core/tools/ToolManager';

import type { ToolId } from '../constants/tools';
import type { SidebarView } from '../components/layout/LeftSidebar';
import type { FileTab } from '../components/layout/TopBar';
import type { DocumentState } from '../components/canvas/types';

export function useEditorState() {
  const [documentState,      setDocumentState]    = useState<DocumentState | null>(null);
  const [pdfDoc,             setPdfDoc]           = useState<pdfjsLib.PDFDocumentProxy | null>(null);
  const [loading,            setLoading]          = useState(false);
  const [scale,              setScale]            = useState(1.0);
  const [activeTool,         setActiveToolState]  = useState<ToolId>('hand');
  const [activePage,         setActivePage]       = useState(0);
  const [sidebarView,        setSidebarView]      = useState<SidebarView>('pages');
  const [showThumbnails,     setShowThumbnails]   = useState(true);
  const [rightPanelOpen,     setRightPanelOpen]   = useState(true);
  const [lastSelectedText,   setLastSelectedText] = useState('');
  const [tabs,               setTabs]             = useState<FileTab[]>([]);
  const [activeTabId,        setActiveTabId]      = useState<string | null>(null);
  const [textProps,          setTextProps]        = useState<TextProps>(DEFAULT_TEXT_PROPS);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const pageRefs     = useRef<(HTMLDivElement | null)[]>([]);
  const { tts, speak, stop: ttsStop, pauseResume, setSpeed } = useTts();

  // Keep React state and Strategy Pattern state perfectly synced
  const setActiveTool = useCallback((id: ToolId) => {
    setActiveToolState(id);
    toolManager.setActiveTool(id);
  }, []);

  const refreshDocumentState = useCallback(async () => {
    try {
      const data = await engineApi.getDocumentState();
      if ((data as any)?.node_type === 'document') setDocumentState(data as DocumentState);
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => { refreshDocumentState(); }, [refreshDocumentState]);

  useEffect(() => {
    if (!documentState) return;
    const observers: IntersectionObserver[] = [];
    pageRefs.current.forEach((el, i) => {
      if (!el) return;
      const obs = new IntersectionObserver(
        ([e]) => { if (e.isIntersecting) setActivePage(i); },
        { threshold: 0.4 },
      );
      obs.observe(el);
      observers.push(obs);
    });
    return () => observers.forEach(o => o.disconnect());
  }, [documentState, pdfDoc]);

  const openFileDialog = useCallback(() => fileInputRef.current?.click(), []);

  const handleFileUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    try {
      const buf = await file.arrayBuffer();
      const pdf = await pdfjsLib.getDocument({ data: buf }).promise;
      setPdfDoc(pdf);
      await engineApi.uploadDocument(file);
      await refreshDocumentState();
      setActivePage(0);
      const id = file.name;
      setTabs(prev => prev.find(x => x.id === id) ? prev : [...prev, { id, name: file.name, fullName: file.name, modified: false }]);
      setActiveTabId(id);
    } catch (err) {
      console.error(err);
      alert('Failed to open document.');
    } finally {
      setLoading(false);
      e.target.value = '';
    }
  }, [refreshDocumentState]);

  const handleExportPdf = useCallback(async () => {
    if (!documentState) return;
    try {
      const res = await fetch('http://localhost:8000/api/document/download');
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = Object.assign(document.createElement('a'), { href: url, download: `edited_${documentState.file_name}` });
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) { alert('Export failed: ' + err.message); }
  }, [documentState]);

  const handleUndo = useCallback(async () => { try { await engineApi.undo(); await refreshDocumentState(); } catch { alert('Nothing to undo!'); } }, [refreshDocumentState]);
  const handleRedo = useCallback(async () => { try { await engineApi.redo(); await refreshDocumentState(); } catch { alert('Nothing to redo!'); } }, [refreshDocumentState]);

  const handleReadPage = useCallback(async () => {
    if (!documentState || !pdfDoc) return alert('Open a document first.');
    const pageNode = documentState.children?.[activePage];
    if (!pageNode) return;
    try {
      const chars = await engineApi.getPageChars(pageNode.id);
      const text = chars.map((c: { text: string }) => c.text).join('');
      if (!text.trim()) return alert('No readable text found. Try OCR first.');
      await speak(text, `Reading page ${activePage + 1}`);
    } catch (err: any) { alert('TTS failed: ' + err.message); }
  }, [documentState, pdfDoc, activePage, speak]);

  const handleReadSelection = useCallback(async () => {
    if (!lastSelectedText?.trim()) return alert('Select text first using the Select tool.');
    await speak(lastSelectedText.trim(), 'Reading selection');
  }, [lastSelectedText, speak]);

  const zoomIn    = useCallback(() => setScale(s => Math.min(+(s + 0.25).toFixed(2), 4.0)), []);
  const zoomOut   = useCallback(() => setScale(s => Math.max(+(s - 0.25).toFixed(2), 0.25)), []);
  const zoomReset = useCallback(() => setScale(1.0), []);

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

  const menus = buildMenuDefs({
    openFileDialog, handleExportPdf, handleUndo, handleRedo,
    handleReadPage, handleReadSelection, ttsStop,
    setShowThumbnails, setRightPanelOpen,
    zoomIn, zoomOut, zoomReset, documentState,
  });

  const pageCount = documentState?.children?.length ?? 0;

  return {
    documentState, setDocumentState,
    pdfDoc, setPdfDoc,
    loading,
    scale,
    activeTool, setActiveTool,
    activePage, setActivePage,
    sidebarView, setSidebarView,
    showThumbnails, setShowThumbnails,
    rightPanelOpen, setRightPanelOpen,
    lastSelectedText, setLastSelectedText,
    tabs, setTabs,
    activeTabId, setActiveTabId,
    textProps, setTextProps,
    fileInputRef, pageRefs,
    tts, ttsStop, pauseResume, setSpeed,
    handleFileUpload, handleUndo, handleRedo, handleReadPage, handleReadSelection,
    zoomIn, zoomOut, zoomReset, openFileDialog,
    refreshDocumentState,
    menus, pageCount
  };
}