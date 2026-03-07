import React, { useEffect, useRef, useState, useCallback } from 'react';
import { engineApi } from '../api/client';
import { TOOLS, TOOL_CURSORS } from '../tools';

// ── Annotation overlay node ──────────────────────────────────────────────────

const NodeOverlay = ({ node, scale = 1.0 }) => {
    const [hovered, setHovered] = useState(false);
    if (!node.bbox) return null;

    const style = {
        position: 'absolute',
        left:   `${node.bbox.x * scale}px`,
        top:    `${node.bbox.y * scale}px`,
        width:  `${node.bbox.width * scale}px`,
        height: `${node.bbox.height * scale}px`,
        pointerEvents: 'none',
    };

    switch (node.node_type) {
        case 'text':
            return (
                <div
                    style={{
                        ...style,
                        border: hovered ? '1px solid #3498db' : '1px solid transparent',
                        cursor: 'pointer',
                        borderRadius: '2px',
                        pointerEvents: 'auto',
                    }}
                    onMouseEnter={() => setHovered(true)}
                    onMouseLeave={() => setHovered(false)}
                >
                    <span style={{
                        fontSize: `${node.font_size * scale}px`,
                        fontFamily: node.font_family,
                        color: node.color || '#000',
                    }}>
                        {node.text_content}
                    </span>
                </div>
            );
        case 'highlight':
            if (node.color === '#000000') {
                return <div style={{ ...style, backgroundColor: '#000000', opacity: 1.0, borderRadius: '2px', pointerEvents: 'none' }} />;
            }
            return <div style={{ ...style, backgroundColor: node.color || '#FFFF00', opacity: node.opacity ?? 0.5, borderRadius: '2px', pointerEvents: 'none' }} />;
        default:
            return null;
    }
};

// ── Drag rect hook ───────────────────────────────────────────────────────────

function useDragRect(overlayRef, scale, onComplete) {
    const [dragRect, setDragRect] = useState(null);
    const startPos = useRef(null);

    const onMouseDown = useCallback((e) => {
        e.preventDefault();
        if (!overlayRef.current) return;
        const rect = overlayRef.current.getBoundingClientRect();
        startPos.current = { x: (e.clientX - rect.left) / scale, y: (e.clientY - rect.top) / scale };
        setDragRect(null);
    }, [scale]);

    const onMouseMove = useCallback((e) => {
        if (!startPos.current || !overlayRef.current) return;
        const rect = overlayRef.current.getBoundingClientRect();
        const cur = { x: (e.clientX - rect.left) / scale, y: (e.clientY - rect.top) / scale };
        setDragRect({
            x: Math.min(startPos.current.x, cur.x), y: Math.min(startPos.current.y, cur.y),
            width: Math.abs(cur.x - startPos.current.x), height: Math.abs(cur.y - startPos.current.y),
        });
    }, [scale]);

    const finishDrag = useCallback((e) => {
        if (!startPos.current || !overlayRef.current) return;
        const rect = overlayRef.current.getBoundingClientRect();
        const cur = { x: (e.clientX - rect.left) / scale, y: (e.clientY - rect.top) / scale };
        const finalRect = {
            x: Math.min(startPos.current.x, cur.x), y: Math.min(startPos.current.y, cur.y),
            width: Math.abs(cur.x - startPos.current.x), height: Math.abs(cur.y - startPos.current.y),
        };
        startPos.current = null;
        setDragRect(null);
        if (finalRect.width > 4 && finalRect.height > 4) onComplete(finalRect);
    }, [scale, onComplete]);

    return { dragRect, onMouseDown, onMouseMove, onMouseUp: finishDrag, onMouseLeave: finishDrag };
}

// ── Page controls bar ────────────────────────────────────────────────────────

