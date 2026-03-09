// components/PageRenderer.jsx
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { engineApi } from '../api/client';
import { TOOLS, TOOL_CURSORS } from '../tools';
import theme from '../theme';
import { PageControls } from './PageControls';
import { NodeOverlay }  from './NodeOverlay';
import { usePdfCanvas } from '../hooks/usePdfCanvas';
import { usePageChars } from '../hooks/usePageChars';
import { useDragSelection } from '../hooks/useDragSelection';

const t = theme;

const CopyToast = ({ visible }) => (
    <div style={{
        position: 'fixed', bottom: '52px', left: '50%',
        transform: `translateX(-50%) translateY(${visible ? '0' : '8px'})`,
        background: t.colors.bgRaised,
        color: t.colors.textPrimary,
        border: `1px solid ${t.colors.borderMid}`,
        padding: '7px 16px', borderRadius: t.radius.md,
        fontSize: '12px', fontWeight: '500', fontFamily: t.fonts.ui,
        opacity: visible ? 1 : 0,
        transition: 'opacity 0.18s ease, transform 0.18s ease',
        zIndex: 9999, boxShadow: t.shadow.md,
        display: 'flex', alignItems: 'center', gap: '6px',
        pointerEvents: 'none',
    }}>
        <span style={{ color: t.colors.success }}>✓</span> Copied to clipboard
    </div>
);

