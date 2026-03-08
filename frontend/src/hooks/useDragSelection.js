import { useRef, useState, useCallback, useEffect } from 'react';
import { TOOLS } from '../tools';

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

// ── Hook ──────────────────────────────────────────────────────────────────────

export const useDragSelection = ({
    overlayRef,
    pageChars,
    scale,
    activeTool,
    metadata,
    onAction
}) => {
    const liveRectsRef = useRef([]);
    const committedRectsRef = useRef([]);
    const [selVersion, setSelVersion] = useState(0);
    const bumpSel = useCallback(() => setSelVersion(v => v + 1), []);

    const isDragging = useRef(false);
    const wasDragging = useRef(false);
    const startPos = useRef(null);
    const startIdx = useRef(-1);

    // Keep onAction fresh without triggering dependency changes in mouse handlers
    const onActionRef = useRef(onAction);
    useEffect(() => { onActionRef.current = onAction; }, [onAction]);

    const clearSelection = useCallback(() => {
        committedRectsRef.current = [];
        liveRectsRef.current = [];
        bumpSel();
    }, [bumpSel]);

    // Clear stale selection when tool changes
    useEffect(() => {
        if (activeTool !== TOOLS.SELECT) {
            clearSelection();
        }
    }, [activeTool, clearSelection]);

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
    }, [scale, overlayRef]);

    const onMouseDown = useCallback((e) => {
        e.preventDefault();
        const pt = toPdf(e);
        if (!pt) return;
        isDragging.current = true;
        wasDragging.current = false;
        startPos.current = pt;
        startIdx.current = nearestCharIdx(pt);
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

        if (activeTool === TOOLS.CROP) {
            const W = metadata?.width || 612;
            const H = metadata?.height || 792;
            liveRectsRef.current = [{
                x: Math.max(0, Math.min(startPos.current.x, cur.x)),
                y: Math.max(0, Math.min(startPos.current.y, cur.y)),
                width: Math.min(Math.abs(cur.x - startPos.current.x), W),
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
    }, [toPdf, nearestCharIdx, pageChars, bumpSel, activeTool, metadata]);

    const onMouseUp = useCallback((e) => {
        if (!isDragging.current) return;
        isDragging.current = false;

        const rects = liveRectsRef.current;
        const r = rects[0];

        if (!r || (r.width < 4 && r.height < 4)) {
            liveRectsRef.current = [];
            bumpSel();
            return;
        }

        committedRectsRef.current = rects;
        liveRectsRef.current = [];
        bumpSel();

        if (onActionRef.current) {
            onActionRef.current(rects);
        }
    }, [bumpSel]);

    const onMouseLeave = useCallback((e) => {
        if (isDragging.current) onMouseUp(e);
    }, [onMouseUp]);

    const onClick = useCallback(() => {
        if (wasDragging.current) {
            wasDragging.current = false;
            return;
        }
        if (activeTool === TOOLS.SELECT && committedRectsRef.current.length > 0) {
            clearSelection();
        }
    }, [activeTool, clearSelection]);

    return {
        liveRects: liveRectsRef.current,
        committedRects: committedRectsRef.current,
        clearSelection,
        setCommittedRects: (rects) => {
            committedRectsRef.current = rects;
            bumpSel();
        },
        handlers: {
            onMouseDown,
            onMouseMove,
            onMouseUp,
            onMouseLeave,
            onClick
        }
    };
};