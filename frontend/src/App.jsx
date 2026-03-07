import React, { useState, useEffect, useCallback, useRef } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import { engineApi } from './api/client';
import { PageRenderer } from './components/PageRenderer';
import { Sidebar } from './components/Sidebar';
import { TOOLS, TOOL_ICONS } from './tools';

import workerUrl from 'pdfjs-dist/build/pdf.worker.mjs?url';
pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

function App() {
    const [documentState, setDocumentState] = useState(null);
    const [pdfDoc, setPdfDoc]               = useState(null);
    const [loading, setLoading]             = useState(false);
    const [scale, setScale]                 = useState(1.5);
    const [activeTool, setActiveTool]       = useState(TOOLS.SELECT);
    const [activePage, setActivePage]       = useState(0);
    const [sidebarOpen, setSidebarOpen]     = useState(true);
    const fileInputRef = useRef(null);
    const pageRefs     = useRef([]);

    const refreshDocumentState = useCallback(async () => {
        try {
            const data = await engineApi.getDocumentState();
            // ── DIAGNOSTIC: remove these logs once working ──
            if (data?.children?.[0]) {
                console.log('[DEBUG] First page from API:', {
                    id: data.children[0].id,
                    rotation: data.children[0].rotation,
                    node_type: data.children[0].node_type,
                    keys: Object.keys(data.children[0]),
                });
            }
            if (data && data.node_type === 'document') {
                setDocumentState(data);
            }
        } catch (error) {
            console.error('Failed to fetch document state:', error);
        }
    }, []);

    useEffect(() => { refreshDocumentState(); }, [refreshDocumentState]);

    const scrollToPage = useCallback((index) => {
        const el = pageRefs.current[index];
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        setActivePage(index);
    }, []);

    useEffect(() => {
        if (!documentState) return;
        const observers = [];
        pageRefs.current.forEach((el, i) => {
            if (!el) return;
            const obs = new IntersectionObserver(
                ([entry]) => { if (entry.isIntersecting) setActivePage(i); },
                { threshold: 0.4 }
            );
            obs.observe(el);
            observers.push(obs);
        });
        return () => observers.forEach(o => o.disconnect());
    }, [documentState, pdfDoc]);

    const handleUndo = async () => {
        try {
            await engineApi.undo();
            await refreshDocumentState();
        } catch { alert('Nothing to undo!'); }
    };

    const handleRedo = async () => {
        try {
            await engineApi.redo();
            await refreshDocumentState();
        } catch { alert('Nothing to redo!'); }
    };

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
        } catch (error) {
            console.error(error);
            alert('Failed to upload document.');
        } finally {
            setLoading(false);
            event.target.value = null;
        }
    };

    const handleDownload = async () => {
        if (!documentState) return;
        try {
            const res = await fetch('http://localhost:8000/api/document/download');
            if (!res.ok) throw new Error(await res.text());
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `edited_${documentState.file_name}`;
            a.click();
            URL.revokeObjectURL(url);
        } catch (err) {
            console.error(err);
            alert('Export failed: ' + err.message);
        }
    };

    const zoomIn    = () => setScale(s => Math.min(parseFloat((s + 0.25).toFixed(2)), 4.0));
    const zoomOut   = () => setScale(s => Math.max(parseFloat((s - 0.25).toFixed(2)), 0.25));
    const zoomReset = () => setScale(1.5);

    const pageCount = documentState?.children?.length ?? 0;

    const btnBase = {
        padding: '7px 14px', cursor: 'pointer', border: 'none',
        borderRadius: '4px', fontWeight: '600', fontSize: '13px',
    };

    if (loading) return (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', backgroundColor: '#1a2332', color: 'white', fontSize: '18px' }}>
            Loading document…
        </div>
    );

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', backgroundColor: '#2c3e50', fontFamily: 'system-ui, sans-serif' }}>

            {/* Toolbar */}
            <div style={{
                padding: '10px 16px', backgroundColor: '#1a2332',
                display: 'flex', gap: '10px', alignItems: 'center',
                flexShrink: 0, borderBottom: '1px solid #0d1520',
                boxShadow: '0 2px 6px rgba(0,0,0,0.4)',
            }}>
                <button
                    onClick={() => setSidebarOpen(o => !o)}
                    style={{ ...btnBase, backgroundColor: sidebarOpen ? '#2980b9' : '#546e7a', color: 'white', fontSize: '16px', padding: '7px 11px' }}
                    title="Toggle sidebar"
                >☰</button>

                <div style={{ width: '1px', height: '28px', backgroundColor: 'rgba(255,255,255,0.15)' }} />

                <input type="file" accept="application/pdf" ref={fileInputRef} style={{ display: 'none' }} onChange={handleFileUpload} />
                <button onClick={() => fileInputRef.current.click()} style={{ ...btnBase, backgroundColor: '#2980b9', color: 'white' }}>Open PDF</button>
                <button onClick={handleUndo} style={{ ...btnBase, backgroundColor: '#c0392b', color: 'white' }} title="Undo (Ctrl+Z)">↩ Undo</button>
                <button onClick={handleRedo} style={{ ...btnBase, backgroundColor: '#7f8c8d', color: 'white' }} title="Redo (Ctrl+Y)">↪ Redo</button>
                <button
                    onClick={handleDownload}
                    disabled={!documentState}
                    style={{ ...btnBase, backgroundColor: documentState ? '#27ae60' : '#3d5a47', color: 'white' }}
                    title="Export and download modified PDF"
                >⬇ Export PDF</button>

                <div style={{ width: '1px', height: '28px', backgroundColor: 'rgba(255,255,255,0.15)' }} />

                {/* Tool buttons */}
                {Object.values(TOOLS).map(tool => (
                    <button
                        key={tool}
                        onClick={() => setActiveTool(tool)}
                        title={TOOL_ICONS[tool].label}
                        style={{
                            ...btnBase,
                            backgroundColor: activeTool === tool ? '#f39c12' : '#546e7a',
                            color: 'white', padding: '7px 11px', fontSize: '15px',
                        }}
                    >
                        {TOOL_ICONS[tool].icon}
                    </button>
                ))}
                <span style={{ color: '#f39c12', fontSize: '12px', fontWeight: '600' }}>
                    {TOOL_ICONS[activeTool].label}
                </span>

                <div style={{ width: '1px', height: '28px', backgroundColor: 'rgba(255,255,255,0.15)' }} />

                {/* Zoom */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <button onClick={zoomOut} disabled={scale <= 0.25} style={{ ...btnBase, backgroundColor: '#546e7a', color: 'white', padding: '7px 11px', fontSize: '16px' }}>−</button>
                    <span onClick={zoomReset} title="Click to reset" style={{ minWidth: '50px', textAlign: 'center', color: 'white', fontWeight: '700', cursor: 'pointer', fontSize: '13px' }}>
                        {Math.round(scale * 100)}%
                    </span>
                    <button onClick={zoomIn} disabled={scale >= 4.0} style={{ ...btnBase, backgroundColor: '#546e7a', color: 'white', padding: '7px 11px', fontSize: '16px' }}>+</button>
                </div>

                <span style={{ marginLeft: 'auto', color: '#aab7c4', fontSize: '13px' }}>
                    {documentState
                        ? <><strong style={{ color: 'white' }}>{documentState.file_name}</strong>&nbsp;—&nbsp;page {activePage + 1} of {pageCount}</>
                        : <span style={{ color: '#546e7a' }}>No document loaded</span>
                    }
                </span>
            </div>

            {/* Body */}
            <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
                {sidebarOpen && (
                    <Sidebar
                        pdfDoc={pdfDoc}
                        documentState={documentState}
                        activePage={activePage}
                        onPageClick={scrollToPage}
                        onDocumentChanged={refreshDocumentState}
                    />
                )}

                <div style={{ flex: 1, overflow: 'auto', padding: '24px', backgroundColor: '#e0e4e8' }}>
                    {!documentState && (
                        <div style={{ marginTop: '80px', textAlign: 'center', color: '#7f8c8d' }}>
                            <div style={{ fontSize: '48px', marginBottom: '16px' }}>📄</div>
                            <div style={{ fontSize: '16px' }}>Click <strong>Open PDF</strong> to load a document</div>
                        </div>
                    )}
                    {documentState && pdfDoc && documentState.children.map((page, index) => (
                        <div key={page.id} ref={el => pageRefs.current[index] = el}>
                            <PageRenderer
                                pageNode={page}
                                pdfDoc={pdfDoc}
                                pageIndex={index}
                                totalPages={pageCount}
                                scale={scale}
                                activeTool={activeTool}
                                onAnnotationAdded={refreshDocumentState}
                                onDocumentChanged={refreshDocumentState}
                            />
                        </div>
                    ))}
                </div>
            </div>

            {/* Status bar */}
            <div style={{
                padding: '4px 16px', backgroundColor: '#1a2332',
                display: 'flex', gap: '24px', alignItems: 'center',
                fontSize: '12px', color: '#7f8c8d', flexShrink: 0,
                borderTop: '1px solid #0d1520',
            }}>
                <span>Tool: <strong style={{ color: '#f39c12' }}>{TOOL_ICONS[activeTool].label}</strong></span>
                <span>Zoom: <strong style={{ color: 'white' }}>{Math.round(scale * 100)}%</strong></span>
                {documentState && <span>Pages: <strong style={{ color: 'white' }}>{pageCount}</strong></span>}
                {documentState && <span>Page: <strong style={{ color: 'white' }}>{activePage + 1}</strong></span>}
            </div>
        </div>
    );
}

export default App;