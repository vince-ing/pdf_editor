// components/LeftPanel.jsx
// Icon rail on the left + expandable drawer.
// Panels: Pages, Bookmarks, Search, Annotations
// Add new panel views by adding entries to PANELS array below.

import React, { useState, useEffect, useRef, useCallback } from 'react';
import theme from '../theme';
import { engineApi } from '../api/client';
const t = theme;

// ─────────────────────────────────────────────────────────────────────────────
// Panel view IDs — add new ones here
// ─────────────────────────────────────────────────────────────────────────────
export const PANEL_VIEWS = {
    PAGES:       'pages',
    BOOKMARKS:   'bookmarks',
    ANNOTATIONS: 'annotations',
    SEARCH:      'search',
};

// ─────────────────────────────────────────────────────────────────────────────
// Thumbnail canvas
// ─────────────────────────────────────────────────────────────────────────────
const Thumbnail = ({ pdfDoc, pageNode, pageIndex, rotation }) => {
    const canvasRef = useRef(null);
    const W = t.layout.thumbW;

    useEffect(() => {
        if (!pdfDoc) return;
        let alive = true, task = null;
        (async () => {
            try {
                const page = await pdfDoc.getPage((pageNode?.page_number ?? pageIndex) + 1);
                if (!alive) return;
                const vp0 = page.getViewport({ scale: 1, rotation });
                const sc  = W / vp0.width;
                const vp  = page.getViewport({ scale: sc, rotation });
                const cv  = canvasRef.current;
                if (!cv) return;
                cv.width = vp.width; cv.height = vp.height;
                task = page.render({ canvasContext: cv.getContext('2d'), viewport: vp });
                await task.promise;
            } catch (e) { if (e?.name !== 'RenderingCancelledException') console.error(e); }
        })();
        return () => { alive = false; task?.cancel(); };
    }, [pdfDoc, pageIndex, rotation, pageNode]);

    return <canvas ref={canvasRef} style={{ width: W, display: 'block', borderRadius: t.radius.xs, background: 'white' }} />;
};

// ─────────────────────────────────────────────────────────────────────────────
// PageCard
// ─────────────────────────────────────────────────────────────────────────────
const PageCard = ({ page, pdfDoc, pageIndex, isActive, isDragOver, isDragging, onClick, onRotate, onDelete, onDragStart, onDragOver, onDragEnd, onDrop }) => {
    const [hov, setHov] = useState(false);

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
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '5px',
                padding: '6px 6px 8px',
                borderRadius: t.radius.md,
                cursor: isDragging ? 'grabbing' : 'pointer',
                backgroundColor: isActive ? t.colors.accentSubtle : hov ? t.colors.bgHover : 'transparent',
                border: `1px solid ${isDragOver ? t.colors.crop : isActive ? t.colors.accent : 'transparent'}`,
                transition: t.t.fast,
                opacity: isDragging ? 0.4 : 1,
                userSelect: 'none',
            }}
        >
            {isDragOver && (
                <div style={{ position: 'absolute', top: '-1px', left: '8px', right: '8px', height: '2px', background: t.colors.crop, borderRadius: '99px', zIndex: 10 }} />
            )}

            <div style={{ position: 'relative', boxShadow: isActive ? `0 0 0 2px ${t.colors.accent}, ${t.shadow.sm}` : t.shadow.xs, borderRadius: t.radius.xs, overflow: 'visible' }}>
                <Thumbnail pdfDoc={pdfDoc} pageNode={page} pageIndex={pageIndex} rotation={page.rotation ?? 0} />

                {/* Hover controls */}
                <div style={{ position: 'absolute', top: '3px', right: '3px', display: 'flex', flexDirection: 'column', gap: '2px', opacity: hov || isActive ? 1 : 0, transition: t.t.fast, pointerEvents: hov || isActive ? 'auto' : 'none' }}>
                    {[
                        { title: 'Rotate', icon: '↻', onClick: onRotate },
                        { title: 'Delete', icon: '✕', onClick: onDelete, danger: true },
                    ].map(btn => (
                        <button key={btn.icon} title={btn.title} onClick={e => { e.stopPropagation(); btn.onClick(); }}
                            style={{ width: 20, height: 20, borderRadius: 3, border: `1px solid ${t.colors.border}`, background: t.colors.bgRaised, color: btn.danger ? t.colors.danger : t.colors.textSecondary, fontSize: 11, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            {btn.icon}
                        </button>
                    ))}
                </div>

                {(page.rotation ?? 0) !== 0 && (
                    <div style={{ position: 'absolute', bottom: 3, left: 3, background: t.colors.accent, color: '#fff', fontSize: 9, fontWeight: 700, padding: '1px 4px', borderRadius: 3, fontFamily: t.fonts.mono }}>
                        {page.rotation}°
                    </div>
                )}
            </div>

            <span style={{ fontSize: '10px', fontWeight: isActive ? '700' : '400', color: isActive ? t.colors.accent : t.colors.textMuted, fontFamily: t.fonts.mono }}>
                {pageIndex + 1}
            </span>
        </div>
    );
};

