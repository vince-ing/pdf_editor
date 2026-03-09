import { useRef, useState, useCallback, useEffect } from 'react';
import { highlightTool, redactTool, selectTool, cropTool, underlineTool } from '../core/tools/DragTool';

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
    pageId,
    pageChars,
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

    const onActionRef = useRef(onAction);
    useEffect(() => { onActionRef.current = onAction; }, [onAction]);

    const clearSelection = useCallback(() => {
        committedRectsRef.current = [];
        liveRectsRef.current = [];
        bumpSel();
    }, [bumpSel]);

    useEffect(() => {
        if (activeTool !== 'select') {
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

    // Map tool names to the tool instances so we can listen to the right one
    const getActiveToolInstance = useCallback(() => {
        switch(activeTool) {
            case 'highlight': return highlightTool;
            case 'redact': return redactTool;
            case 'select': return selectTool;
            case 'crop': return cropTool;
            case 'underline': return underlineTool;
            default: return null;
        }
    }, [activeTool]);

    useEffect(() => {
        const tool = getActiveToolInstance();
        if (!tool) return;

        const onDown = (ctx) => {
            if (ctx.pageId !== pageId || ctx.originalEvent.button !== 0) return;
            
            // Clear selections on normal click if using select tool
            if (activeTool === 'select' && committedRectsRef.current.length > 0) {
                clearSelection();
            }

            isDragging.current = true;
            wasDragging.current = false;
            startPos.current = { x: ctx.x, y: ctx.y };
            startIdx.current = nearestCharIdx(startPos.current);
            liveRectsRef.current = [];
            bumpSel();
        };

        const onMove = (ctx) => {
            if (!isDragging.current || !startPos.current || ctx.pageId !== pageId) return;
            
            const dx = Math.abs(ctx.x - startPos.current.x);
            const dy = Math.abs(ctx.y - startPos.current.y);
            if (dx < 3 && dy < 3) return;

            wasDragging.current = true;

            if (activeTool === 'crop') {
                const W = metadata?.width || 612;
                const H = metadata?.height || 792;
                liveRectsRef.current = [{
                    x: Math.max(0, Math.min(startPos.current.x, ctx.x)),
                    y: Math.max(0, Math.min(startPos.current.y, ctx.y)),
                    width: Math.min(Math.abs(ctx.x - startPos.current.x), W),
                    height: Math.min(Math.abs(ctx.y - startPos.current.y), H),
                }];
                bumpSel();
                return;
            }

            if (startIdx.current !== -1 && pageChars.length > 0) {
                const endIdx = nearestCharIdx({ x: ctx.x, y: ctx.y });
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
        };

        const onUp = (ctx) => {
            if (!isDragging.current || ctx.pageId !== pageId) return;
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
        };

        const onLeave = (ctx) => {
            if (ctx.pageId === pageId) onUp(ctx);
        };

        const unsubDown = tool.onDown(onDown);
        const unsubMove = tool.onMove(onMove);
        const unsubUp = tool.onUp(onUp);
        const unsubLeave = tool.onLeave(onLeave);

        return () => {
            unsubDown(); unsubMove(); unsubUp(); unsubLeave();
        };
    }, [activeTool, pageId, getActiveToolInstance, nearestCharIdx, metadata, pageChars, clearSelection, bumpSel]);

    return {
        liveRects: liveRectsRef.current,
        committedRects: committedRectsRef.current,
        clearSelection,
        setCommittedRects: (rects) => {
            committedRectsRef.current = rects;
            bumpSel();
        }
    };
};