const PageControls = ({ pageIndex, totalPages, onRotateCW, onRotateCCW, onDelete, onMoveUp, onMoveDown }) => (
    <div style={{
        position: 'absolute', top: '10px', left: '50%', transform: 'translateX(-50%)',
        display: 'flex', gap: '6px', alignItems: 'center',
        backgroundColor: 'rgba(15, 23, 35, 0.88)', backdropFilter: 'blur(6px)',
        borderRadius: '8px', padding: '5px 10px', zIndex: 30,
        boxShadow: '0 2px 12px rgba(0,0,0,0.5)', border: '1px solid rgba(255,255,255,0.1)',
        pointerEvents: 'auto', whiteSpace: 'nowrap',
    }}>
        <CtrlBtn onClick={onMoveUp}    disabled={pageIndex === 0}             title="Move up"       color="#546e7a">↑</CtrlBtn>
        <CtrlBtn onClick={onMoveDown}  disabled={pageIndex >= totalPages - 1} title="Move down"     color="#546e7a">↓</CtrlBtn>
        <Divider />
        <CtrlBtn onClick={onRotateCW}  title="Rotate CW"  color="#2980b9">↻</CtrlBtn>
        <CtrlBtn onClick={onRotateCCW} title="Rotate CCW" color="#2980b9">↺</CtrlBtn>
        <Divider />
        <CtrlBtn onClick={onDelete} disabled={totalPages <= 1} title="Delete page" color="#c0392b">✕</CtrlBtn>
    </div>
);

const CtrlBtn = ({ children, onClick, title, color, disabled }) => (
    <button title={title} onClick={onClick} disabled={disabled} style={{
        width: '26px', height: '26px', borderRadius: '5px', border: 'none',
        backgroundColor: disabled ? 'rgba(255,255,255,0.06)' : color,
        color: disabled ? '#3d5166' : 'white',
        fontSize: '14px', fontWeight: '700', cursor: disabled ? 'not-allowed' : 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1, padding: 0,
    }}>
        {children}
    </button>
);

const Divider = () => <div style={{ width: '1px', height: '16px', backgroundColor: 'rgba(255,255,255,0.12)' }} />;

// ── PageRenderer ─────────────────────────────────────────────────────────────