// ─────────────────────────────────────────────────────────────────────────────
// BookmarksView — scaffolded for future backend support
// ─────────────────────────────────────────────────────────────────────────────
const BookmarksView = () => (
    <div style={{ padding: '16px 12px', textAlign: 'center' }}>
        <div style={{ fontSize: '24px', marginBottom: '8px' }}>🔖</div>
        <div style={{ fontSize: '12px', color: t.colors.textSecondary, lineHeight: 1.6 }}>
            No bookmarks yet.
        </div>
        <div style={{ fontSize: '11px', color: t.colors.textMuted, marginTop: '6px' }}>
            Use Insert › Bookmark to add one.
        </div>
    </div>
);

// ─────────────────────────────────────────────────────────────────────────────
// SearchView — scaffolded
// ─────────────────────────────────────────────────────────────────────────────
const SearchView = () => {
    const [query, setQuery] = useState('');
    return (
        <div style={{ padding: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: t.colors.bgRaised, border: `1px solid ${t.colors.borderMid}`, borderRadius: t.radius.sm, padding: '5px 8px', marginBottom: '8px' }}>
                <span style={{ color: t.colors.textMuted, fontSize: '12px' }}>🔍</span>
                <input
                    value={query}
                    onChange={e => setQuery(e.target.value)}
                    placeholder="Search document…"
                    style={{ flex: 1, background: 'none', border: 'none', color: t.colors.textPrimary, fontSize: '12px', fontFamily: t.fonts.ui, outline: 'none' }}
                />
            </div>
            <div style={{ fontSize: '11px', color: t.colors.textMuted, textAlign: 'center', marginTop: '12px' }}>
                Search coming soon
            </div>
        </div>
    );
};

// ─────────────────────────────────────────────────────────────────────────────
// AnnotationsView — scaffolded
// ─────────────────────────────────────────────────────────────────────────────
const AnnotationsView = () => (
    <div style={{ padding: '16px 12px', textAlign: 'center' }}>
        <div style={{ fontSize: '24px', marginBottom: '8px' }}>✏️</div>
        <div style={{ fontSize: '11px', color: t.colors.textMuted, lineHeight: 1.6 }}>
            Annotations list coming soon
        </div>
    </div>
);

// ─────────────────────────────────────────────────────────────────────────────
// Left rail icon
// ─────────────────────────────────────────────────────────────────────────────
const RailIcon = ({ icon, label, isActive, onClick }) => {
    const [hov, setHov] = useState(false);
    return (
        <button
            onClick={onClick}
            title={label}
            onMouseEnter={() => setHov(true)}
            onMouseLeave={() => setHov(false)}
            style={{
                width: '100%', height: t.layout.leftRailW,
                border: 'none',
                borderLeft: `2px solid ${isActive ? t.colors.accent : 'transparent'}`,
                background: isActive ? t.colors.accentSubtle : hov ? t.colors.bgHover : 'transparent',
                color: isActive ? t.colors.accent : hov ? t.colors.textPrimary : t.colors.textMuted,
                cursor: 'pointer', fontSize: '15px',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: t.t.fast, flexShrink: 0,
            }}
        >{icon}</button>
    );
};

