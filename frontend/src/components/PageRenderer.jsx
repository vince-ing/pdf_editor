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
                <div style={{ ...style, border: hovered ? '1px solid #3498db' : '1px solid transparent', cursor: 'pointer', borderRadius: '2px', pointerEvents: 'auto' }}
                    onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}>
                    <span style={{ fontSize: `${node.font_size * scale}px`, fontFamily: node.font_family, color: node.color || '#000' }}>
                        {node.text_content}
                    </span>
                </div>
            );
        case 'highlight':
            if (node.color === '#000000') return <div style={{ ...style, backgroundColor: '#000000', opacity: 1.0, borderRadius: '2px', pointerEvents: 'none' }} />;
            return <div style={{ ...style, backgroundColor: node.color || '#FFFF00', opacity: node.opacity ?? 0.5, borderRadius: '2px', pointerEvents: 'none' }} />;
        default:
            return null;
    }
};

// ── helpers ───────────────────────────────────────────────────────────────────

function lineBBox(lineChars) {
    const minX = Math.min(...lineChars.map(c => c.x));
    const minY = Math.min(...lineChars.map(c => c.y));
    const maxX = Math.max(...lineChars.map(c => c.x + c.width));
    const maxY = Math.max(...lineChars.map(c => c.y + c.height));
    return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
}

function buildLineRects(chars) {
    if (!chars.length) return [];
    const rects = [];
    let line = [chars[0]];
    for (let i = 1; i < chars.length; i++) {
        const prev = line[line.length - 1];
        const curr = chars[i];
        const avgH = (prev.height + curr.height) / 2;
        if (Math.abs((prev.y + prev.height / 2) - (curr.y + curr.height / 2)) < avgH * 0.75) {
            line.push(curr);
        } else {
            rects.push(lineBBox(line));
            line = [curr];
        }
    }
    if (line.length) rects.push(lineBBox(line));
    return rects;
}

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

// ── Page controls ─────────────────────────────────────────────────────────────

const PageControls = ({ pageIndex, totalPages, onRotateCW, onRotateCCW, onDelete, onMoveUp, onMoveDown }) => (
    <div style={{
        position: 'absolute', top: '10px', left: '50%', transform: 'translateX(-50%)',
        display: 'flex', gap: '6px', alignItems: 'center',
        backgroundColor: 'rgba(15,23,35,0.88)', backdropFilter: 'blur(6px)',
        borderRadius: '8px', padding: '5px 10px', zIndex: 30,
        boxShadow: '0 2px 12px rgba(0,0,0,0.5)', border: '1px solid rgba(255,255,255,0.1)',
        pointerEvents: 'auto', whiteSpace: 'nowrap',
    }}>
        <CtrlBtn onClick={onMoveUp}    disabled={pageIndex === 0}             title="Move up"    color="#546e7a">↑</CtrlBtn>
        <CtrlBtn onClick={onMoveDown}  disabled={pageIndex >= totalPages - 1} title="Move down"  color="#546e7a">↓</CtrlBtn>
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
        color: disabled ? '#3d5166' : 'white', fontSize: '14px', fontWeight: '700',
        cursor: disabled ? 'not-allowed' : 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1, padding: 0,
    }}>{children}</button>
);

const Divider = () => <div style={{ width: '1px', height: '16px', backgroundColor: 'rgba(255,255,255,0.12)' }} />;

// ── PageRenderer ─────────────────────────────────────────────────────────────

