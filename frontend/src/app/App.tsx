// App.tsx — Root layout. Owns all top-level state.
// Layout: TopBar → [LeftSidebar | Toolbar+Canvas | RightPanel] → TtsBar → StatusBar

import { useState, useEffect, useCallback, useRef } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.mjs?url';
import { engineApi } from '../api/client';
import { useTts } from '../hooks/useTts';
import { TopBar } from "../components/TopBar";
import { LeftSidebar } from "../components/LeftSidebar";
import { Toolbar } from "../components/Toolbar";
import { Canvas } from '../components/Canvas';
import { RightPanel } from '../components/RightPanel';
import { TtsBar } from '../components/TtsBar';
import { StatusBar } from '../components/StatusBar';

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

// ── Types ─────────────────────────────────────────────────────────────────────

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

// ─────────────────────────────────────────────────────────────────────────────

export default function App() {
  // ── State ──────────────────────────────────────────────────────────────────
  const [documentState,  setDocumentState]  = useState<DocumentState | null>(null);
  const [pdfDoc,         setPdfDoc]         = useState<pdfjsLib.PDFDocumentProxy | null>(null);
  const [loading,        setLoading]        = useState(false);
  const [scale,          setScale]          = useState(1.5);
  const [activeTool,     setActiveTool]     = useState<ToolId>('hand');
  const [activePage,     setActivePage]     = useState(0);
  const [sidebarView,    setSidebarView]    = useState<SidebarView>('pages');
  const [showThumbnails, setShowThumbnails] = useState(true);
  const [rightPanelOpen, setRightPanelOpen] = useState(true);
  const [lastSelectedText, setLastSelectedText] = useState('');
  const [tabs,    setTabs]    = useState<FileTab[]>([]);
  const [activeTabId, setActiveTabId] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const pageRefs     = useRef<(HTMLDivElement | null)[]>([]);
  const { tts, speak, stop: ttsStop, pauseResume, setSpeed } = useTts();

  // ── Document state ─────────────────────────────────────────────────────────
  const refreshDocumentState = useCallback(async () => {
    try {
      const data = await engineApi.getDocumentState();
      if (data?.node_type === 'document') setDocumentState(data);
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => { refreshDocumentState(); }, [refreshDocumentState]);

  // ── Intersection observer for active page ──────────────────────────────────
  useEffect(() => {
    if (!documentState) return;
    const observers: IntersectionObserver[] = [];
    pageRefs.current.forEach((el, i) => {
      if (!el) return;
      const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setActivePage(i); }, { threshold: 0.4 });
      obs.observe(el);
      observers.push(obs);
    });
    return () => observers.forEach(o => o.disconnect());
  }, [documentState, pdfDoc]);

  // ── File open ──────────────────────────────────────────────────────────────
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
      setTabs(prev => {
        const exists = prev.find(x => x.id === id);
        if (exists) return prev;
        return [...prev, { id, name: file.name, fullName: file.name, modified: false }];
      });
      setActiveTabId(id);
    } catch (err) {
      console.error(err);
      alert('Failed to open document.');
    } finally {
      setLoading(false);
      e.target.value = '';
    }
  };

  // ── Export ─────────────────────────────────────────────────────────────────
  const handleExportPdf = async () => {
    if (!documentState) return;
    try {
      const res = await fetch('http://localhost:8000/api/document/download');
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = Object.assign(document.createElement('a'), { href: url, download: `edited_${documentState.file_name}` });
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: unknown) { alert('Export failed: ' + (err as Error).message); }
  };

  // ── Undo / Redo ────────────────────────────────────────────────────────────
  const handleUndo = async () => { try { await engineApi.undo(); await refreshDocumentState(); } catch { alert('Nothing to undo!'); } };
  const handleRedo = async () => { try { await engineApi.redo(); await refreshDocumentState(); } catch { alert('Nothing to redo!'); } };

  // ── TTS ────────────────────────────────────────────────────────────────────
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

  // ── Zoom ───────────────────────────────────────────────────────────────────
  const zoomIn    = () => setScale(s => Math.min(+(s + 0.25).toFixed(2), 4.0));
  const zoomOut   = () => setScale(s => Math.max(+(s - 0.25).toFixed(2), 0.25));
  const zoomReset = () => setScale(1.0);

  // ── Keyboard shortcuts ─────────────────────────────────────────────────────
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

  // ── Menu definitions ───────────────────────────────────────────────────────
  const menus: Menu[] = [
    {
      label: 'File',
      items: [
        { label: 'Open…',             icon: '📂', shortcut: 'Ctrl+O', onClick: openFileDialog },
        { label: 'Close Tab',         icon: '✕',  shortcut: 'Ctrl+W', disabled: !documentState },
        { separator: true },
        { label: 'Save',              icon: '💾', shortcut: 'Ctrl+S', disabled: true },
        { label: 'Save As…',          icon: '📝', shortcut: 'Ctrl+Shift+S', disabled: true },
        { separator: true },
        {
          label: 'Export',
          icon: '⬇',
          submenu: [
            { label: 'Export as PDF',         icon: '📄', onClick: handleExportPdf },
            { label: 'Export Flattened PDF',  icon: '🔒', disabled: true },
            { label: 'Export as PDF/A',       icon: '📋', disabled: true },
            { separator: true },
            { label: 'Compress & Export…',    icon: '📦', disabled: true },
          ],
        },
        { separator: true },
        { label: 'Print…', icon: '🖨', shortcut: 'Ctrl+P', disabled: true },
      ],
    },
    {
      label: 'Edit',
      items: [
        { label: 'Undo', icon: '↩', shortcut: 'Ctrl+Z', onClick: handleUndo },
        { label: 'Redo', icon: '↪', shortcut: 'Ctrl+Y', onClick: handleRedo },
        { separator: true },
        { label: 'Copy Selected Text', icon: '⎘', shortcut: 'Ctrl+C', disabled: true },
        { label: 'Select All',         icon: '☐', shortcut: 'Ctrl+A', disabled: true },
        { separator: true },
        {
          label: 'Find & Replace', icon: '🔍',
          submenu: [
            { label: 'Find…',    shortcut: 'Ctrl+F', disabled: true },
            { label: 'Replace…', shortcut: 'Ctrl+H', disabled: true },
          ],
        },
      ],
    },
    {
      label: 'View',
      items: [
        { label: 'Toggle Sidebar',    icon: '🗂', shortcut: 'Ctrl+B', onClick: () => setShowThumbnails(v => !v) },
        { label: 'Toggle Properties', icon: '⚙', shortcut: 'Ctrl+E', onClick: () => setRightPanelOpen(v => !v) },
        { separator: true },
        { label: 'Zoom In',    icon: '🔍', shortcut: 'Ctrl++', onClick: zoomIn },
        { label: 'Zoom Out',   icon: '🔎', shortcut: 'Ctrl+-', onClick: zoomOut },
        { label: 'Actual Size (100%)', onClick: zoomReset, disabled: false },
      ],
    },
    {
      label: 'Insert',
      items: [
        { label: 'Hyperlink…',    icon: '🔗', disabled: true },
        { label: 'Bookmark…',     icon: '🔖', disabled: true },
        { separator: true },
        { label: 'Blank Page',    icon: '📄', disabled: true },
        {
          label: 'Image…', icon: '🖼',
          submenu: [
            { label: 'From File…',     disabled: true },
            { label: 'From Clipboard', disabled: true },
          ],
        },
        { separator: true },
        { label: 'Signature Field…', icon: '✍', disabled: true },
        { label: 'Form Field…',      icon: '☐', disabled: true },
      ],
    },
    {
      label: 'Tools',
      items: [
        {
          label: 'Read Aloud', icon: '📖',
          submenu: [
            { label: 'Read Current Page', icon: '🔊', onClick: handleReadPage },
            { label: 'Read Selection',    icon: '🔉', onClick: handleReadSelection },
            { label: 'Stop Reading',      icon: '⏹',  onClick: ttsStop },
          ],
        },
        { separator: true },
        { label: 'OCR (Recognize Text)…', icon: '🔑', disabled: true },
        { label: 'Protect / Encrypt…',    icon: '🔒', disabled: true },
        { label: 'Compress Document…',    icon: '⚡', disabled: true },
      ],
    },
    {
      label: 'Help',
      items: [
        { label: 'Documentation',        icon: '📘', disabled: true },
        { label: 'Keyboard Shortcuts…',  icon: '⌨',  disabled: true },
        { separator: true },
        { label: 'About PDFEdit', icon: 'ℹ', onClick: () => alert('PDFEdit — Professional PDF Editor') },
      ],
    },
  ];

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

      {/* ── Top bar ── */}
      <TopBar
        tabs={tabs}
        activeTabId={activeTabId}
        onTabClick={setActiveTabId}
        onTabClose={id => {
          setTabs(prev => prev.filter(x => x.id !== id));
          if (activeTabId === id) { setActiveTabId(null); setDocumentState(null); setPdfDoc(null); }
        }}
        onNewTab={openFileDialog}
        menus={menus}
      />

      {/* ── Main body ── */}
      <div className="flex-1 flex overflow-hidden">

        {/* Left sidebar */}
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

        {/* Center: toolbar + canvas */}
        <div className="flex-1 flex flex-col overflow-hidden">
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
        </div>

        {/* Right panel */}
        {rightPanelOpen && (
          <RightPanel
            documentState={documentState}
            activePage={activePage}
          />
        )}
      </div>

      {/* ── TTS bar ── */}
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

      {/* ── Status bar ── */}
      <StatusBar
        activeTool={activeTool}
        scale={scale}
        activePage={activePage}
        pageCount={pageCount}
        lastSelectedText={lastSelectedText}
        documentState={documentState}
      />

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={handleFileUpload}
      />
    </div>
  );
}