export const PageRenderer = ({
    pageNode, pdfDoc, pageIndex, totalPages, scale = 1.5,
    activeTool, onAnnotationAdded, onDocumentChanged, onTextSelected,
}) => {
    const overlayRef        = useRef(null);
    const clearSelectionRef = useRef(null);
    const toastTimer        = useRef(null);
    const busyRef           = useRef(false);

    const [annotations,   setAnnotations]   = useState([]);
    const [hovered,       setHovered]       = useState(false);
    const [busy,          setBusy]          = useState(false);
    const [localRotation, setLocalRotation] = useState(pageNode.rotation ?? 0);
    const [showToast,     setShowToast]     = useState(false);

    useEffect(() => { if (typeof pageNode.rotation === 'number') setLocalRotation(pageNode.rotation); }, [pageNode.rotation, pageNode.id]);
    useEffect(() => { setAnnotations(pageNode.children || []); }, [pageNode.children]);

    const { canvasRef, fullDimensions } = usePdfCanvas({ pdfDoc, pageNode, pageIndex, scale, localRotation });
    const { pageChars } = usePageChars({ pageNodeId: pageNode.id, localRotation, metadata: pageNode.metadata });

    const triggerToast = useCallback(() => {
        setShowToast(true);
        clearTimeout(toastTimer.current);
        toastTimer.current = setTimeout(() => setShowToast(false), 2000);
    }, []);

    const handleAction = useCallback(async (rects) => {
        if (activeTool === TOOLS.CROP) return;

        if (activeTool === TOOLS.SELECT) {
            const tol = 4;
            const sel = pageChars.filter(c => {
                const cx = c.x + c.width / 2, cy = c.y + c.height / 2;
                return rects.some(r => cx >= r.x - tol && cx <= r.x + r.width + tol && cy >= r.y - tol && cy <= r.y + r.height + tol);
            }).sort((a, b) => Math.abs(a.y - b.y) > 5 ? a.y - b.y : a.x - b.x);

            if (!sel.length) return;
            let text = sel[0].text;
            for (let i = 1; i < sel.length; i++) {
                const p = sel[i - 1], c = sel[i];
                const avgH = (p.height + c.height) / 2;
                text += Math.abs((p.y + p.height / 2) - (c.y + c.height / 2)) > avgH * 0.75 ? '\n' + c.text : (c.x - (p.x + p.width) > p.width * 0.4 ? ' ' : '') + c.text;
            }
            try { await navigator.clipboard.writeText(text); triggerToast(); onTextSelected?.(text); }
            catch { window.prompt('Copy (Ctrl+C):', text); onTextSelected?.(text); }
            return;
        }

        try {
            let results = [];
            if (activeTool === TOOLS.HIGHLIGHT) {
                const res = await fetch('http://localhost:8000/api/annotations/highlight', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ page_id: pageNode.id, rects: rects.map(r => ({ x: r.x, y: r.y, width: r.width, height: r.height })) }),
                }).then(r => r.json());
                results = [res];
            } else if (activeTool === TOOLS.REDACT) {
                const res = await engineApi.applyRedaction(pageNode.id, rects);
                results = [res];
            }
            const nodes = results.flatMap(r => r?.node ? [r.node] : r?.nodes ?? []);
            if (nodes.length) { setAnnotations(p => [...p, ...nodes]); onAnnotationAdded?.(); }
            if (clearSelectionRef.current && activeTool !== TOOLS.CROP) clearSelectionRef.current();
        } catch (e) { console.error(e); alert('Failed: ' + e.message); }
    }, [activeTool, pageNode.id, pageChars, triggerToast, onAnnotationAdded]);

    const { liveRects, committedRects, clearSelection, handlers } = useDragSelection({
        overlayRef, pageChars, scale, activeTool, metadata: pageNode.metadata, onAction: handleAction,
    });

    useEffect(() => { clearSelectionRef.current = clearSelection; }, [clearSelection]);

    const withBusy = useCallback(async (fn) => {
        if (busyRef.current) return;
        busyRef.current = true; setBusy(true);
        try { await fn(); } finally { busyRef.current = false; setBusy(false); }
    }, []);

    const handleRotateCW  = useCallback(() => withBusy(async () => { const r = await engineApi.rotatePage(pageNode.id, 90);  setLocalRotation(r?.page?.rotation ?? (v => (v + 90) % 360));  await onDocumentChanged?.(); }), [pageNode.id, withBusy, onDocumentChanged]);
    const handleRotateCCW = useCallback(() => withBusy(async () => { const r = await engineApi.rotatePage(pageNode.id, -90); setLocalRotation(r?.page?.rotation ?? (v => (v - 90 + 360) % 360)); await onDocumentChanged?.(); }), [pageNode.id, withBusy, onDocumentChanged]);
    const handleDelete    = useCallback(() => { if (totalPages <= 1) return alert('Cannot delete the last page.'); if (!window.confirm(`Delete page ${pageIndex + 1}?`)) return; withBusy(async () => { await engineApi.deletePage(pageNode.id); await onDocumentChanged?.(); }); }, [pageNode.id, pageIndex, totalPages, withBusy, onDocumentChanged]);
    const handleMoveUp    = useCallback(() => withBusy(async () => { await engineApi.movePage(pageNode.id, pageIndex - 1); await onDocumentChanged?.(); }), [pageNode.id, pageIndex, withBusy, onDocumentChanged]);
    const handleMoveDown  = useCallback(() => withBusy(async () => { await engineApi.movePage(pageNode.id, pageIndex + 1); await onDocumentChanged?.(); }), [pageNode.id, pageIndex, withBusy, onDocumentChanged]);

    const handleCropConfirm = useCallback(() => {
        const rect = committedRects[0];
        if (!rect) return;
        withBusy(async () => { await engineApi.cropPage(pageNode.id, rect.x, rect.y, rect.width, rect.height); clearSelection(); await onDocumentChanged?.(); });
    }, [pageNode.id, withBusy, onDocumentChanged, clearSelection, committedRects]);

    const handleTextClick = useCallback(async (e) => {
        if (!overlayRef.current) return;
        const r = overlayRef.current.getBoundingClientRect();
        const text = window.prompt('Enter text:');
        if (!text) return;
        try {
            const res = await engineApi.addTextAnnotation(pageNode.id, text, (e.clientX - r.left) / scale, (e.clientY - r.top) / scale);
            if (res?.node) setAnnotations(p => [...p, res.node]);
            onAnnotationAdded?.();
        } catch (err) { alert('Failed: ' + err.message); }
    }, [scale, pageNode.id, onAnnotationAdded]);

    const isDragTool   = [TOOLS.HIGHLIGHT, TOOLS.REDACT, TOOLS.SELECT, TOOLS.CROP].includes(activeTool);
    const displayRects = liveRects.length > 0 ? liveRects : committedRects;
    const cropRect     = activeTool === TOOLS.CROP && committedRects.length > 0 ? committedRects[0] : null;

    const selColor = {
        [TOOLS.REDACT]:    t.colors.redactBg,
        [TOOLS.SELECT]:    t.colors.selectBg,
        [TOOLS.HIGHLIGHT]: t.colors.highlightBg,
        [TOOLS.CROP]:      'rgba(0,0,0,0)',
    }[activeTool] ?? 'rgba(255,255,0,0.3)';

    const cropBox      = pageNode.crop_box;
    const isCropped    = cropBox && typeof cropBox.width === 'number';
    const outerW       = isCropped ? cropBox.width * scale  : fullDimensions.width;
    const outerH       = isCropped ? cropBox.height * scale : fullDimensions.height;
    const innerX       = isCropped ? -(cropBox.x * scale) : 0;
    const innerY       = isCropped ? -(cropBox.y * scale) : 0;

    return (
        <div
            style={{
                position: 'relative', width: outerW, height: outerH,
                flexShrink: 0, background: 'white', margin: '0 auto 24px',
                overflow: isCropped ? 'hidden' : 'visible',
                boxShadow: hovered ? t.shadow.pageHov : t.shadow.page,
                borderRadius: '1px',
                transition: 'box-shadow 0.18s ease',
                opacity: busy ? 0.75 : 1,
            }}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
        >
            {hovered && !cropRect && (
                <PageControls pageIndex={pageIndex} totalPages={totalPages}
                    onRotateCW={handleRotateCW} onRotateCCW={handleRotateCCW}
                    onDelete={handleDelete} onMoveUp={handleMoveUp} onMoveDown={handleMoveDown} />
            )}

            <div style={{ position: 'absolute', top: innerY, left: innerX, width: fullDimensions.width, height: fullDimensions.height }}>
                <canvas ref={canvasRef} style={{ position: 'absolute', top: 0, left: 0, width: fullDimensions.width, height: fullDimensions.height, pointerEvents: 'none' }} />

                <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 5, overflow: 'hidden' }}>
                    {annotations.map(child => <NodeOverlay key={child.id} node={child} scale={scale} />)}
                </div>

                {cropRect && (
                    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 8 }}>
                        {[
                            { left: 0, top: 0, right: 0, height: `${cropRect.y * scale}px` },
                            { left: 0, bottom: 0, right: 0, top: `${(cropRect.y + cropRect.height) * scale}px` },
                            { left: 0, top: `${cropRect.y * scale}px`, width: `${cropRect.x * scale}px`, height: `${cropRect.height * scale}px` },
                            { right: 0, top: `${cropRect.y * scale}px`, left: `${(cropRect.x + cropRect.width) * scale}px`, height: `${cropRect.height * scale}px` },
                        ].map((s, i) => <div key={i} style={{ position: 'absolute', background: 'rgba(0,0,0,0.5)', ...s }} />)}
                    </div>
                )}

                <div
                    ref={overlayRef}
                    style={{ position: 'absolute', inset: 0, cursor: TOOL_CURSORS[activeTool] ?? 'default', userSelect: 'none', zIndex: 10 }}
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
                            background: selColor,
                            border: activeTool === TOOLS.CROP ? `2px dashed ${t.colors.crop}` : 'none',
                            pointerEvents: 'none', borderRadius: 1, boxSizing: 'border-box',
                        }} />
                    ))}
                </div>

                {cropRect && (
                    <div style={{ position: 'absolute', bottom: `${fullDimensions.height - (cropRect.y + cropRect.height) * scale + 10}px`, left: '50%', transform: 'translateX(-50%)', display: 'flex', gap: '6px', zIndex: 30 }}>
                        <button onClick={handleCropConfirm} style={{ height: 28, padding: '0 14px', background: t.colors.success, color: '#0a1f17', border: 'none', borderRadius: t.radius.sm, fontWeight: '600', fontSize: '12px', cursor: 'pointer', fontFamily: t.fonts.ui }}>
                            ✓ Apply
                        </button>
                        <button onClick={clearSelection} style={{ height: 28, padding: '0 12px', background: t.colors.bgRaised, color: t.colors.textSecondary, border: `1px solid ${t.colors.border}`, borderRadius: t.radius.sm, fontSize: '12px', cursor: 'pointer', fontFamily: t.fonts.ui }}>
                            Cancel
                        </button>
                    </div>
                )}
            </div>

            {/* Page number badge */}
            <div style={{ position: 'absolute', bottom: 7, right: 9, background: 'rgba(0,0,0,0.38)', backdropFilter: 'blur(4px)', color: 'rgba(255,255,255,0.8)', fontSize: 10, fontWeight: 600, fontFamily: t.fonts.mono, padding: '2px 6px', borderRadius: t.radius.pill, pointerEvents: 'none', zIndex: 20 }}>
                {pageIndex + 1}
            </div>

            {busy && (
                <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
                    <div style={{ background: t.colors.bgSurface, color: t.colors.textPrimary, fontSize: 12, fontWeight: 600, padding: '7px 16px', borderRadius: t.radius.md, border: `1px solid ${t.colors.border}`, fontFamily: t.fonts.ui }}>
                        Working…
                    </div>
                </div>
            )}

            <CopyToast visible={showToast} />
        </div>
    );
};