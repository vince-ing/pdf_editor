// app/App.tsx — Root layout.
// RightPanel now receives activeTool so it can auto-expand the right section.

import { useState, useEffect, useCallback, useRef } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.mjs?url';
import { engineApi } from '../api/client';
import { useTts } from '../hooks/useTts';
import { buildMenuDefs } from '../constants/menuDefs';

import { TopBar }      from '../components/layout/TopBar';
import { LeftSidebar } from '../components/layout/LeftSidebar';
import { RightPanel }  from '../components/layout/RightPanel';
import { TtsBar }      from '../components/layout/TtsBar';
import { StatusBar }   from '../components/layout/StatusBar';
import { Toolbar }     from '../components/toolbar/Toolbar';
import { Canvas }      from '../components/canvas/Canvas';

import type { ToolId } from '../constants/tools';
import type { SidebarView } from '../components/layout/LeftSidebar';
import type { FileTab } from '../components/layout/TopBar';

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

interface PageNode {
  id: string;
  page_number?: number;
  rotation?: number;
  metadata?: { width: number; height: number };
  crop_box?: { x: number; y: number; width: number; height: number };
  children?: unknown[];
}

interface DocumentState {
  node_type: string;
  file_name: string;
  file_size?: number;
  children?: PageNode[];
}

