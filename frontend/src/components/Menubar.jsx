// components/MenuBar.jsx
// Mac/Windows-style menu bar with cascading dropdown menus.
// Add new top-level menus by adding entries to MENUS below — fully data-driven.

import React, { useState, useRef, useEffect } from 'react';
import theme from '../theme';
import { DropdownMenu } from './Primitives';
const t = theme;

// ─────────────────────────────────────────────────────────────────────────────
// Menu definitions — add/remove/reorder here freely
// ─────────────────────────────────────────────────────────────────────────────
export const buildMenus = ({
    onOpen, onClose, onSave, onSaveAs,
    onExportPdf, onExportFlatPdf, onExportPdfA, onExportCompressed,
    onPrint,
    onUndo, onRedo,
    onSelectAll, onCopyText,
    onReadPage, onReadSelection, onStopReading,
    onInsertBlankPage, onDeletePage, onRotatePage,
    onZoomIn, onZoomOut, onZoomFit, onZoomActual,
    onToggleSidebar, onToggleRightPanel,
    onInsertLink, onInsertBookmark,
    onAbout,
} = {}) => [
    {
        label: 'File',
        items: [
            { icon: '📂', label: 'Open…',               shortcut: 'Ctrl+O',       onClick: onOpen },
            { icon: '✕',  label: 'Close Tab',            shortcut: 'Ctrl+W',       onClick: onClose, disabled: true },
            { separator: true },
            { icon: '💾', label: 'Save',                 shortcut: 'Ctrl+S',       onClick: onSave, disabled: true },
            { icon: '📝', label: 'Save As…',             shortcut: 'Ctrl+Shift+S', onClick: onSaveAs, disabled: true },
            { separator: true },
            {
                icon: '⬇', label: 'Export',
                submenu: [
                    { icon: '📄', label: 'Export as PDF',            onClick: onExportPdf },
                    { icon: '🔒', label: 'Export Flattened PDF',     onClick: onExportFlatPdf, disabled: true },
                    { icon: '📋', label: 'Export as PDF/A',          onClick: onExportPdfA, disabled: true },
                    { separator: true },
                    { icon: '📦', label: 'Compress & Export…',       onClick: onExportCompressed, disabled: true },
                ],
            },
            { separator: true },
            { icon: '🖨', label: 'Print…',               shortcut: 'Ctrl+P',       onClick: onPrint, disabled: true },
        ],
    },
    {
        label: 'Edit',
        items: [
            { icon: '↩', label: 'Undo',                  shortcut: 'Ctrl+Z',   onClick: onUndo },
            { icon: '↪', label: 'Redo',                  shortcut: 'Ctrl+Y',   onClick: onRedo },
            { separator: true },
            { icon: '⎘', label: 'Copy Selected Text',    shortcut: 'Ctrl+C',   onClick: onCopyText, disabled: true },
            { icon: '☐', label: 'Select All',            shortcut: 'Ctrl+A',   onClick: onSelectAll, disabled: true },
            { separator: true },
            {
                icon: '🔍', label: 'Find & Replace',
                submenu: [
                    { icon: '🔎', label: 'Find in Document…',  shortcut: 'Ctrl+F',   disabled: true },
                    { icon: '🔄', label: 'Replace Text…',      shortcut: 'Ctrl+H',   disabled: true },
                ],
            },
        ],
    },
    {
        label: 'View',
        items: [
            { icon: '🗂', label: 'Toggle Pages Panel',   shortcut: 'Ctrl+B',   onClick: onToggleSidebar },
            { icon: '⚙', label: 'Toggle Properties',    shortcut: 'Ctrl+E',   onClick: onToggleRightPanel },
            { separator: true },
            { icon: '🔍', label: 'Zoom In',              shortcut: 'Ctrl++',   onClick: onZoomIn },
            { icon: '🔎', label: 'Zoom Out',             shortcut: 'Ctrl+-',   onClick: onZoomOut },
            { icon: '⊡',  label: 'Fit to Window',       shortcut: 'Ctrl+0',   onClick: onZoomFit, disabled: true },
            { icon: '⊞',  label: 'Actual Size (100%)',  shortcut: 'Ctrl+1',   onClick: onZoomActual, disabled: true },
        ],
    },
    {
        label: 'Insert',
        items: [
            { icon: '🔗', label: 'Hyperlink…',                           onClick: onInsertLink, disabled: true },
            { icon: '🔖', label: 'Bookmark…',                            onClick: onInsertBookmark, disabled: true },
            { separator: true },
            { icon: '📄', label: 'Insert Blank Page',                    onClick: onInsertBlankPage, disabled: true },
            {
                icon: '🖼', label: 'Insert Image…',
                submenu: [
                    { label: 'From File…',     disabled: true },
                    { label: 'From Camera…',   disabled: true },
                    { label: 'From Clipboard', disabled: true },
                ],
            },
            { separator: true },
            { icon: '✍', label: 'Signature Field…',  disabled: true },
            { icon: '☐', label: 'Form Field…',       disabled: true },
            { icon: '🔑', label: 'Stamp…',           disabled: true },
        ],
    },
    {
        label: 'Tools',
        items: [
            {
                icon: '✏', label: 'Annotation',
                submenu: [
                    { icon: '▬', label: 'Highlight',           shortcut: 'H' },
                    { icon: '■', label: 'Redact',              shortcut: 'R' },
                    { icon: 'T', label: 'Text Note',           shortcut: 'T' },
                    { icon: '🔵', label: 'Sticky Note',        disabled: true },
                    { icon: '📐', label: 'Shape…',             disabled: true },
                ],
            },
            {
                icon: '📖', label: 'Read Aloud',
                submenu: [
                    { icon: '🔊', label: 'Read Current Page',  onClick: onReadPage },
                    { icon: '🔉', label: 'Read Selection',     onClick: onReadSelection },
                    { icon: '⏹',  label: 'Stop Reading',       onClick: onStopReading },
                ],
            },
            { separator: true },
            { icon: '✂',  label: 'Crop Page',          disabled: true },
            { icon: '🔄', label: 'Rotate Page',        onClick: onRotatePage, disabled: true },
            { separator: true },
            { icon: '🔑', label: 'OCR (Recognize Text)…', disabled: true },
            { icon: '🔒', label: 'Protect / Encrypt…',   disabled: true },
            { icon: '⚡', label: 'Compress Document…',   disabled: true },
        ],
    },
    {
        label: 'Help',
        items: [
            { icon: '📘', label: 'Documentation',         disabled: true },
            { icon: '⌨', label: 'Keyboard Shortcuts…',  disabled: true },
            { separator: true },
            { icon: 'ℹ', label: 'About PDFEdit',        onClick: onAbout },
        ],
    },
];