// ─────────────────────────────────────────────────────────────────────────────
// LeftPanel — rail + conditional drawer
// ─────────────────────────────────────────────────────────────────────────────
export const LeftPanel = ({
    pdfDoc, documentState, activePage,
    onPageClick, onDocumentChanged,
    activeView, onViewChange,
}) => {
    const pages = documentState?.children ?? [];
    const [dragSrc,  setDragSrc]  = useState(null);
    const [dragOver, setDragOver] = useState(null);
    const [busy,     setBusy]     = useState(false);
    const busyRef = useRef(false);

    const withBusy = useCallback(async (fn) => {
        if (busyRef.current) return;
        busyRef.current = true; setBusy(true);
        try { await fn(); } finally { busyRef.current = false; setBusy(false); }
    }, []);

    const handleRotate = p  => withBusy(async () => { await engineApi.rotatePage(p.id, 90); await onDocumentChanged(); });
    const handleDelete = (p, i) => {
        if (pages.length <= 1) return alert('Cannot delete the last page.');
        if (!window.confirm(`Delete page ${i + 1}?`)) return;
        withBusy(async () => { await engineApi.deletePage(p.id); await onDocumentChanged(); });
    };

    const RAIL_ITEMS = [
        { id: PANEL_VIEWS.PAGES,       icon: '⊞', label: 'Pages' },
        { id: PANEL_VIEWS.BOOKMARKS,   icon: '🔖', label: 'Bookmarks' },
        { id: PANEL_VIEWS.ANNOTATIONS, icon: '✏', label: 'Annotations' },
        { id: PANEL_VIEWS.SEARCH,      icon: '🔍', label: 'Search' },
    ];

    const showDrawer = activeView !== null;

    return (
        <div style={{ display: 'flex', height: '100%', flexShrink: 0 }}>
            {/* Rail */}
            <div style={{
                width: t.layout.leftRailW,
                backgroundColor: t.colors.bgSurface,
                borderRight: `1px solid ${t.colors.border}`,
                display: 'flex', flexDirection: 'column',
                alignItems: 'center', paddingTop: '4px', gap: '2px',
                flexShrink: 0,
            }}>
                {RAIL_ITEMS.map(item => (
                    <RailIcon
                        key={item.id}
                        icon={item.icon}
                        label={item.label}
                        isActive={activeView === item.id}
                        onClick={() => onViewChange(activeView === item.id ? null : item.id)}
                    />
                ))}
            </div>

            {/* Drawer */}
            {showDrawer && (
                <div style={{
                    width: t.layout.leftDrawerW,
                    backgroundColor: t.colors.bgSurface,
                    borderRight: `1px solid ${t.colors.border}`,
                    display: 'flex', flexDirection: 'column',
                    overflow: 'hidden',
                    animation: 'slideRight 0.15s ease',
                }}>
                    {/* Drawer header */}
                    <div style={{
                        height: '34px', padding: '0 12px',
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        borderBottom: `1px solid ${t.colors.border}`, flexShrink: 0,
                    }}>
                        <span style={{ fontSize: '11px', fontWeight: '600', color: t.colors.textSecondary, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                            {RAIL_ITEMS.find(x => x.id === activeView)?.label}
                            {activeView === PANEL_VIEWS.PAGES && pages.length > 0 && (
                                <span style={{ color: t.colors.accent, background: t.colors.accentSubtle, padding: '1px 5px', borderRadius: t.radius.pill, fontSize: '10px', marginLeft: '6px', fontFamily: t.fonts.mono }}>{pages.length}</span>
                            )}
                        </span>
                        {busy && <span style={{ fontSize: '10px', color: t.colors.warning }}>●</span>}
                    </div>

                    {/* Drawer body */}
                    <div style={{ flex: 1, overflowY: 'auto', padding: activeView === PANEL_VIEWS.PAGES ? '6px' : '0' }}>
                        {activeView === PANEL_VIEWS.PAGES && (
                            <>
                                {!pdfDoc && (
                                    <div style={{ color: t.colors.textMuted, fontSize: '12px', textAlign: 'center', marginTop: '40px' }}>No document loaded</div>
                                )}
                                {pdfDoc && pages.map((page, i) => (
                                    <PageCard
                                        key={page.id}
                                        page={page} pdfDoc={pdfDoc} pageIndex={i}
                                        isActive={activePage === i}
                                        isDragOver={dragOver === i && dragSrc !== i}
                                        isDragging={dragSrc === i}
                                        onClick={() => onPageClick(i)}
                                        onRotate={() => handleRotate(page)}
                                        onDelete={() => handleDelete(page, i)}
                                        onDragStart={(e, idx) => { setDragSrc(idx); e.dataTransfer.effectAllowed = 'move'; }}
                                        onDragOver={(e, idx) => { e.preventDefault(); if (idx !== dragSrc) setDragOver(idx); }}
                                        onDragEnd={() => { setDragSrc(null); setDragOver(null); }}
                                        onDrop={(e, idx) => {
                                            e.preventDefault();
                                            const src = dragSrc;
                                            setDragSrc(null); setDragOver(null);
                                            if (src !== null && src !== idx) withBusy(async () => { await engineApi.movePage(pages[src].id, idx); await onDocumentChanged(); });
                                        }}
                                    />
                                ))}
                            </>
                        )}
                        {activeView === PANEL_VIEWS.BOOKMARKS   && <BookmarksView />}
                        {activeView === PANEL_VIEWS.SEARCH       && <SearchView />}
                        {activeView === PANEL_VIEWS.ANNOTATIONS  && <AnnotationsView />}
                    </div>
                </div>
            )}
        </div>
    );
};