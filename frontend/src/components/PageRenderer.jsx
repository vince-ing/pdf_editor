import React, { useEffect, useRef, useState, useCallback } from 'react';
import { engineApi } from '../api/client';
import { TOOLS, TOOL_CURSORS } from '../tools';

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
            return (
                <div style={{
                    ...style,
                    backgroundColor: '#FFFF00',
                    opacity: 0.5,
                    borderRadius: '2px',
                }} />
            );
        case 'highlight_black': // redaction stored as highlight with black color
        default:
            if (node.color === '#000000') {
                return (
                    <div style={{
                        ...style,
                        backgroundColor: '#000000',
                        opacity: 1.0,
                        borderRadius: '2px',
                    }} />
                );
            }
            return null;
    }
};

function useDragRect(overlayRef, scale, onComplete) {
    const [dragRect, setDragRect] = useState(null);
    const startPos = useRef(null);

    const onMouseDown = useCallback((e) => {
        e.preventDefault();
        if (!overlayRef.current) return;
        const rect = overlayRef.current.getBoundingClientRect();
        startPos.current = {
            x: (e.clientX - rect.left) / scale,
            y: (e.clientY - rect.top)  / scale,
        };
        setDragRect(null);
    }, [scale]);

    const onMouseMove = useCallback((e) => {
        if (!startPos.current || !overlayRef.current) return;
        const rect = overlayRef.current.getBoundingClientRect();
        const cur = {
            x: (e.clientX - rect.left) / scale,
            y: (e.clientY - rect.top)  / scale,
        };
        setDragRect({
            x:      Math.min(startPos.current.x, cur.x),
            y:      Math.min(startPos.current.y, cur.y),
            width:  Math.abs(cur.x - startPos.current.x),
            height: Math.abs(cur.y - startPos.current.y),
        });
    }, [scale]);

    const finishDrag = useCallback((e) => {
        if (!startPos.current || !overlayRef.current) return;
        const rect = overlayRef.current.getBoundingClientRect();
        const cur = {
            x: (e.clientX - rect.left) / scale,
            y: (e.clientY - rect.top)  / scale,
        };
        const finalRect = {
            x:      Math.min(startPos.current.x, cur.x),
            y:      Math.min(startPos.current.y, cur.y),
            width:  Math.abs(cur.x - startPos.current.x),
            height: Math.abs(cur.y - startPos.current.y),
        };
        startPos.current = null;
        setDragRect(null);
        if (finalRect.width > 4 && finalRect.height > 4) onComplete(finalRect);
    }, [scale, onComplete]);

    return { dragRect, onMouseDown, onMouseMove, onMouseUp: finishDrag, onMouseLeave: finishDrag };
}

export const PageRenderer = ({ pageNode, pdfDoc, pageIndex, scale = 1.5, activeTool, onAnnotationAdded }) => {
    const canvasRef  = useRef(null);
    const overlayRef = useRef(null);
    const [annotations, setAnnotations] = useState([]);
    const [dimensions, setDimensions] = useState({
        width:  (pageNode.metadata?.width  || 612) * scale,
        height: (pageNode.metadata?.height || 792) * scale,
    });

    // Sync annotations when parent document state refreshes (e.g. after undo)
    useEffect(() => {
        setAnnotations(pageNode.children || []);
    }, [pageNode.children]);

    // Canvas render — isolated from annotation state changes
    useEffect(() => {
        if (!pdfDoc) return;
        let isMounted = true;
        let renderTask = null;

        const renderPage = async () => {
            try {
                const pageNum = pageIndex + 1;
                if (pageNum < 1 || pageNum > pdfDoc.numPages) return;

                const page     = await pdfDoc.getPage(pageNum);
                if (!isMounted) return;

                const viewport = page.getViewport({ scale, rotation: pageNode.rotation ?? 0 });
                setDimensions({ width: viewport.width, height: viewport.height });

                const canvas  = canvasRef.current;
                if (!canvas) return;

                const context = canvas.getContext('2d');
                canvas.width  = viewport.width;
                canvas.height = viewport.height;

                renderTask = page.render({ canvasContext: context, viewport });
                await renderTask.promise;
            } catch (err) {
                if (err?.name !== 'RenderingCancelledException') console.error('Render error:', err);
            }
        };

        renderPage();
        return () => { isMounted = false; renderTask?.cancel(); };
    }, [pdfDoc, pageIndex, pageNode.rotation, scale]);

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
            onAnnotationAdded?.();
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
            } else {
                return;
            }
            if (res?.node) {
                setAnnotations(prev => [...prev, res.node]);
            } else if (res?.nodes) {
                setAnnotations(prev => [...prev, ...res.nodes]);
            }
            onAnnotationAdded?.();
        } catch (err) {
            console.error('Annotation failed:', err);
            alert('Annotation failed: ' + (err.response?.data?.detail || err.message));
        }
    }, [activeTool, pageNode.id, onAnnotationAdded]);

    const { dragRect, onMouseDown, onMouseMove, onMouseUp, onMouseLeave } = useDragRect(
        overlayRef, scale, handleRectComplete
    );

    const isDragTool = activeTool === TOOLS.HIGHLIGHT || activeTool === TOOLS.REDACT;
    const dragColor  = activeTool === TOOLS.REDACT ? 'rgba(0,0,0,0.6)' : 'rgba(255,255,0,0.4)';
    const dragBorder = activeTool === TOOLS.REDACT ? '#333' : '#cccc00';

    return (
        <div style={{
            position: 'relative',
            width:  `${dimensions.width}px`,
            height: `${dimensions.height}px`,
            flexShrink: 0,
            backgroundColor: 'white',
            boxShadow: '0 4px 16px rgba(0,0,0,0.25)',
            margin: '20px auto',
            overflow: 'hidden',
        }}>
            {/* PDF canvas */}
            <canvas
                ref={canvasRef}
                style={{
                    position: 'absolute', top: 0, left: 0,
                    width: `${dimensions.width}px`, height: `${dimensions.height}px`,
                    pointerEvents: 'none',
                }}
            />

            {/* Annotation layer */}
            <div style={{
                position: 'absolute', top: 0, left: 0,
                width: '100%', height: '100%',
                pointerEvents: 'none', zIndex: 5,
            }}>
                {annotations.map(child => (
                    <NodeOverlay key={child.id} node={child} scale={scale} />
                ))}
            </div>

            {/* Interaction layer */}
            <div
                ref={overlayRef}
                style={{
                    position: 'absolute', top: 0, left: 0,
                    width: '100%', height: '100%',
                    cursor: TOOL_CURSORS[activeTool] || 'default',
                    userSelect: 'none', zIndex: 10,
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
                        left:   `${dragRect.x * scale}px`,
                        top:    `${dragRect.y * scale}px`,
                        width:  `${dragRect.width * scale}px`,
                        height: `${dragRect.height * scale}px`,
                        backgroundColor: dragColor,
                        border: `2px dashed ${dragBorder}`,
                        pointerEvents: 'none',
                        borderRadius: '2px',
                    }} />
                )}
            </div>

            {/* Page number badge */}
            <div style={{
                position: 'absolute', bottom: '8px', right: '10px',
                backgroundColor: 'rgba(0,0,0,0.45)', color: 'white',
                fontSize: '11px', fontWeight: '600', padding: '2px 7px',
                borderRadius: '10px', pointerEvents: 'none', zIndex: 20,
            }}>
                {pageIndex + 1}
            </div>
        </div>
    );
};