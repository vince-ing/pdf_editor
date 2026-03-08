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

// ── Smart text selection hook ────────────────────────────────────────────────

function useSmartSelection(overlayRef, scale, chars, onComplete) {
    const [mouseBox, setMouseBox] = useState(null);
    const [textRects, setTextRects] = useState([]);
    const startPos = useRef(null);

    const lineBBox = (lineChars) => {
        const minX = Math.min(...lineChars.map(c => c.x));
        const minY = Math.min(...lineChars.map(c => c.y));
        const maxX = Math.max(...lineChars.map(c => c.x + c.width));
        const maxY = Math.max(...lineChars.map(c => c.y + c.height));
        return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
    };

    const onMouseDown = useCallback((e) => {
        e.preventDefault();
        if (!overlayRef.current) return;
        const rect = overlayRef.current.getBoundingClientRect();
        startPos.current = { x: (e.clientX - rect.left) / scale, y: (e.clientY - rect.top) / scale };
        setMouseBox(null);
        setTextRects([]);
    }, [scale]);

    const onMouseMove = useCallback((e) => {
        if (!startPos.current || !overlayRef.current) return;
        const rect = overlayRef.current.getBoundingClientRect();
        const cur = { x: (e.clientX - rect.left) / scale, y: (e.clientY - rect.top) / scale };
        
        const rawBox = {
            x: Math.min(startPos.current.x, cur.x),
            y: Math.min(startPos.current.y, cur.y),
            width: Math.abs(cur.x - startPos.current.x),
            height: Math.abs(cur.y - startPos.current.y),
        };
        setMouseBox(rawBox);

        // Ignore tiny accidental drags
        if (rawBox.width < 2 && rawBox.height < 2) {
            setTextRects([]);
            return;
        }

        if (chars && chars.length > 0) {
            let startDist = Infinity;
            let startIdx = -1;
            let endDist = Infinity;
            let endIdx = -1;

            for (let i = 0; i < chars.length; i++) {
                const c = chars[i];
                const cx = c.x + c.width / 2;
                const cy = c.y + c.height / 2;
                
                const d1 = Math.pow(cx - startPos.current.x, 2) + Math.pow(cy - startPos.current.y, 2);
                if (d1 < startDist) { startDist = d1; startIdx = i; }

                const d2 = Math.pow(cx - cur.x, 2) + Math.pow(cy - cur.y, 2);
                if (d2 < endDist) { endDist = d2; endIdx = i; }
            }

            // Snap to text if the drag starts and ends reasonably close to characters (~31px threshold)
            if (startIdx !== -1 && endIdx !== -1 && startDist < 1000 && endDist < 1000) {
                const minIdx = Math.min(startIdx, endIdx);
                const maxIdx = Math.max(startIdx, endIdx);
                const selectedChars = chars.slice(minIdx, maxIdx + 1);

                const rects = [];
                if (selectedChars.length > 0) {
                    let currentLine = [selectedChars[0]];
                    for (let i = 1; i < selectedChars.length; i++) {
                        const prev = currentLine[currentLine.length - 1];
                        const curr = selectedChars[i];
                        const prevCenterY = prev.y + prev.height / 2;
                        const currCenterY = curr.y + curr.height / 2;

                        // Start a new line box if vertical jump is significant
                        if (Math.abs(prevCenterY - currCenterY) < prev.height * 0.5) {
                            currentLine.push(curr);
                        } else {
                            rects.push(lineBBox(currentLine));
                            currentLine = [curr];
                        }
                    }
                    if (currentLine.length > 0) rects.push(lineBBox(currentLine));
                }
                setTextRects(rects);
                return;
            }
        }
        
        // Clear text rects if we didn't snap, falling back to showing rawBox
        setTextRects([]);

    }, [scale, chars]);

    const finishDrag = useCallback(() => {
        if (!startPos.current) return;
        
        if (textRects.length > 0) {
            onComplete(textRects);
        } else if (mouseBox && mouseBox.width > 4 && mouseBox.height > 4) {
            onComplete([mouseBox]);
        }
        
        startPos.current = null;
        setMouseBox(null);
        setTextRects([]);
    }, [mouseBox, textRects, onComplete]);

    return { mouseBox, textRects, onMouseDown, onMouseMove, onMouseUp: finishDrag, onMouseLeave: finishDrag };
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
    const [pageChars, setPageChars] = useState([]);
    const [hovered, setHovered] = useState(false);
    const [busy, setBusy] = useState(false);
    const [localRotation, setLocalRotation] = useState(pageNode.rotation ?? 0);

    // Fetch and explicitly sort characters to ensure perfect line-reading order
    useEffect(() => {
        let isMounted = true;
        fetch(`http://localhost:8000/api/pages/${pageNode.id}/chars`)
            .then(res => res.json())
            .then(data => {
                if (isMounted && data.status === 'success') {
                    const fetchedChars = data.chars || [];
                    fetchedChars.sort((a, b) => {
                        // Sort top-to-bottom first (with a 5px forgiveness for inline shifts)
                        if (Math.abs(a.y - b.y) > 5) return a.y - b.y;
                        // Then sort left-to-right
                        return a.x - b.x;
                    });
                    setPageChars(fetchedChars);
                }
            })
            .catch(err => console.error("Could not fetch page chars:", err));
        return () => { isMounted = false; };
    }, [pageNode.id]);

    useEffect(() => {
        if (typeof pageNode.rotation === 'number') setLocalRotation(pageNode.rotation);
    }, [pageNode.rotation, pageNode.id]);

    const [dimensions, setDimensions] = useState({
        width:  (pageNode.metadata?.width  || 612) * scale,
        height: (pageNode.metadata?.height || 792) * scale,
    });

    useEffect(() => {
        setAnnotations(pageNode.children || []);
    }, [pageNode.children]);

    // ── Canvas render ────────────────────────────────────────────────────────
    useEffect(() => {
        if (!pdfDoc) return;
        let isMounted = true;
        let renderTask = null;

        const renderPage = async () => {
            try {
                const pageNum = (pageNode.page_number ?? pageIndex) + 1;
                if (pageNum < 1 || pageNum > pdfDoc.numPages) return;

                const page = await pdfDoc.getPage(pageNum);
                if (!isMounted) return;

                const dpr = window.devicePixelRatio || 1;
                const viewport = page.getViewport({ scale: scale * dpr, rotation: localRotation });
                const canvas = canvasRef.current;
                if (!canvas) return;

                const context = canvas.getContext('2d');
                canvas.width = viewport.width;
                canvas.height = viewport.height;

                const cssW = viewport.width / dpr;
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
            if (res?.page?.rotation !== undefined) setLocalRotation(res.page.rotation);
            else setLocalRotation(r => (r + 90) % 360);
            if (onDocumentChanged) await onDocumentChanged();
        });
    }, [pageNode.id, withBusy, onDocumentChanged]);

    const handleRotateCCW = useCallback(() => {
        withBusy(async () => {
            const res = await engineApi.rotatePage(pageNode.id, -90);
            if (res?.page?.rotation !== undefined) setLocalRotation(res.page.rotation);
            else setLocalRotation(r => (r - 90 + 360) % 360);
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

    const handleRectComplete = useCallback(async (rects) => {
        try {
            const promises = rects.map(rect => {
                if (activeTool === TOOLS.HIGHLIGHT) {
                    return engineApi.addHighlight(pageNode.id, rect.x, rect.y, rect.width, rect.height);
                } else if (activeTool === TOOLS.REDACT) {
                    return engineApi.applyRedaction(pageNode.id, rect.x, rect.y, rect.width, rect.height);
                }
                return null;
            }).filter(Boolean);

            const results = await Promise.all(promises);
            const newNodes = [];
            for (const res of results) {
                if (res?.node) newNodes.push(res.node);
                else if (res?.nodes) newNodes.push(...res.nodes);
            }

            if (newNodes.length > 0) {
                setAnnotations(prev => [...prev, ...newNodes]);
                if (onAnnotationAdded) onAnnotationAdded();
            }
        } catch (err) {
            console.error('Annotation failed:', err);
            alert('Annotation failed: ' + (err.response?.data?.detail || err.message));
        }
    }, [activeTool, pageNode.id, onAnnotationAdded]);

    const isDragTool = activeTool === TOOLS.HIGHLIGHT || activeTool === TOOLS.REDACT;
    const dragColor  = activeTool === TOOLS.REDACT ? 'rgba(0,0,0,0.6)' : 'rgba(255,255,0,0.4)';
    const dragBorder = activeTool === TOOLS.REDACT ? '#333' : '#cccc00';

    const { mouseBox, textRects, onMouseDown, onMouseMove, onMouseUp, onMouseLeave } = useSmartSelection(
        overlayRef, scale, pageChars, handleRectComplete
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
                {/* Fallback box shown if not snapping to text */}
                {mouseBox && textRects.length === 0 && (
                    <div style={{
                        position: 'absolute',
                        left: `${mouseBox.x * scale}px`, top: `${mouseBox.y * scale}px`,
                        width: `${mouseBox.width * scale}px`, height: `${mouseBox.height * scale}px`,
                        backgroundColor: 'rgba(52, 152, 219, 0.15)', border: '1px solid rgba(52, 152, 219, 0.5)',
                        pointerEvents: 'none', borderRadius: '2px',
                    }} />
                )}

                {/* Snapped Text Lines */}
                {textRects.map((rect, i) => (
                    <div key={i} style={{
                        position: 'absolute',
                        left: `${rect.x * scale}px`, top: `${rect.y * scale}px`,
                        width: `${rect.width * scale}px`, height: `${rect.height * scale}px`,
                        backgroundColor: dragColor, border: `2px dashed ${dragBorder}`,
                        pointerEvents: 'none', borderRadius: '2px',
                    }} />
                ))}
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