// App.jsx — Root component. Orchestrates all panels, state, and interactions.
// Layout: MenuBar → TabBar → Toolbar → [LeftPanel | Canvas | RightPanel] → TtsBar → StatusBar

import React, { useState, useEffect, useCallback, useRef } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import { engineApi } from './api/client';

import { PageRenderer }       from './components/PageRenderer';
import { LeftPanel, PANEL_VIEWS } from './components/LeftPanel';
import { RightPanel }         from './components/RightPanel';
import { MenuBar, buildMenus } from './components/MenuBar';
import { TabBar }             from './components/TabBar';
import { Toolbar }            from './components/Toolbar';
import { TtsBar }             from './components/TtsBar';
import { StatusBar }          from './components/StatusBar';
import { EmptyState }         from './components/EmptyState';

import { useTts }   from './hooks/useTts';
import { TOOLS }    from './tools';
import theme, { injectGlobalStyles } from './theme';

import workerUrl from 'pdfjs-dist/build/pdf.worker.mjs?url';
pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

injectGlobalStyles();

const t = theme;

// ─────────────────────────────────────────────────────────────────────────────
// Loading screen
// ─────────────────────────────────────────────────────────────────────────────
const LoadingScreen = () => (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', background: t.colors.bgBase, gap: '14px', fontFamily: t.fonts.ui }}>
        <div style={{ width: 36, height: 36, border: `2px solid ${t.colors.bgRaised}`, borderTop: `2px solid ${t.colors.accent}`, borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
        <span style={{ fontSize: '13px', color: t.colors.textSecondary }}>Loading document…</span>
    </div>
);

// ─────────────────────────────────────────────────────────────────────────────
// App
// ─────────────────────────────────────────────────────────────────────────────
export default function App() {
    const [documentState,    setDocumentState]    = useState(null);
    const [pdfDoc,           setPdfDoc]           = useState(null);
    const [loading,          setLoading]          = useState(false);
    const [scale,            setScale]            = useState(1.5);
    const [activeTool,       setActiveTool]       = useState(TOOLS.SELECT);
    const [activePage,       setActivePage]       = useState(0);
    const [leftView,         setLeftView]         = useState(PANEL_VIEWS.PAGES); // null = collapsed
    const [rightPanelOpen,   setRightPanelOpen]   = useState(true);
    const [lastSelectedText, setLastSelectedText] = useState('');

    // Tab bar state — scaffolded, single tab for now
    const [tabs,        setTabs]        = useState([]);
    const [activeTabId, setActiveTabId] = useState(null);

    const fileInputRef = useRef(null);
    const pageRefs     = useRef([]);

    const { tts, speak, stop: ttsStop, pauseResume, setSpeed } = useTts();

    // ── Document state ──────────────────────────────────────────────────────
    const refreshDocumentState = useCallback(async () => {
        try {
            const data = await engineApi.getDocumentState();
            if (data?.node_type === 'document') setDocumentState(data);
        } catch (e) { console.error(e); }
    }, []);

    useEffect(() => { refreshDocumentState(); }, [refreshDocumentState]);

    // ── Page intersection tracking ──────────────────────────────────────────
    const scrollToPage = useCallback((index) => {
        pageRefs.current[index]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        setActivePage(index);
    }, []);

    useEffect(() => {
        if (!documentState) return;
        const obs = [];
        pageRefs.current.forEach((el, i) => {
            if (!el) return;
            const o = new IntersectionObserver(
                ([e]) => { if (e.isIntersecting) setActivePage(i); },
                { threshold: 0.4 }
            );
            o.observe(el);
            obs.push(o);
        });
        return () => obs.forEach(o => o.disconnect());
    }, [documentState, pdfDoc]);

    // ── File open ───────────────────────────────────────────────────────────
    const openFileDialog = () => fileInputRef.current?.click();

    const handleFileUpload = async (event) => {
        const file = event.target.files[0];
        if (!file) return;
        setLoading(true);
        try {
            const arrayBuffer = await file.arrayBuffer();
            const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
            setPdfDoc(pdf);
            await engineApi.uploadDocument(file);
            await refreshDocumentState();
            setActivePage(0);

            // Add/update tab
            const id = file.name;
            setTabs(prev => {
                const exists = prev.find(x => x.id === id);
                if (exists) return prev.map(x => x.id === id ? { ...x, name: file.name } : x);
                return [...prev, { id, name: file.name, fullName: file.name, modified: false }];
            });
            setActiveTabId(id);
        } catch (e) {
            console.error(e);
            alert('Failed to open document.');
        } finally {
            setLoading(false);
            event.target.value = null;
        }
    };

    // ── Export ──────────────────────────────────────────────────────────────
    const handleExportPdf = async () => {
        if (!documentState) return;
        try {
            const res = await fetch('http://localhost:8000/api/document/download');
            if (!res.ok) throw new Error(await res.text());
            const blob = await res.blob();
            const url  = URL.createObjectURL(blob);
            const a    = Object.assign(document.createElement('a'), { href: url, download: `edited_${documentState.file_name}` });
            a.click();
            URL.revokeObjectURL(url);
        } catch (e) { alert('Export failed: ' + e.message); }
    };

    // ── Undo / Redo ─────────────────────────────────────────────────────────
    const handleUndo = async () => { try { await engineApi.undo(); await refreshDocumentState(); } catch { alert('Nothing to undo!'); } };
    const handleRedo = async () => { try { await engineApi.redo(); await refreshDocumentState(); } catch { alert('Nothing to redo!'); } };

    // ── TTS ─────────────────────────────────────────────────────────────────
    const handleReadPage = useCallback(async () => {
        if (!documentState || !pdfDoc) return alert('Open a document first.');
        const pageNode = documentState.children[activePage];
        if (!pageNode) return;
        try {
            const chars = await engineApi.getPageChars(pageNode.id);
            const text  = chars.map(c => c.text).join('');
            if (!text.trim()) return alert('No readable text on this page. Try running OCR first.');
            await speak(text, `Reading page ${activePage + 1}`);
        } catch (e) { alert('TTS failed: ' + e.message); }
    }, [documentState, pdfDoc, activePage, speak]);

    const handleReadSelection = useCallback(async () => {
        if (!lastSelectedText?.trim()) return alert('Select text first using the Select tool.');
        await speak(lastSelectedText.trim(), 'Reading selection');
    }, [lastSelectedText, speak]);

    // ── Zoom ────────────────────────────────────────────────────────────────
    const zoomIn    = () => setScale(s => Math.min(+(s + 0.25).toFixed(2), 4.0));
    const zoomOut   = () => setScale(s => Math.max(+(s - 0.25).toFixed(2), 0.25));
    const zoomReset = () => setScale(1.0);

    // ── Keyboard shortcuts ──────────────────────────────────────────────────
    useEffect(() => {
        const handler = (e) => {
            if (e.ctrlKey || e.metaKey) {
                if (e.key === 'z') { e.preventDefault(); handleUndo(); }
                if (e.key === 'y') { e.preventDefault(); handleRedo(); }
                if (e.key === 'o') { e.preventDefault(); openFileDialog(); }
                if (e.key === '=') { e.preventDefault(); zoomIn(); }
                if (e.key === '-') { e.preventDefault(); zoomOut(); }
                if (e.key === 'b') { e.preventDefault(); setLeftView(v => v === PANEL_VIEWS.PAGES ? null : PANEL_VIEWS.PAGES); }
                if (e.key === 'e') { e.preventDefault(); setRightPanelOpen(v => !v); }
            }
        };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, [handleUndo, handleRedo]);

    // ── Menus ───────────────────────────────────────────────────────────────
    const menus = buildMenus({
        onOpen:            openFileDialog,
        onExportPdf:       handleExportPdf,
        onUndo:            handleUndo,
        onRedo:            handleRedo,
        onReadPage:        handleReadPage,
        onReadSelection:   handleReadSelection,
        onStopReading:     ttsStop,
        onZoomIn:          zoomIn,
        onZoomOut:         zoomOut,
        onToggleSidebar:   () => setLeftView(v => v === PANEL_VIEWS.PAGES ? null : PANEL_VIEWS.PAGES),
        onToggleRightPanel:() => setRightPanelOpen(v => !v),
        onAbout:           () => alert('PDFEdit\nProfessional PDF editor\n\nBuilt with React + pdf.js'),
    });

    const pageCount = documentState?.children?.length ?? 0;

    if (loading) return <LoadingScreen />;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: t.colors.bgBase, fontFamily: t.fonts.ui, color: t.colors.textPrimary, overflow: 'hidden' }}>

            {/* ── Menu bar ── */}
            <MenuBar
                menus={menus}
                documentName={documentState?.file_name}
            />

            {/* ── Tab bar ── */}
            <TabBar
                tabs={tabs}
                activeTabId={activeTabId}
                onTabClick={setActiveTabId}
                onTabClose={(id) => {
                    setTabs(prev => prev.filter(x => x.id !== id));
                    if (activeTabId === id) { setActiveTabId(null); setDocumentState(null); setPdfDoc(null); }
                }}
                onNewTab={openFileDialog}
            />

            {/* ── Toolbar ── */}
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

            {/* ── Body ── */}
            <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

                {/* Left panel (rail + optional drawer) */}
                <LeftPanel
                    pdfDoc={pdfDoc}
                    documentState={documentState}
                    activePage={activePage}
                    onPageClick={scrollToPage}
                    onDocumentChanged={refreshDocumentState}
                    activeView={leftView}
                    onViewChange={setLeftView}
                />

                {/* Canvas */}
                <main style={{
                    flex: 1, overflow: 'auto',
                    backgroundColor: t.colors.bgCanvas,
                    backgroundImage: 'radial-gradient(circle, rgba(0,0,0,0.07) 1px, transparent 1px)',
                    backgroundSize: '20px 20px',
                    padding: '28px 20px',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                }}>
                    {!documentState ? (
                        <EmptyState onOpen={openFileDialog} />
                    ) : (
                        documentState.children.map((page, index) => (
                            <div key={page.id} ref={el => pageRefs.current[index] = el} style={{ width: '100%' }}>
                                <PageRenderer
                                    pageNode={page}
                                    pdfDoc={pdfDoc}
                                    pageIndex={index}
                                    totalPages={pageCount}
                                    scale={scale}
                                    activeTool={activeTool}
                                    onAnnotationAdded={refreshDocumentState}
                                    onDocumentChanged={refreshDocumentState}
                                    onTextSelected={setLastSelectedText}
                                />
                            </div>
                        ))
                    )}
                </main>

                {/* Right properties panel */}
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
                style={{ display: 'none' }}
                onChange={handleFileUpload}
            />
        </div>
    );
}