export const PageRenderer = ({
    pageNode, pdfDoc, pageIndex, totalPages, scale = 1.5,
    activeTool, onAnnotationAdded, onDocumentChanged,
}) => {
    const canvasRef  = useRef(null);
    const overlayRef = useRef(null);

    const [annotations,   setAnnotations]   = useState([]);
    const [rawChars,      setRawChars]      = useState([]);  // always in original PDF space
    const [pageChars,     setPageChars]     = useState([]);  // rotated to match current render
    const [hovered,       setHovered]       = useState(false);
    const [busy,          setBusy]          = useState(false);
    const [localRotation, setLocalRotation] = useState(pageNode.rotation ?? 0);
    const [showToast,     setShowToast]     = useState(false);
    const [dimensions,    setDimensions]    = useState({
        width:  (pageNode.metadata?.width  || 612) * scale,
        height: (pageNode.metadata?.height || 792) * scale,
    });

    // ── All selection state lives entirely in refs so there are zero
    //    stale-closure or batching issues. A single `selVersion` integer
    //    is the only piece of React state — incrementing it forces a
    //    re-render whenever selection changes.
    const liveRectsRef      = useRef([]);   // rects shown during active drag
    const committedRectsRef = useRef([]);   // rects shown after mouse-up
    const [selVersion, setSelVersion] = useState(0);
    const bumpSel = useCallback(() => setSelVersion(v => v + 1), []);

    // drag tracking
    const isDragging  = useRef(false);
    const wasDragging = useRef(false); // lets onClick know a drag just finished
    const startPos    = useRef(null);
    const startIdx    = useRef(-1);

    const toastTimer = useRef(null);

    // ── Chars — fetch raw (original PDF space), re-transform on rotation ─────
    useEffect(() => {
        let alive = true;
        fetch(`http://localhost:8000/api/pages/${pageNode.id}/chars`)
            .then(r => r.json())
            .then(data => {
                if (!alive || data.status !== 'success') return;
                setRawChars(data.chars || []);
            })
            .catch(err => console.error('[PageRenderer] chars fetch error:', err));
        return () => { alive = false; };
    }, [pageNode.id]);

    // Re-derive pageChars whenever rawChars or localRotation changes.
    // PyMuPDF returns coords in the original (unrotated) PDF coordinate system
    // (origin top-left, y increases downward). When the page is rotated we
    // must transform each char bbox so hit-testing stays aligned with what the
    // user actually sees on the canvas.
    useEffect(() => {
        if (!rawChars.length) { setPageChars([]); return; }

        // Page dimensions in the *original* (unrotated) orientation
        const W = pageNode.metadata?.width  || 612;
        const H = pageNode.metadata?.height || 792;

        const transformed = rawChars.map(c => {
            let { x, y, width, height } = c;
            switch (((localRotation % 360) + 360) % 360) {
                case 90: {
                    // (x,y) → (H - y - h,  x)  then swap w/h
                    const nx = H - y - height;
                    const ny = x;
                    return { ...c, x: nx, y: ny, width: height, height: width };
                }
                case 180: {
                    // (x,y) → (W - x - w,  H - y - h)
                    return { ...c, x: W - x - width, y: H - y - height };
                }
                case 270: {
                    // (x,y) → (y,  W - x - w)  then swap w/h
                    const nx = y;
                    const ny = W - x - width;
                    return { ...c, x: nx, y: ny, width: height, height: width };
                }
                default:
                    return c; // 0° — no transform needed
            }
        });

        // Sort into reading order for the *rotated* orientation
        transformed.sort((a, b) =>
            Math.abs(a.y - b.y) > 5 ? a.y - b.y : a.x - b.x
        );
        setPageChars(transformed);
    }, [rawChars, localRotation, pageNode.metadata]);

    useEffect(() => {
        if (typeof pageNode.rotation === 'number') setLocalRotation(pageNode.rotation);
    }, [pageNode.rotation, pageNode.id]);

    useEffect(() => { setAnnotations(pageNode.children || []); }, [pageNode.children]);

    useEffect(() => {
        if (activeTool !== TOOLS.SELECT) {
            committedRectsRef.current = [];
            liveRectsRef.current = [];
            bumpSel();
        }
    }, [activeTool, bumpSel]);

    // Clear stale selection whenever the page is rotated
    useEffect(() => {
        committedRectsRef.current = [];
        liveRectsRef.current = [];
        bumpSel();
    }, [localRotation, bumpSel]);

    // ── Canvas render ─────────────────────────────────────────────────────────
    useEffect(() => {
        if (!pdfDoc) return;
        let alive = true;
        let renderTask = null;
        const go = async () => {
            try {
                const pageNum = (pageNode.page_number ?? pageIndex) + 1;
                if (pageNum < 1 || pageNum > pdfDoc.numPages) return;
                const page = await pdfDoc.getPage(pageNum);
                if (!alive) return;
                const dpr = window.devicePixelRatio || 1;
                const vp  = page.getViewport({ scale: scale * dpr, rotation: localRotation });
                const canvas = canvasRef.current;
                if (!canvas) return;
                canvas.width  = vp.width;
                canvas.height = vp.height;
                const cssW = vp.width / dpr, cssH = vp.height / dpr;
                canvas.style.width = `${cssW}px`; canvas.style.height = `${cssH}px`;
                setDimensions({ width: cssW, height: cssH });
                renderTask = page.render({ canvasContext: canvas.getContext('2d'), viewport: vp });
                await renderTask.promise;
            } catch (err) { if (err?.name !== 'RenderingCancelledException') console.error(err); }
        };
        go();
        return () => { alive = false; renderTask?.cancel(); };
    }, [pdfDoc, pageIndex, localRotation, scale]);

    // ── Page commands ─────────────────────────────────────────────────────────
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

    // ── Selection helpers ─────────────────────────────────────────────────────

    const nearestCharIdx = useCallback((pt) => {
        if (!pageChars.length) return -1;
        let best = -1, bestD = 60 * 60;
        pageChars.forEach((c, i) => {
            const dx = (c.x + c.width/2) - pt.x, dy = (c.y + c.height/2) - pt.y;
            const d = dx*dx + dy*dy;
            if (d < bestD) { bestD = d; best = i; }
        });
        return best;
    }, [pageChars]);

    const toPdf = useCallback((e) => {
        if (!overlayRef.current) return null;
        const r = overlayRef.current.getBoundingClientRect();
        return { x: (e.clientX - r.left) / scale, y: (e.clientY - r.top) / scale };
    }, [scale]);

    // ── Mouse handlers (stable — no deps that go stale) ───────────────────────

    const onMouseDown = useCallback((e) => {
        e.preventDefault();
        const pt = toPdf(e);
        if (!pt) return;
        isDragging.current  = true;
        wasDragging.current = false;
        startPos.current    = pt;
        startIdx.current    = nearestCharIdx(pt);
        liveRectsRef.current = [];
        bumpSel();
    }, [toPdf, nearestCharIdx, bumpSel]);

    const onMouseMove = useCallback((e) => {
        if (!isDragging.current || !startPos.current) return;
        const cur = toPdf(e);
        if (!cur) return;

        const dx = Math.abs(cur.x - startPos.current.x);
        const dy = Math.abs(cur.y - startPos.current.y);
        if (dx < 3 && dy < 3) return;

        wasDragging.current = true;

        // Crop: raw box clamped to page bounds, no text snapping
        if (activeTool === TOOLS.CROP) {
            const W = pageNode.metadata?.width  || 612;
            const H = pageNode.metadata?.height || 792;
            liveRectsRef.current = [{
                x:      Math.max(0, Math.min(startPos.current.x, cur.x)),
                y:      Math.max(0, Math.min(startPos.current.y, cur.y)),
                width:  Math.min(Math.abs(cur.x - startPos.current.x), W),
                height: Math.min(Math.abs(cur.y - startPos.current.y), H),
            }];
            bumpSel();
            return;
        }

        if (startIdx.current !== -1 && pageChars.length > 0) {
            const endIdx = nearestCharIdx(cur);
            if (endIdx !== -1) {
                const lo = Math.min(startIdx.current, endIdx);
                const hi = Math.max(startIdx.current, endIdx);
                liveRectsRef.current = buildLineRects(pageChars.slice(lo, hi + 1));
                bumpSel();
                return;
            }
        }
        liveRectsRef.current = [];
        bumpSel();
    }, [toPdf, nearestCharIdx, pageChars, bumpSel, activeTool, pageNode.metadata]);

    const onMouseUp = useCallback((e) => {
        if (!isDragging.current) return;
        isDragging.current = false;

        const rects = liveRectsRef.current;
        const r = rects[0];

        // Discard tiny accidental drags
        if (!r || (r.width < 4 && r.height < 4)) {
            liveRectsRef.current = [];
            bumpSel();
            return;
        }

        // Commit the selection so it persists
        committedRectsRef.current = rects;
        liveRectsRef.current = [];
        bumpSel();

        // Handle tool action
        handleAction(rects);
    }, [bumpSel]); // eslint-disable-line react-hooks/exhaustive-deps
    // NOTE: handleAction is called via ref below to avoid stale closure

    const handleActionRef = useRef(null);

    const onMouseLeave = useCallback((e) => {
        if (isDragging.current) onMouseUp(e);
    }, [onMouseUp]);

    // ── Action (copy / highlight / redact) ────────────────────────────────────

    const triggerToast = useCallback(() => {
        setShowToast(true);
        clearTimeout(toastTimer.current);
        toastTimer.current = setTimeout(() => setShowToast(false), 2000);
    }, []);

    const handleAction = useCallback(async (rects) => {
        if (activeTool === TOOLS.CROP) {
            // Just store the first rect as the pending crop — confirm button applies it
            committedRectsRef.current = [rects[0]];
            liveRectsRef.current = [];
            bumpSel();
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
            console.log('[action] copying text:', JSON.stringify(text.slice(0, 80)));
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

    // Keep handleAction reachable from the stable onMouseUp via a ref
    handleActionRef.current = handleAction;

    // ── Crop confirm / cancel ─────────────────────────────────────────────────

    const handleCropConfirm = useCallback(() => {
        const rect = committedRectsRef.current[0];
        if (!rect) return;
        withBusy(async () => {
            // Convert from canvas (top-left, y-down, scaled) to PDF space (top-left, y-down, unscaled)
            // The backend CropPageCommand stores in the same top-left space and
            // document_service.py converts to fitz's bottom-left space on export.
            await engineApi.cropPage(pageNode.id, rect.x, rect.y, rect.width, rect.height);
            committedRectsRef.current = [];
            liveRectsRef.current = [];
            bumpSel();
            if (onDocumentChanged) await onDocumentChanged();
        });
    }, [pageNode.id, withBusy, onDocumentChanged, bumpSel]);

    const handleCropCancel = useCallback(() => {
        committedRectsRef.current = [];
        liveRectsRef.current = [];
        bumpSel();
    }, [bumpSel]);

    // ── Click = clear selection (only if no drag just finished) ──────────────
    const handleClick = useCallback(() => {
        if (wasDragging.current) {
            // This click is the tail of a drag — don't clear
            wasDragging.current = false;
            return;
        }
        if (activeTool === TOOLS.SELECT && committedRectsRef.current.length > 0) {
            console.log('[click] clearing committed selection');
            committedRectsRef.current = [];
            bumpSel();
        }
    }, [activeTool, bumpSel]);

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

    // ── Derived display ───────────────────────────────────────────────────────

    const isDragTool = activeTool === TOOLS.HIGHLIGHT || activeTool === TOOLS.REDACT
                    || activeTool === TOOLS.SELECT   || activeTool === TOOLS.CROP;

    // Live drag takes priority; fall back to committed
    const displayRects = liveRectsRef.current.length > 0
        ? liveRectsRef.current
        : committedRectsRef.current;

    const selColor  = activeTool === TOOLS.REDACT ? 'rgba(0,0,0,0.6)'
                    : activeTool === TOOLS.SELECT  ? 'rgba(52,152,219,0.3)'
                    : activeTool === TOOLS.CROP    ? 'rgba(0,0,0,0)'
                    : 'rgba(255,255,0,0.4)';
    const selBorder = activeTool === TOOLS.REDACT ? '2px solid #333'
                    : activeTool === TOOLS.SELECT  ? 'none'
                    : activeTool === TOOLS.CROP    ? '2px solid #f39c12'
                    : '2px solid #cccc00';

    // For the crop tool — the pending crop rect (only ever one rect)
    const cropRect = activeTool === TOOLS.CROP && committedRectsRef.current.length > 0
        ? committedRectsRef.current[0]
        : null;

    return (
        <div
            style={{
                position: 'relative', width: `${dimensions.width}px`, height: `${dimensions.height}px`,
                flexShrink: 0, backgroundColor: 'white', margin: '20px auto', overflow: 'visible',
                boxShadow: hovered ? '0 6px 28px rgba(0,0,0,0.35)' : '0 4px 16px rgba(0,0,0,0.25)',
                transition: 'box-shadow 0.18s ease', opacity: busy ? 0.7 : 1,
            }}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
        >
            <canvas ref={canvasRef} style={{ position: 'absolute', top: 0, left: 0, width: `${dimensions.width}px`, height: `${dimensions.height}px`, pointerEvents: 'none' }} />

            {/* Annotation layer */}
            <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 5, overflow: 'hidden' }}>
                {annotations.map(child => <NodeOverlay key={child.id} node={child} scale={scale} />)}
            </div>

            {/* Crop darkened-outside overlay — shown when a crop rect is committed */}
            {cropRect && (
                <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 8 }}>
                    {/* top */}
                    <div style={{ position: 'absolute', left: 0, top: 0, right: 0, height: `${cropRect.y * scale}px`, backgroundColor: 'rgba(0,0,0,0.45)' }} />
                    {/* bottom */}
                    <div style={{ position: 'absolute', left: 0, bottom: 0, right: 0, top: `${(cropRect.y + cropRect.height) * scale}px`, backgroundColor: 'rgba(0,0,0,0.45)' }} />
                    {/* left */}
                    <div style={{ position: 'absolute', left: 0, top: `${cropRect.y * scale}px`, width: `${cropRect.x * scale}px`, height: `${cropRect.height * scale}px`, backgroundColor: 'rgba(0,0,0,0.45)' }} />
                    {/* right */}
                    <div style={{ position: 'absolute', right: 0, top: `${cropRect.y * scale}px`, left: `${(cropRect.x + cropRect.width) * scale}px`, height: `${cropRect.height * scale}px`, backgroundColor: 'rgba(0,0,0,0.45)' }} />
                </div>
            )}

            {/* Interaction layer */}
            <div
                ref={overlayRef}
                style={{ position: 'absolute', inset: 0, cursor: TOOL_CURSORS[activeTool] || 'default', userSelect: 'none', zIndex: 10 }}
                onClick={activeTool === TOOLS.TEXT ? handleTextClick : handleClick}
                onMouseDown={isDragTool ? onMouseDown : undefined}
                onMouseMove={isDragTool ? onMouseMove : undefined}
                onMouseUp={isDragTool   ? onMouseUp   : undefined}
                onMouseLeave={isDragTool ? onMouseLeave : undefined}
            >
                {/* Selection / crop rects */}
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

            {/* Crop confirm / cancel bar */}
            {cropRect && (
                <div style={{
                    position: 'absolute',
                    bottom: `${(dimensions.height - (cropRect.y + cropRect.height) * scale) + 8}px`,
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