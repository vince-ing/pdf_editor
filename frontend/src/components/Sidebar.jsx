// frontend/src/components/Sidebar.jsx
// Left panel — page thumbnails with drag-to-reorder, rotate, delete.

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { engineApi } from '../api/client';
import { theme as t } from '../theme';
import { IconButton } from './Primitives';

// ── Thumbnail canvas ──────────────────────────────────────────────────────────
const Thumbnail = ({ pdfDoc, pageNode, pageIndex, rotation = 0 }) => {
    const canvasRef  = useRef(null);
    const THUMB_W    = t.sidebar.thumbWidth;

    useEffect(() => {
        if (!pdfDoc) return;
        let isMounted = true;
        let renderTask = null;

        const render = async () => {
            try {
                const page = await pdfDoc.getPage((pageNode?.page_number ?? pageIndex) + 1);
                if (!isMounted) return;
                const rotatedVp = page.getViewport({ scale: 1, rotation });
                const scale     = THUMB_W / rotatedVp.width;
                const viewport  = page.getViewport({ scale, rotation });
                const canvas    = canvasRef.current;
                if (!canvas) return;
                canvas.width  = viewport.width;
                canvas.height = viewport.height;
                renderTask = page.render({ canvasContext: canvas.getContext('2d'), viewport });
                await renderTask.promise;
            } catch (err) {
                if (err?.name !== 'RenderingCancelledException')
                    console.error('Thumb render error:', err);
            }
        };
        render();
        return () => { isMounted = false; renderTask?.cancel(); };
    }, [pdfDoc, pageIndex, rotation, pageNode]);

    return (
        <canvas
            ref={canvasRef}
            style={{ width: `${THUMB_W}px`, display: 'block', borderRadius: t.radius.sm, backgroundColor: 'white' }}
        />
    );
};

// ── Page card ─────────────────────────────────────────────────────────────────
const PageCard = ({
    page, pdfDoc, pageIndex, isActive, isDragOver, isDragging,
    onClick, onRotate, onDelete, onDragStart, onDragOver, onDragEnd, onDrop,
}) => {
    const [hovered, setHov] = useState(false);
    const showCtrl = hovered || isActive;

    return (
        <div
            draggable
            onDragStart={e => onDragStart(e, pageIndex)}
            onDragOver={e => onDragOver(e, pageIndex)}
            onDragEnd={onDragEnd}
            onDrop={e => onDrop(e, pageIndex)}
            onClick={onClick}
            onMouseEnter={() => setHov(true)}
            onMouseLeave={() => setHov(false)}
            style={{
                position: 'relative',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 8px 10px',
                borderRadius: t.radius.lg,
                cursor: isDragging ? 'grabbing' : 'pointer',
                backgroundColor: isActive
                    ? t.colors.accentMuted
                    : hovered ? t.colors.bgHover : 'transparent',
                border: `1px solid ${isDragOver
                    ? t.colors.crop
                    : isActive
                    ? t.colors.accent
                    : 'transparent'}`,
                transition: t.transitions.fast,
                opacity: isDragging ? 0.4 : 1,
                userSelect: 'none',
            }}
        >
            {/* Drop indicator */}
            {isDragOver && (
                <div style={{
                    position: 'absolute',
                    top: '-2px', left: '10px', right: '10px',
                    height: '2px',
                    backgroundColor: t.colors.crop,
                    borderRadius: t.radius.pill,
                    zIndex: 10,
                }} />
            )}

            {/* Thumbnail with overlay controls */}
            <div style={{
                position: 'relative',
                boxShadow: isActive
                    ? `0 0 0 2px ${t.colors.accent}, ${t.shadows.md}`
                    : t.shadows.sm,
                borderRadius: t.radius.sm,
                overflow: 'visible',
            }}>
                <Thumbnail pdfDoc={pdfDoc} pageNode={page} pageIndex={pageIndex} rotation={page.rotation ?? 0} />

                {/* Hover controls */}
                <div style={{
                    position: 'absolute',
                    top: '4px',
                    right: '4px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '3px',
                    opacity: showCtrl ? 1 : 0,
                    transition: t.transitions.fast,
                    pointerEvents: showCtrl ? 'auto' : 'none',
                }}>
                    <button
                        title="Rotate 90°"
                        onClick={e => { e.stopPropagation(); onRotate(); }}
                        style={miniBtn(t.colors.bgSurface, t.colors.textSecondary)}
                    >↻</button>
                    <button
                        title="Delete page"
                        onClick={e => { e.stopPropagation(); onDelete(); }}
                        style={miniBtn(t.colors.bgSurface, t.colors.danger)}
                    >✕</button>
                </div>

                {/* Rotation badge */}
                {(page.rotation ?? 0) !== 0 && (
                    <div style={{
                        position: 'absolute',
                        bottom: '4px',
                        left: '4px',
                        backgroundColor: t.colors.accent,
                        color: 'white',
                        fontSize: '9px',
                        fontWeight: '700',
                        padding: '1px 5px',
                        borderRadius: t.radius.sm,
                        fontFamily: t.fonts.mono,
                    }}>
                        {page.rotation}°
                    </div>
                )}
            </div>

            {/* Page number */}
            <span style={{
                fontSize: '11px',
                fontWeight: isActive ? '700' : '500',
                color: isActive ? t.colors.accent : t.colors.textMuted,
                fontFamily: t.fonts.mono,
                letterSpacing: '0.04em',
            }}>
                {pageIndex + 1}
            </span>
        </div>
    );
};

