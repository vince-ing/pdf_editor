import React, { useEffect, useRef, useState, useCallback } from 'react';
import { engineApi } from '../api/client';

// ── Thumbnail canvas ─────────────────────────────────────────────────────────

const Thumbnail = ({ pdfDoc, pageNode, pageIndex, rotation = 0 }) => {
    const canvasRef = useRef(null);
    const THUMB_WIDTH = 132;

    useEffect(() => {
        if (!pdfDoc) return;
        let isMounted = true;
        let renderTask = null;

        const render = async () => {
            try {
                const page = await pdfDoc.getPage((pageNode?.page_number ?? pageIndex) + 1);
                if (!isMounted) return;

                // Get the rotated viewport at scale=1 so we know the actual
                // rendered width (swaps for 90/270 rotations).
                const rotatedViewport = page.getViewport({ scale: 1, rotation });
                const scale = THUMB_WIDTH / rotatedViewport.width;
                const viewport = page.getViewport({ scale, rotation });

                const canvas = canvasRef.current;
                if (!canvas) return;
                canvas.width  = viewport.width;
                canvas.height = viewport.height;

                renderTask = page.render({
                    canvasContext: canvas.getContext('2d'),
                    viewport,
                });
                await renderTask.promise;
            } catch (err) {
                if (err?.name !== 'RenderingCancelledException')
                    console.error('Thumbnail render error:', err);
            }
        };

        render();
        return () => { isMounted = false; renderTask?.cancel(); };
    }, [pdfDoc, pageIndex, rotation]);

    return (
        <canvas
            ref={canvasRef}
            style={{
                width: `${THUMB_WIDTH}px`,
                display: 'block',
                borderRadius: '3px',
                backgroundColor: 'white',
            }}
        />
    );
};

// ── Page card ────────────────────────────────────────────────────────────────

const PageCard = ({
    page, pdfDoc, pageIndex, isActive, isDragOver, isDragging,
    onClick, onRotate, onDelete, onDragStart, onDragOver, onDragEnd, onDrop,
}) => {
    const [hovered, setHovered] = useState(false);
    const showControls = hovered || isActive;

    return (
        <div
            draggable
            onDragStart={(e) => onDragStart(e, pageIndex)}
            onDragOver={(e) => onDragOver(e, pageIndex)}
            onDragEnd={onDragEnd}
            onDrop={(e) => onDrop(e, pageIndex)}
            onClick={onClick}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            style={{
                position: 'relative',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 8px 10px',
                borderRadius: '7px',
                cursor: isDragging ? 'grabbing' : 'pointer',
                backgroundColor: isActive
                    ? 'rgba(52, 152, 219, 0.18)'
                    : hovered
                    ? 'rgba(255,255,255,0.06)'
                    : 'transparent',
                border: isDragOver
                    ? '2px solid #f39c12'
                    : isActive
                    ? '2px solid #3498db'
                    : '2px solid transparent',
                transition: 'all 0.15s ease',
                opacity: isDragging ? 0.45 : 1,
                userSelect: 'none',
            }}
        >
            {/* Drag indicator */}
            {isDragOver && (
                <div style={{
                    position: 'absolute',
                    top: '-2px', left: '12px', right: '12px',
                    height: '3px',
                    backgroundColor: '#f39c12',
                    borderRadius: '2px',
                    zIndex: 10,
                }} />
            )}

            {/* Thumbnail wrapper */}
            <div style={{
                position: 'relative',
                boxShadow: isActive
                    ? '0 0 0 2px #3498db, 0 4px 14px rgba(0,0,0,0.5)'
                    : '0 2px 8px rgba(0,0,0,0.45)',
                borderRadius: '3px',
                overflow: 'visible',
            }}>
                <Thumbnail
                    pdfDoc={pdfDoc}
                    pageNode={page}
                    pageIndex={pageIndex}
                    rotation={page.rotation ?? 0}
                />

                {/* Hover controls overlay */}
                <div style={{
                    position: 'absolute',
                    top: '4px',
                    right: '4px',
                    display: 'flex',
                    gap: '4px',
                    opacity: showControls ? 1 : 0,
                    transition: 'opacity 0.15s',
                    pointerEvents: showControls ? 'auto' : 'none',
                }}>
                    <ControlBtn
                        title="Rotate 90°"
                        onClick={(e) => { e.stopPropagation(); onRotate(); }}
                        color="#2980b9"
                    >
                        ↻
                    </ControlBtn>
                    <ControlBtn
                        title="Delete page"
                        onClick={(e) => { e.stopPropagation(); onDelete(); }}
                        color="#c0392b"
                    >
                        ✕
                    </ControlBtn>
                </div>

                {/* Rotation badge */}
                {(page.rotation ?? 0) !== 0 && (
                    <div style={{
                        position: 'absolute',
                        bottom: '4px', left: '4px',
                        backgroundColor: 'rgba(41,128,185,0.9)',
                        color: 'white',
                        fontSize: '9px',
                        fontWeight: '700',
                        padding: '1px 5px',
                        borderRadius: '3px',
                    }}>
                        {page.rotation}°
                    </div>
                )}
            </div>

            {/* Page number */}
            <span style={{
                fontSize: '11px',
                fontWeight: isActive ? '700' : '500',
                color: isActive ? '#3498db' : '#7f8c8d',
                letterSpacing: '0.02em',
            }}>
                {pageIndex + 1}
            </span>
        </div>
    );
};

