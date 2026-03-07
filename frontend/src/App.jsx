import React, { useState, useEffect, useCallback, useRef } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import { engineApi } from './api/client';
import { PageRenderer } from './components/PageRenderer';

import workerUrl from 'pdfjs-dist/build/pdf.worker.mjs?url';
pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

function App() {
    const [documentState, setDocumentState] = useState(null);
    const [pdfDoc, setPdfDoc] = useState(null);
    const [loading, setLoading] = useState(false);
    const [scale, setScale] = useState(1.5);
    const fileInputRef = useRef(null);

    const refreshDocumentState = useCallback(async () => {
        try {
            const data = await engineApi.getDocumentState();
            if (data && data.node_type === "document") {
                setDocumentState(data);
            }
        } catch (error) {
            console.error("Failed to fetch document state:", error);
        }
    }, []);

    useEffect(() => {
        refreshDocumentState();
    }, [refreshDocumentState]);

    const handleUndo = async () => {
        try {
            await engineApi.undo();
            await refreshDocumentState();
        } catch (e) {
            alert("Nothing to undo!");
        }
    };

    const handleFileUpload = async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        setLoading(true);
        try {
            const arrayBuffer = await file.arrayBuffer();
            const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer });
            const pdf = await loadingTask.promise;
            setPdfDoc(pdf);

            await engineApi.uploadDocument(file);
            await refreshDocumentState();
        } catch (error) {
            console.error(error);
            alert("Failed to upload document.");
        } finally {
            setLoading(false);
            event.target.value = null;
        }
    };

    const zoomIn  = () => setScale(s => Math.min(parseFloat((s + 0.25).toFixed(2)), 4.0));
    const zoomOut = () => setScale(s => Math.max(parseFloat((s - 0.25).toFixed(2)), 0.25));
    const zoomReset = () => setScale(1.5);

    if (loading) return <div style={{ padding: '20px' }}>Loading...</div>;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', backgroundColor: '#e0e0e0' }}>
            <div style={{ padding: '15px', backgroundColor: '#2c3e50', color: 'white', display: 'flex', gap: '15px', alignItems: 'center', flexWrap: 'wrap' }}>
                <input
                    type="file"
                    accept="application/pdf"
                    ref={fileInputRef}
                    style={{ display: 'none' }}
                    onChange={handleFileUpload}
                />
                <button
                    onClick={() => fileInputRef.current.click()}
                    style={{ padding: '8px 16px', cursor: 'pointer', backgroundColor: '#3498db', color: 'white', border: 'none', borderRadius: '4px' }}
                >
                    Open PDF File
                </button>
                <button
                    onClick={handleUndo}
                    style={{ padding: '8px 16px', cursor: 'pointer', backgroundColor: '#e74c3c', color: 'white', border: 'none', borderRadius: '4px' }}
                >
                    Undo
                </button>
                <button
                    onClick={refreshDocumentState}
                    style={{ padding: '8px 16px', cursor: 'pointer', backgroundColor: '#2ecc71', color: 'white', border: 'none', borderRadius: '4px' }}
                >
                    Sync State
                </button>

                {/* Zoom controls */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginLeft: '16px', borderLeft: '1px solid rgba(255,255,255,0.2)', paddingLeft: '16px' }}>
                    <button
                        onClick={zoomOut}
                        disabled={scale <= 0.25}
                        style={{ padding: '8px 12px', cursor: 'pointer', backgroundColor: '#546e7a', color: 'white', border: 'none', borderRadius: '4px', fontSize: '16px', lineHeight: 1 }}
                    >
                        −
                    </button>
                    <span
                        onClick={zoomReset}
                        title="Click to reset to 150%"
                        style={{ minWidth: '52px', textAlign: 'center', fontWeight: 'bold', cursor: 'pointer', userSelect: 'none' }}
                    >
                        {Math.round(scale * 100)}%
                    </span>
                    <button
                        onClick={zoomIn}
                        disabled={scale >= 4.0}
                        style={{ padding: '8px 12px', cursor: 'pointer', backgroundColor: '#546e7a', color: 'white', border: 'none', borderRadius: '4px', fontSize: '16px', lineHeight: 1 }}
                    >
                        +
                    </button>
                </div>

                <span style={{ marginLeft: 'auto', fontWeight: 'bold' }}>
                    {documentState ? `Loaded: ${documentState.file_name}` : "No Document Loaded"}
                </span>
            </div>

            <div style={{ flex: 1, overflow: 'auto', padding: '20px', display: 'flex', flexDirection: 'column' }}>
                {!documentState && (
                    <div style={{ margin: 'auto', color: '#7f8c8d' }}>
                        Click "Open PDF File" to select a document.
                    </div>
                )}
                {documentState && pdfDoc && documentState.children.map((page, index) => (
                    <PageRenderer
                        key={page.id}
                        pageNode={page}
                        pdfDoc={pdfDoc}
                        pageIndex={index}
                        scale={scale}
                    />
                ))}
            </div>
        </div>
    );
}

export default App;