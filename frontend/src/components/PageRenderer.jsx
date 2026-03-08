import React, { useState, useEffect, useCallback, useRef } from 'react';
import { engineApi } from '../api/client';
import { TOOLS, TOOL_CURSORS } from '../tools';

import { PageControls } from './PageControls';
import { NodeOverlay } from './NodeOverlay';
import { usePdfCanvas } from '../hooks/usePdfCanvas';
import { usePageChars } from '../hooks/usePageChars';
import { useDragSelection } from '../hooks/useDragSelection';

// ── Copy toast ────────────────────────────────────────────────────────────────
const CopyToast = ({ visible }) => (
    <div style={{
        position: 'fixed', bottom: '32px', left: '50%',
        transform: `translateX(-50%) translateY(${visible ? '0' : '12px'})`,
        backgroundColor: 'rgba(20,30,48,0.95)', color: 'white',
        padding: '9px 20px', borderRadius: '8px', fontSize: '13px', fontWeight: '600',
        pointerEvents: 'none', opacity: visible ? 1 : 0,
        transition: 'opacity 0.2s ease, transform 0.2s ease',
        zIndex: 9999, boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
        border: '1px solid rgba(255,255,255,0.1)',
    }}>✓ Copied to clipboard</div>
);

// ── PageRenderer ──────────────────────────────────────────────────────────────
export const PageRenderer = ({
    pageNode, pdfDoc, pageIndex, totalPages, scale = 1.5,
    activeTool, onAnnotationAdded, onDocumentChanged,
}) => {
    const overlayRef = useRef(null);

    const [annotations,   setAnnotations]   = useState([]);
    const [hovered,       setHovered]       = useState(false);
    const [busy,          setBusy]          = useState(false);
    const [localRotation, setLocalRotation] = useState(pageNode.rotation ?? 0);
    const [showToast,     setShowToast]     = useState(false);
    
    const toastTimer = useRef(null);

    // Keep rotation and annotations synced with the underlying node
    useEffect(() => {
        if (typeof pageNode.rotation === 'number') setLocalRotation(pageNode.rotation);
    }, [pageNode.rotation, pageNode.id]);

    useEffect(() => { 
        setAnnotations(pageNode.children || []); 
    }, [pageNode.children]);

    // ── Custom Hooks ──────────────────────────────────────────────────────────
    const { canvasRef, fullDimensions } = usePdfCanvas({
        pdfDoc,
        pageNode,
        pageIndex,
        scale,
        localRotation
    });

    const { pageChars } = usePageChars({
        pageNodeId: pageNode.id,
        localRotation,
        metadata: pageNode.metadata
    });

    // ── Action / Tool Handlers ────────────────────────────────────────────────
    const triggerToast = useCallback(() => {
        setShowToast(true);
        clearTimeout(toastTimer.current);
        toastTimer.current = setTimeout(() => setShowToast(false), 2000);
    }, []);

    const handleAction = useCallback(async (rects) => {
        if (activeTool === TOOLS.CROP) {
            // Drag hook automatically stores this in committedRects, we just wait for confirm
            return;
        }

        if (activeTool === TOOLS.SELECT) {
            const tol = 4;
            const sel = pageChars.filter(c => {
                const cx = c.x + c.width/2, cy = c.y + c.height/2;
                return rects.some(r =>
                    cx >= r.x - tol && cx <= r.x + r.width  + tol &&
                    cy >= r.y - tol && cy <= r.y + r.height + tol
                );
            }).sort((a, b) => Math.abs(a.y - b.y) > 5 ? a.y - b.y : a.x - b.x);

            if (!sel.length) return;

            let text = sel[0].text;
            for (let i = 1; i < sel.length; i++) {
                const p = sel[i-1], c = sel[i];
                const avgH = (p.height + c.height) / 2;
                if (Math.abs((p.y + p.height/2) - (c.y + c.height/2)) > avgH * 0.75) {
                    text += '\n' + c.text;
                } else {
                    text += (c.x - (p.x + p.width) > p.width * 0.4 ? ' ' : '') + c.text;
                }
            }
            try { await navigator.clipboard.writeText(text); triggerToast(); }
            catch { window.prompt('Copy (Ctrl+C):', text); }
            return;
        }

        try {
            const results = await Promise.all(rects.map(r => {
                if (activeTool === TOOLS.HIGHLIGHT) return engineApi.addHighlight(pageNode.id, r.x, r.y, r.width, r.height);
                if (activeTool === TOOLS.REDACT)    return engineApi.applyRedaction(pageNode.id, r.x, r.y, r.width, r.height);
                return null;
            }).filter(Boolean));
            const nodes = results.flatMap(r => r?.node ? [r.node] : r?.nodes ?? []);
            if (nodes.length) { setAnnotations(p => [...p, ...nodes]); onAnnotationAdded?.(); }
        } catch (err) { console.error(err); alert('Failed: ' + err.message); }
    }, [activeTool, pageNode.id, pageChars, triggerToast, onAnnotationAdded]);

    const { 
        liveRects, 
        committedRects, 
        clearSelection, 
        handlers 
    } = useDragSelection({
        overlayRef,
        pageChars,
        scale,
        activeTool,
        metadata: pageNode.metadata,
        onAction: handleAction
    });

    // ── Page Commands ─────────────────────────────────────────────────────────
    const busyRef = useRef(false);
    const withBusy = useCallback(async (fn) => {
        if (busyRef.current) return;
        busyRef.current = true; setBusy(true);
        try { await fn(); } finally { busyRef.current = false; setBusy(false); }
    }, []);

    const handleRotateCW  = useCallback(() => withBusy(async () => { const r = await engineApi.rotatePage(pageNode.id, 90);  setLocalRotation(r?.page?.rotation ?? (v => (v+90)%360));  if (onDocumentChanged) await onDocumentChanged(); }), [pageNode.id, withBusy, onDocumentChanged]);
    const handleRotateCCW = useCallback(() => withBusy(async () => { const r = await engineApi.rotatePage(pageNode.id, -90); setLocalRotation(r?.page?.rotation ?? (v => (v-90+360)%360)); if (onDocumentChanged) await onDocumentChanged(); }), [pageNode.id, withBusy, onDocumentChanged]);
    const handleDelete    = useCallback(() => { if (totalPages <= 1) { alert('Cannot delete the last page.'); return; } if (!window.confirm(`Delete page ${pageIndex + 1}?`)) return; withBusy(async () => { await engineApi.deletePage(pageNode.id); if (onDocumentChanged) await onDocumentChanged(); }); }, [pageNode.id, pageIndex, totalPages, withBusy, onDocumentChanged]);
    const handleMoveUp    = useCallback(() => withBusy(async () => { await engineApi.movePage(pageNode.id, pageIndex-1); if (onDocumentChanged) await onDocumentChanged(); }), [pageNode.id, pageIndex, withBusy, onDocumentChanged]);
    const handleMoveDown  = useCallback(() => withBusy(async () => { await engineApi.movePage(pageNode.id, pageIndex+1); if (onDocumentChanged) await onDocumentChanged(); }), [pageNode.id, pageIndex, withBusy, onDocumentChanged]);

    const handleCropConfirm = useCallback(() => {
        const rect = committedRects[0];
        if (!rect) return;
        withBusy(async () => {
            await engineApi.cropPage(pageNode.id, rect.x, rect.y, rect.width, rect.height);
            clearSelection();
            if (onDocumentChanged) await onDocumentChanged();
        });
    }, [pageNode.id, withBusy, onDocumentChanged, clearSelection, committedRects]);

    const handleCropCancel = useCallback(() => {
        clearSelection();
    }, [clearSelection]);

    const handleTextClick = useCallback(async (e) => {
        if (!overlayRef.current) return;
        const r = overlayRef.current.getBoundingClientRect();
        const x = (e.clientX - r.left) / scale, y = (e.clientY - r.top) / scale;
        const text = window.prompt('Enter text:');
        if (!text) return;
        try {
            const res = await engineApi.addTextAnnotation(pageNode.id, text, x, y);
            if (res?.node) setAnnotations(p => [...p, res.node]);
            onAnnotationAdded?.();
        } catch (err) { console.error(err); alert('Failed: ' + err.message); }
    }, [scale, pageNode.id, onAnnotationAdded]);

    // ── Derived Display & Masking Variables ───────────────────────────────────
    const isDragTool = activeTool === TOOLS.HIGHLIGHT || activeTool === TOOLS.REDACT
                    || activeTool === TOOLS.SELECT   || activeTool === TOOLS.CROP;

    const displayRects = liveRects.length > 0 ? liveRects : committedRects;

    const selColor  = activeTool === TOOLS.REDACT ? 'rgba(0,0,0,0.6)'
                    : activeTool === TOOLS.SELECT  ? 'rgba(52,152,219,0.3)'
                    : activeTool === TOOLS.CROP    ? 'rgba(0,0,0,0)'
                    : 'rgba(255,255,0,0.4)';
    const selBorder = activeTool === TOOLS.REDACT ? '2px solid #333'
                    : activeTool === TOOLS.SELECT  ? 'none'
                    : activeTool === TOOLS.CROP    ? '2px solid #f39c12'
                    : '2px solid #cccc00';

    const cropRect = activeTool === TOOLS.CROP && committedRects.length > 0
        ? committedRects[0]
        : null;

    // Masking values
    const cropBox = pageNode.crop_box;
    const isCroppedView = cropBox && typeof cropBox.width === 'number';

    const outerWidth   = isCroppedView ? cropBox.width * scale : fullDimensions.width;
    const outerHeight  = isCroppedView ? cropBox.height * scale : fullDimensions.height;
    const innerOffsetX = isCroppedView ? -(cropBox.x * scale) : 0;
    const innerOffsetY = isCroppedView ? -(cropBox.y * scale) : 0;

    return (
        <div
            style={{
                position: 'relative', width: `${outerWidth}px`, height: `${outerHeight}px`,
                flexShrink: 0, backgroundColor: 'white', margin: '20px auto', 
                overflow: isCroppedView ? 'hidden' : 'visible',
                boxShadow: hovered ? '0 6px 28px rgba(0,0,0,0.35)' : '0 4px 16px rgba(0,0,0,0.25)',
                transition: 'box-shadow 0.18s ease', opacity: busy ? 0.7 : 1,
            }}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
        >
            {/* Inner Wrapper (Retains full dimensions, shifted by mask offsets) */}
            <div style={{
                position: 'absolute',
                top: `${innerOffsetY}px`, left: `${innerOffsetX}px`,
                width: `${fullDimensions.width}px`, height: `${fullDimensions.height}px`,
            }}>
                <canvas ref={canvasRef} style={{ position: 'absolute', top: 0, left: 0, width: `${fullDimensions.width}px`, height: `${fullDimensions.height}px`, pointerEvents: 'none' }} />

                <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 5, overflow: 'hidden' }}>
                    {annotations.map(child => <NodeOverlay key={child.id} node={child} scale={scale} />)}
                </div>

                {cropRect && (
                    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 8 }}>
                        <div style={{ position: 'absolute', left: 0, top: 0, right: 0, height: `${cropRect.y * scale}px`, backgroundColor: 'rgba(0,0,0,0.45)' }} />
                        <div style={{ position: 'absolute', left: 0, bottom: 0, right: 0, top: `${(cropRect.y + cropRect.height) * scale}px`, backgroundColor: 'rgba(0,0,0,0.45)' }} />
                        <div style={{ position: 'absolute', left: 0, top: `${cropRect.y * scale}px`, width: `${cropRect.x * scale}px`, height: `${cropRect.height * scale}px`, backgroundColor: 'rgba(0,0,0,0.45)' }} />
                        <div style={{ position: 'absolute', right: 0, top: `${cropRect.y * scale}px`, left: `${(cropRect.x + cropRect.width) * scale}px`, height: `${cropRect.height * scale}px`, backgroundColor: 'rgba(0,0,0,0.45)' }} />
                    </div>
                )}

                <div
                    ref={overlayRef}
                    style={{ position: 'absolute', inset: 0, cursor: TOOL_CURSORS[activeTool] || 'default', userSelect: 'none', zIndex: 10 }}
                    onClick={activeTool === TOOLS.TEXT ? handleTextClick : handlers.onClick}
                    onMouseDown={isDragTool ? handlers.onMouseDown : undefined}
                    onMouseMove={isDragTool ? handlers.onMouseMove : undefined}
                    onMouseUp={isDragTool   ? handlers.onMouseUp   : undefined}
                    onMouseLeave={isDragTool ? handlers.onMouseLeave : undefined}
                >
                    {displayRects.map((rect, i) => (
                        <div key={i} style={{
                            position: 'absolute',
                            left: `${rect.x * scale}px`, top: `${rect.y * scale}px`,
                            width: `${rect.width * scale}px`, height: `${rect.height * scale}px`,
                            backgroundColor: selColor, border: selBorder,
                            pointerEvents: 'none', borderRadius: '1px',
                            boxSizing: 'border-box',
                        }} />
                    ))}
                </div>

                {cropRect && (
                    <div style={{
                        position: 'absolute',
                        bottom: `${(fullDimensions.height - (cropRect.y + cropRect.height) * scale) + 8}px`,
                        left: '50%', transform: 'translateX(-50%)',
                        display: 'flex', gap: '8px', zIndex: 30, pointerEvents: 'auto',
                    }}>
                        <button
                            onClick={handleCropConfirm}
                            style={{ padding: '6px 16px', backgroundColor: '#27ae60', color: 'white', border: 'none', borderRadius: '5px', fontWeight: '700', fontSize: '13px', cursor: 'pointer', boxShadow: '0 2px 8px rgba(0,0,0,0.4)' }}
                        >✓ Apply Crop</button>
                        <button
                            onClick={handleCropCancel}
                            style={{ padding: '6px 16px', backgroundColor: '#c0392b', color: 'white', border: 'none', borderRadius: '5px', fontWeight: '700', fontSize: '13px', cursor: 'pointer', boxShadow: '0 2px 8px rgba(0,0,0,0.4)' }}
                        >✕ Cancel</button>
                    </div>
                )}
            </div>

            {hovered && !cropRect && <PageControls pageIndex={pageIndex} totalPages={totalPages} onRotateCW={handleRotateCW} onRotateCCW={handleRotateCCW} onDelete={handleDelete} onMoveUp={handleMoveUp} onMoveDown={handleMoveDown} />}

            <div style={{ position: 'absolute', bottom: '8px', right: '10px', backgroundColor: 'rgba(0,0,0,0.45)', color: 'white', fontSize: '11px', fontWeight: '600', padding: '2px 7px', borderRadius: '10px', pointerEvents: 'none', zIndex: 20 }}>
                {pageIndex + 1}
            </div>

            {busy && (
                <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(0,0,0,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
                    <div style={{ backgroundColor: 'rgba(15,23,35,0.9)', color: 'white', fontSize: '13px', fontWeight: '600', padding: '8px 18px', borderRadius: '6px' }}>Working…</div>
                </div>
            )}

            <CopyToast visible={showToast} />
        </div>
    );
};