const ControlBtn = ({ children, onClick, title, color }) => (
    <button
        title={title}
        onClick={onClick}
        style={{
            width: '22px',
            height: '22px',
            borderRadius: '4px',
            border: 'none',
            backgroundColor: color,
            color: 'white',
            fontSize: '12px',
            fontWeight: '700',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 1px 4px rgba(0,0,0,0.4)',
            lineHeight: 1,
            padding: 0,
        }}
    >
        {children}
    </button>
);

// ── Sidebar ──────────────────────────────────────────────────────────────────

export const Sidebar = ({ pdfDoc, documentState, activePage, onPageClick, onDocumentChanged }) => {
    const pages = documentState?.children ?? [];
    const [dragSrcIndex, setDragSrcIndex] = useState(null);
    const [dragOverIndex, setDragOverIndex] = useState(null);
    const [busy, setBusy] = useState(false);

    const busyRef = useRef(false);

    const withBusy = useCallback(async (fn) => {
        if (busyRef.current) return;
        busyRef.current = true;
        setBusy(true);
        try { await fn(); }
        finally { busyRef.current = false; setBusy(false); }
    }, []);

    // ── Rotate ───────────────────────────────────────────────────────────────
    const handleRotate = useCallback((page) => {
        withBusy(async () => {
            await engineApi.rotatePage(page.id, 90);
            await onDocumentChanged();
        });
    }, [withBusy, onDocumentChanged]);

    // ── Delete ───────────────────────────────────────────────────────────────
    const handleDelete = useCallback((page, index) => {
        if (pages.length <= 1) { alert('Cannot delete the last page.'); return; }
        if (!window.confirm(`Delete page ${index + 1}?`)) return;
        withBusy(async () => {
            await engineApi.deletePage(page.id);
            await onDocumentChanged();
        });
    }, [pages.length, withBusy, onDocumentChanged]);

    // ── Drag-to-reorder ──────────────────────────────────────────────────────
    const handleDragStart = useCallback((e, index) => {
        setDragSrcIndex(index);
        e.dataTransfer.effectAllowed = 'move';
        // ghost image
        e.dataTransfer.setDragImage(e.currentTarget, 60, 40);
    }, []);

    const handleDragOver = useCallback((e, index) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        if (index !== dragSrcIndex) setDragOverIndex(index);
    }, [dragSrcIndex]);

    const handleDragEnd = useCallback(() => {
        setDragSrcIndex(null);
        setDragOverIndex(null);
    }, []);

    const handleDrop = useCallback((e, dropIndex) => {
        e.preventDefault();
        const src = dragSrcIndex;
        setDragSrcIndex(null);
        setDragOverIndex(null);
        if (src === null || src === dropIndex) return;

        const page = pages[src];
        withBusy(async () => {
            await engineApi.movePage(page.id, dropIndex);
            await onDocumentChanged();
        });
    }, [dragSrcIndex, pages, withBusy, onDocumentChanged]);

    return (
        <div style={{
            width: '172px',
            flexShrink: 0,
            backgroundColor: '#1a2535',
            borderRight: '1px solid #0d1520',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
        }}>
            {/* Header */}
            <div style={{
                padding: '10px 12px',
                fontSize: '10px',
                fontWeight: '700',
                color: '#546e7a',
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                borderBottom: '1px solid rgba(255,255,255,0.06)',
                flexShrink: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
            }}>
                <span>Pages ({pages.length})</span>
                {busy && (
                    <span style={{ color: '#f39c12', fontSize: '10px' }}>…</span>
                )}
            </div>

            {/* Help tip */}
            {pages.length > 1 && (
                <div style={{
                    padding: '5px 10px',
                    fontSize: '10px',
                    color: '#3d5166',
                    borderBottom: '1px solid rgba(255,255,255,0.04)',
                    lineHeight: 1.4,
                }}>
                    Drag to reorder · hover for controls
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
                        color: '#3d5166',
                        fontSize: '12px',
                        textAlign: 'center',
                        marginTop: '32px',
                        lineHeight: 1.6,
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
        </div>
    );
};