// ─────────────────────────────────────────────────────────────────────────────
// MenuBar component
// ─────────────────────────────────────────────────────────────────────────────
export const MenuBar = ({ menus, documentName }) => {
    const [openIdx, setOpenIdx] = useState(null);
    const barRef = useRef(null);

    useEffect(() => {
        const handler = (e) => {
            if (barRef.current && !barRef.current.contains(e.target)) setOpenIdx(null);
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    return (
        <div
            ref={barRef}
            className="no-select"
            style={{
                height: t.layout.menuBarH,
                backgroundColor: t.colors.chrome,
                borderBottom: `1px solid ${t.colors.border}`,
                display: 'flex',
                alignItems: 'center',
                flexShrink: 0,
                zIndex: 8000,
                paddingLeft: '8px',
                gap: '0',
            }}
        >
            {/* App icon + name */}
            <div style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                paddingRight: '12px', marginRight: '4px',
                borderRight: `1px solid ${t.colors.border}`,
                height: '100%',
            }}>
                <span style={{ fontSize: '13px' }}>📄</span>
                <span style={{
                    fontSize: '12px', fontWeight: '700',
                    color: t.colors.textPrimary, letterSpacing: '-0.01em',
                }}>
                    PDF<span style={{ color: t.colors.accent }}>Edit</span>
                </span>
            </div>

            {/* Menu items */}
            {menus.map((menu, idx) => {
                const isOpen = openIdx === idx;
                return (
                    <div key={idx} style={{ position: 'relative', height: '100%', display: 'flex', alignItems: 'center' }}>
                        <button
                            onMouseDown={() => setOpenIdx(isOpen ? null : idx)}
                            onMouseEnter={() => openIdx !== null && setOpenIdx(idx)}
                            style={{
                                height: '100%',
                                padding: '0 9px',
                                background: isOpen ? t.colors.bgSurface : 'transparent',
                                color: isOpen ? t.colors.textPrimary : t.colors.textSecondary,
                                border: 'none',
                                borderBottom: isOpen ? `1px solid ${t.colors.bgSurface}` : '1px solid transparent',
                                cursor: 'pointer',
                                fontSize: '12px',
                                fontFamily: t.fonts.ui,
                                fontWeight: '400',
                                transition: t.t.fast,
                            }}
                        >
                            {menu.label}
                        </button>
                        {isOpen && (
                            <DropdownMenu
                                items={menu.items}
                                onClose={() => setOpenIdx(null)}
                                style={{ top: '100%', left: 0 }}
                            />
                        )}
                    </div>
                );
            })}

            {/* Document name — centered */}
            {documentName && (
                <span style={{
                    position: 'absolute', left: '50%', transform: 'translateX(-50%)',
                    fontSize: '11px', color: t.colors.textMuted,
                    fontFamily: t.fonts.ui, pointerEvents: 'none',
                    whiteSpace: 'nowrap', overflow: 'hidden', maxWidth: '300px',
                    textOverflow: 'ellipsis',
                }}>
                    {documentName}
                </span>
            )}
        </div>
    );
};