export default function App() {
  const [documentState,    setDocumentState]    = useState<DocumentState | null>(null);
  const [pdfDoc,           setPdfDoc]           = useState<pdfjsLib.PDFDocumentProxy | null>(null);
  const [loading,          setLoading]          = useState(false);
  const [scale,            setScale]            = useState(1.0);
  const [activeTool,       setActiveTool]       = useState<ToolId>('hand');
  const [activePage,       setActivePage]       = useState(0);
  const [sidebarView,      setSidebarView]      = useState<SidebarView>('pages');
  const [showThumbnails,   setShowThumbnails]   = useState(true);
  const [rightPanelOpen,   setRightPanelOpen]   = useState(true);
  const [lastSelectedText, setLastSelectedText] = useState('');
  const [tabs,             setTabs]             = useState<FileTab[]>([]);
  const [activeTabId,      setActiveTabId]      = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const pageRefs     = useRef<(HTMLDivElement | null)[]>([]);
  const { tts, speak, stop: ttsStop, pauseResume, setSpeed } = useTts();

  const refreshDocumentState = useCallback(async () => {
    try {
      const data = await engineApi.getDocumentState();
      if (data?.node_type === 'document') setDocumentState(data);
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

  const openFileDialog = () => fileInputRef.current?.click();

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
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
  };

  const handleExportPdf = async () => {
    if (!documentState) return;
    try {
      const res = await fetch('http://localhost:8000/api/document/download');
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = Object.assign(document.createElement('a'), {
        href: url, download: `edited_${documentState.file_name}`,
      });
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: unknown) { alert('Export failed: ' + (err as Error).message); }
  };

  const handleUndo = async () => { try { await engineApi.undo(); await refreshDocumentState(); } catch { alert('Nothing to undo!'); } };
  const handleRedo = async () => { try { await engineApi.redo(); await refreshDocumentState(); } catch { alert('Nothing to redo!'); } };

  const handleReadPage = useCallback(async () => {
    if (!documentState || !pdfDoc) return alert('Open a document first.');
    const pageNode = documentState.children?.[activePage];
    if (!pageNode) return;
    try {
      const chars = await engineApi.getPageChars(pageNode.id);
      const text = chars.map((c: { text: string }) => c.text).join('');
      if (!text.trim()) return alert('No readable text found. Try OCR first.');
      await speak(text, `Reading page ${activePage + 1}`);
    } catch (err: unknown) { alert('TTS failed: ' + (err as Error).message); }
  }, [documentState, pdfDoc, activePage, speak]);

  const handleReadSelection = useCallback(async () => {
    if (!lastSelectedText?.trim()) return alert('Select text first using the Select tool.');
    await speak(lastSelectedText.trim(), 'Reading selection');
  }, [lastSelectedText, speak]);

  const zoomIn    = () => setScale(s => Math.min(+(s + 0.25).toFixed(2), 4.0));
  const zoomOut   = () => setScale(s => Math.max(+(s - 0.25).toFixed(2), 0.25));
  const zoomReset = () => setScale(1.0);

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
  });

  const menus = buildMenuDefs({
    openFileDialog, handleExportPdf, handleUndo, handleRedo,
    handleReadPage, handleReadSelection, ttsStop,
    setShowThumbnails, setRightPanelOpen,
    zoomIn, zoomOut, zoomReset, documentState,
  });

  const pageCount = documentState?.children?.length ?? 0;

  if (loading) {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-[#1e2327] gap-3">
        <div className="w-9 h-9 border-2 border-[#2d3338] border-t-[#4a90e2] rounded-full animate-spin-slow" />
        <span className="text-sm text-gray-400">Loading document…</span>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-[#1e2327] text-white overflow-hidden">

      <TopBar
        tabs={tabs}
        activeTabId={activeTabId}
        onTabClick={setActiveTabId}
        onTabClose={id => {
          setTabs(prev => prev.filter(x => x.id !== id));
          if (activeTabId === id) {
            setActiveTabId(null);
            setDocumentState(null);
            setPdfDoc(null);
          }
        }}
        onNewTab={openFileDialog}
        onUndo={handleUndo}
        onRedo={handleRedo}
        menus={menus}
      />

      <div className="flex-1 flex overflow-hidden min-h-0">

        <LeftSidebar
          showThumbnails={showThumbnails}
          onToggleThumbnails={() => setShowThumbnails(v => !v)}
          pdfDoc={pdfDoc}
          documentState={documentState}
          activePage={activePage}
          activeView={sidebarView}
          onViewChange={v => { setSidebarView(v); if (v) setShowThumbnails(true); }}
          onPageClick={i => {
            setActivePage(i);
            pageRefs.current[i]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }}
          onDocumentChanged={refreshDocumentState}
        />

        <div className="flex-1 flex flex-col overflow-hidden min-w-0">
          <Toolbar
            activeTool={activeTool}
            onToolChange={setActiveTool}
            scale={scale}
            onZoomIn={zoomIn}
            onZoomOut={zoomOut}
            onZoomReset={zoomReset}
            onUndo={handleUndo}
            onRedo={handleRedo}
            onReadPage={handleReadPage}
            onReadSelection={handleReadSelection}
            hasSelection={!!lastSelectedText}
            ttsActive={tts.visible}
            pageInfo={documentState ? { current: activePage + 1, total: pageCount } : null}
          />

          <div className="flex-1 flex overflow-hidden min-h-0">
            <Canvas
              pdfDoc={pdfDoc}
              documentState={documentState}
              activeTool={activeTool}
              scale={scale}
              onAnnotationAdded={refreshDocumentState}
              onDocumentChanged={refreshDocumentState}
              onTextSelected={setLastSelectedText}
              pageRefs={pageRefs}
            />
            {rightPanelOpen && (
              <RightPanel
                documentState={documentState}
                activePage={activePage}
                activeTool={activeTool}
              />
            )}
          </div>
        </div>
      </div>

      <TtsBar
        visible={tts.visible}
        status={tts.status}
        phase={tts.phase}
        progress={tts.progress}
        isPaused={tts.isPaused}
        speed={tts.speed}
        onStop={ttsStop}
        onPauseResume={pauseResume}
        onSpeedChange={setSpeed}
      />

      <StatusBar
        activeTool={activeTool}
        scale={scale}
        activePage={activePage}
        pageCount={pageCount}
        lastSelectedText={lastSelectedText}
        documentState={documentState}
      />

      <input ref={fileInputRef} type="file" accept="application/pdf"
        className="hidden" onChange={handleFileUpload} />
    </div>
  );
}