export const PageRenderer = ({
    pageNode, pdfDoc, pageIndex, totalPages, scale = 1.5,
    activeTool, onAnnotationAdded, onDocumentChanged,
}) => {
    const canvasRef  = useRef(null);
    const overlayRef = useRef(null);
    const [annotations, setAnnotations] = useState([]);
    const [hovered, setHovered] = useState(false);
    const [busy, setBusy] = useState(false);

    // Track rotation locally — the GET /api/document endpoint strips PageNode-specific
    // fields (rotation, page_number) because children is typed as List[Node] in Pydantic.
    // We update localRotation directly from the rotate API response, which serializes
    // the PageNode directly and preserves all fields.
    const [localRotation, setLocalRotation] = useState(pageNode.rotation ?? 0);

    // Sync localRotation from pageNode.rotation whenever it changes.
    // Now that the backend uses model_dump(), rotation is always a number.
    // This handles: undo, sidebar-initiated rotate, reorder, new doc load.
    useEffect(() => {
        if (typeof pageNode.rotation === 'number') {
            setLocalRotation(pageNode.rotation);
        }
    }, [pageNode.rotation, pageNode.id]);

    const [dimensions, setDimensions] = useState({
        width:  (pageNode.metadata?.width  || 612) * scale,
        height: (pageNode.metadata?.height || 792) * scale,
    });

    useEffect(() => {
        setAnnotations(pageNode.children || []);
    }, [pageNode.children]);

    // ── Canvas render — driven by localRotation ───────────────────────────────
    useEffect(() => {
        if (!pdfDoc) return;
        let isMounted = true;
        let renderTask = null;

        const renderPage = async () => {
            try {
                // Use the original source page number, not the current array index.
                // After deletes/moves, pageIndex shifts but page_number stays fixed.
                const pageNum = (pageNode.page_number ?? pageIndex) + 1;
                if (pageNum < 1 || pageNum > pdfDoc.numPages) return;

                const page    = await pdfDoc.getPage(pageNum);
                if (!isMounted) return;

                // Scale the canvas by devicePixelRatio so text is sharp on
                // HiDPI / Retina screens. CSS size stays at logical dimensions.
                const dpr      = window.devicePixelRatio || 1;
                const viewport = page.getViewport({ scale: scale * dpr, rotation: localRotation });
                const canvas   = canvasRef.current;
                if (!canvas) return;

                const context  = canvas.getContext('2d');

                // Physical pixels = logical size × dpr
                canvas.width  = viewport.width;
                canvas.height = viewport.height;

                // CSS size = logical dimensions (unaffected by dpr)
                const cssW = viewport.width  / dpr;
                const cssH = viewport.height / dpr;
                canvas.style.width  = `${cssW}px`;
                canvas.style.height = `${cssH}px`;
                setDimensions({ width: cssW, height: cssH });

                renderTask = page.render({ canvasContext: context, viewport });
                await renderTask.promise;
            } catch (err) {
                if (err?.name !== 'RenderingCancelledException') console.error('Render error:', err);
            }
        };

        renderPage();
        return () => { isMounted = false; if (renderTask) renderTask.cancel(); };
    }, [pdfDoc, pageIndex, localRotation, scale]);

    // ── Page-level commands ───────────────────────────────────────────────────

    const busyRef = useRef(false);
    const withBusy = useCallback(async (fn) => {
        if (busyRef.current) return;
        busyRef.current = true;
        setBusy(true);
        try { await fn(); }
        finally { busyRef.current = false; setBusy(false); }
    }, []);

    const handleRotateCW = useCallback(() => {
        withBusy(async () => {
            const res = await engineApi.rotatePage(pageNode.id, 90);
            // res.page is serialized as PageNode directly — rotation field is present
            if (res?.page?.rotation !== undefined) {
                console.log('[rotate] new rotation from API:', res.page.rotation);
                setLocalRotation(res.page.rotation);
            } else {
                // Fallback: just add 90 locally
                setLocalRotation(r => (r + 90) % 360);
            }
            if (onDocumentChanged) await onDocumentChanged();
        });
    }, [pageNode.id, withBusy, onDocumentChanged]);

    const handleRotateCCW = useCallback(() => {
        withBusy(async () => {
            const res = await engineApi.rotatePage(pageNode.id, -90);
            if (res?.page?.rotation !== undefined) {
                setLocalRotation(res.page.rotation);
            } else {
                setLocalRotation(r => (r - 90 + 360) % 360);
            }
            if (onDocumentChanged) await onDocumentChanged();
        });
    }, [pageNode.id, withBusy, onDocumentChanged]);

    const handleDelete = useCallback(() => {
        if (totalPages <= 1) { alert('Cannot delete the last page.'); return; }
        if (!window.confirm(`Delete page ${pageIndex + 1}?`)) return;
        withBusy(async () => {
            await engineApi.deletePage(pageNode.id);
            if (onDocumentChanged) await onDocumentChanged();
        });
    }, [pageNode.id, pageIndex, totalPages, withBusy, onDocumentChanged]);

    const handleMoveUp = useCallback(() => {
        withBusy(async () => {
            await engineApi.movePage(pageNode.id, pageIndex - 1);
            if (onDocumentChanged) await onDocumentChanged();
        });
    }, [pageNode.id, pageIndex, withBusy, onDocumentChanged]);

    const handleMoveDown = useCallback(() => {
        withBusy(async () => {
            await engineApi.movePage(pageNode.id, pageIndex + 1);
            if (onDocumentChanged) await onDocumentChanged();
        });
    }, [pageNode.id, pageIndex, withBusy, onDocumentChanged]);

    // ── Annotation interactions ───────────────────────────────────────────────

    const handleTextClick = useCallback(async (e) => {
        if (!overlayRef.current) return;
        const rect = overlayRef.current.getBoundingClientRect();
        const x = (e.clientX - rect.left) / scale;
        const y = (e.clientY - rect.top)  / scale;
        const text = window.prompt('Enter text:');
        if (!text) return;
        try {
            const res = await engineApi.addTextAnnotation(pageNode.id, text, x, y);
            if (res?.node) setAnnotations(prev => [...prev, res.node]);
            if (onAnnotationAdded) onAnnotationAdded();
        } catch (err) {
            console.error('Failed to add text:', err);
            alert('Failed to add text: ' + (err.response?.data?.detail || err.message));
        }
    }, [scale, pageNode.id, onAnnotationAdded]);

    const handleRectComplete = useCallback(async (rect) => {
        try {
            let res = null;
            if (activeTool === TOOLS.HIGHLIGHT) {
                res = await engineApi.addHighlight(pageNode.id, rect.x, rect.y, rect.width, rect.height);
            } else if (activeTool === TOOLS.REDACT) {
                res = await engineApi.applyRedaction(pageNode.id, rect.x, rect.y, rect.width, rect.height);
            } else return;
            if (res?.node)       setAnnotations(prev => [...prev, res.node]);
            else if (res?.nodes) setAnnotations(prev => [...prev, ...res.nodes]);
            if (onAnnotationAdded) onAnnotationAdded();
        } catch (err) {
            console.error('Annotation failed:', err);
            alert('Annotation failed: ' + (err.response?.data?.detail || err.message));
        }
    }, [activeTool, pageNode.id, onAnnotationAdded]);

    const isDragTool = activeTool === TOOLS.HIGHLIGHT || activeTool === TOOLS.REDACT;
    const dragColor  = activeTool === TOOLS.REDACT ? 'rgba(0,0,0,0.6)' : 'rgba(255,255,0,0.4)';
    const dragBorder = activeTool === TOOLS.REDACT ? '#333' : '#cccc00';

    const { dragRect, onMouseDown, onMouseMove, onMouseUp, onMouseLeave } = useDragRect(
        overlayRef, scale, handleRectComplete
    );

    return (
        <div
            style={{
                position: 'relative',
                width:  `${dimensions.width}px`,
                height: `${dimensions.height}px`,
                flexShrink: 0,
                backgroundColor: 'white',
                boxShadow: hovered ? '0 6px 28px rgba(0,0,0,0.35)' : '0 4px 16px rgba(0,0,0,0.25)',
                margin: '20px auto',
                overflow: 'visible',
                transition: 'box-shadow 0.18s ease',
                opacity: busy ? 0.7 : 1,
            }}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
        >
            <canvas ref={canvasRef} style={{
                position: 'absolute', top: 0, left: 0,
                width: `${dimensions.width}px`, height: `${dimensions.height}px`,
                pointerEvents: 'none',
            }} />

            {/* Annotation layer */}
            <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 5, overflow: 'hidden' }}>
                {annotations.map(child => <NodeOverlay key={child.id} node={child} scale={scale} />)}
            </div>

            {/* Interaction layer */}
            <div
                ref={overlayRef}
                style={{
                    position: 'absolute', top: 0, left: 0, width: '100%', height: '100%',
                    cursor: TOOL_CURSORS[activeTool] || 'default', userSelect: 'none', zIndex: 10,
                }}
                onClick={activeTool === TOOLS.TEXT ? handleTextClick : undefined}
                onMouseDown={isDragTool ? onMouseDown : undefined}
                onMouseMove={isDragTool ? onMouseMove : undefined}
                onMouseUp={isDragTool ? onMouseUp : undefined}
                onMouseLeave={isDragTool ? onMouseLeave : undefined}
            >
                {dragRect && (
                    <div style={{
                        position: 'absolute',
                        left: `${dragRect.x * scale}px`, top: `${dragRect.y * scale}px`,
                        width: `${dragRect.width * scale}px`, height: `${dragRect.height * scale}px`,
                        backgroundColor: dragColor, border: `2px dashed ${dragBorder}`,
                        pointerEvents: 'none', borderRadius: '2px',
                    }} />
                )}
            </div>

            {/* Page controls */}
            {hovered && (
                <PageControls
                    pageIndex={pageIndex}
                    totalPages={totalPages}
                    onRotateCW={handleRotateCW}
                    onRotateCCW={handleRotateCCW}
                    onDelete={handleDelete}
                    onMoveUp={handleMoveUp}
                    onMoveDown={handleMoveDown}
                />
            )}

            {/* Page number badge */}
            <div style={{
                position: 'absolute', bottom: '8px', right: '10px',
                backgroundColor: 'rgba(0,0,0,0.45)', color: 'white',
                fontSize: '11px', fontWeight: '600', padding: '2px 7px',
                borderRadius: '10px', pointerEvents: 'none', zIndex: 20,
            }}>
                {pageIndex + 1}
            </div>

            {busy && (
                <div style={{
                    position: 'absolute', inset: 0, backgroundColor: 'rgba(0,0,0,0.15)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50,
                }}>
                    <div style={{ backgroundColor: 'rgba(15,23,35,0.9)', color: 'white', fontSize: '13px', fontWeight: '600', padding: '8px 18px', borderRadius: '6px' }}>
                        Working…
                    </div>
                </div>
            )}
        </div>
    );
};