const miniBtn = (bg, color) => ({
    width: '22px', height: '22px',
    borderRadius: t.radius.sm,
    border: `1px solid ${t.colors.border}`,
    backgroundColor: bg,
    color,
    fontSize: '13px',
    fontWeight: '700',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    boxShadow: t.shadows.sm,
    lineHeight: 1,
    padding: 0,
});

// ── Sidebar ───────────────────────────────────────────────────────────────────
export const Sidebar = ({ pdfDoc, documentState, activePage, onPageClick, onDocumentChanged }) => {
    const pages = documentState?.children ?? [];
    const [dragSrcIndex, setDragSrcIndex] = useState(null);
    const [dragOverIndex, setDragOverIndex] = useState(null);
    const [busy, setBusy] = useState(false);
    const busyRef = useRef(false);

    const withBusy = useCallback(async (fn) => {
        if (busyRef.current) return;
        busyRef.current = true; setBusy(true);
        try { await fn(); } finally { busyRef.current = false; setBusy(false); }
    }, []);

    const handleRotate = useCallback((page) => {
        withBusy(async () => { await engineApi.rotatePage(page.id, 90); await onDocumentChanged(); });
    }, [withBusy, onDocumentChanged]);

    const handleDelete = useCallback((page, index) => {
        if (pages.length <= 1) { alert('Cannot delete the last page.'); return; }
        if (!window.confirm(`Delete page ${index + 1}?`)) return;
        withBusy(async () => { await engineApi.deletePage(page.id); await onDocumentChanged(); });
    }, [pages.length, withBusy, onDocumentChanged]);

    const handleDragStart = useCallback((e, index) => {
        setDragSrcIndex(index);
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setDragImage(e.currentTarget, 60, 40);
    }, []);

    const handleDragOver = useCallback((e, index) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        if (index !== dragSrcIndex) setDragOverIndex(index);
    }, [dragSrcIndex]);

    const handleDragEnd = useCallback(() => {
        setDragSrcIndex(null); setDragOverIndex(null);
    }, []);

    const handleDrop = useCallback((e, dropIndex) => {
        e.preventDefault();
        const src = dragSrcIndex;
        setDragSrcIndex(null); setDragOverIndex(null);
        if (src === null || src === dropIndex) return;
        const page = pages[src];
        withBusy(async () => { await engineApi.movePage(page.id, dropIndex); await onDocumentChanged(); });
    }, [dragSrcIndex, pages, withBusy, onDocumentChanged]);

    return (
        <aside style={{
            width: t.sidebar.width,
            flexShrink: 0,
            backgroundColor: t.colors.bgSurface,
            borderRight: `1px solid ${t.colors.border}`,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
        }}>
            {/* Header */}
            <div style={{
                padding: '10px 12px',
                borderBottom: `1px solid ${t.colors.border}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexShrink: 0,
            }}>
                <span style={{
                    fontSize: '11px',
                    fontWeight: '600',
                    color: t.colors.textMuted,
                    textTransform: 'uppercase',
                    letterSpacing: '0.1em',
                    fontFamily: t.fonts.ui,
                }}>
                    Pages
                </span>
                <span style={{
                    fontSize: '11px',
                    fontWeight: '700',
                    color: t.colors.accent,
                    fontFamily: t.fonts.mono,
                    backgroundColor: t.colors.accentMuted,
                    padding: '1px 6px',
                    borderRadius: t.radius.pill,
                }}>
                    {pages.length}
                </span>
            </div>

            {/* Hint */}
            {pages.length > 1 && (
                <div style={{
                    padding: '6px 12px',
                    fontSize: '10px',
                    color: t.colors.textMuted,
                    borderBottom: `1px solid ${t.colors.border}`,
                    lineHeight: 1.5,
                }}>
                    Drag to reorder
                </div>
            )}

            {/* Page list */}
            <div style={{
                flex: 1,
                overflowY: 'auto',
                padding: '8px 6px',
                display: 'flex',
                flexDirection: 'column',
                gap: '2px',
            }}>
                {!pdfDoc && (
                    <div style={{
                        color: t.colors.textMuted,
                        fontSize: '12px',
                        textAlign: 'center',
                        marginTop: '40px',
                        lineHeight: 1.7,
                        fontFamily: t.fonts.ui,
                    }}>
                        No document<br />loaded
                    </div>
                )}

                {pdfDoc && pages.map((page, index) => (
                    <PageCard
                        key={page.id}
                        page={page}
                        pdfDoc={pdfDoc}
                        pageIndex={index}
                        isActive={activePage === index}
                        isDragOver={dragOverIndex === index && dragSrcIndex !== index}
                        isDragging={dragSrcIndex === index}
                        onClick={() => onPageClick(index)}
                        onRotate={() => handleRotate(page)}
                        onDelete={() => handleDelete(page, index)}
                        onDragStart={handleDragStart}
                        onDragOver={handleDragOver}
                        onDragEnd={handleDragEnd}
                        onDrop={handleDrop}
                    />
                ))}
            </div>
        </aside>
    );
};