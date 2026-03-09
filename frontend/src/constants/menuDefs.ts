// constants/menuDefs.ts — App menu bar definitions.
// Extracted from App.tsx for separation of concerns.
// Icons are Lucide React components (no emoji).

import {
  FolderOpen, X, Save, FilePen, Download, FileText, Lock,
  ClipboardList, Package, Printer, Undo2, Redo2, Copy, Square,
  Search, PanelLeft, SlidersHorizontal, ZoomIn, ZoomOut,
  Link2, Bookmark, Image, PenLine, BookOpen, Volume2, Volume1,
  ScanText, Zap, BookMarked, Keyboard, Info, RotateCw, RotateCcw,
  FilePlus, Trash2, Palette, Check,
} from 'lucide-react';
import { THEMES, type ThemeId } from '../theme/themes';
import type { LucideIcon } from 'lucide-react';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface MenuAction {
  label: string;
  icon?: LucideIcon;
  shortcut?: string;
  onClick?: () => void;
  disabled?: boolean;
  separator?: true;
  submenu?: MenuAction[];
}

export interface MenuDef {
  label: string;
  items: MenuAction[];
}

// ── Menu builder ──────────────────────────────────────────────────────────────
// Returns menu definitions with callbacks injected.
// All icon fields are LucideIcon components — no emoji.

export interface MenuCallbacks {
  openFileDialog: () => void;
  handleExportPdf: () => void;
  handleUndo: () => void;
  handleRedo: () => void;
  handleReadPage: () => void;
  handleReadSelection: () => void;
  ttsStop: () => void;
  setShowThumbnails: (fn: (v: boolean) => boolean) => void;
  setRightPanelOpen: (fn: (v: boolean) => boolean) => void;
  zoomIn: () => void;
  zoomOut: () => void;
  zoomReset: () => void;
  documentState: unknown | null;
  themeId: ThemeId;
  setTheme: (id: ThemeId) => void;
}

export function buildMenuDefs(cb: MenuCallbacks): MenuDef[] {
  return [
    {
      label: 'File',
      items: [
        { label: 'Open…',             icon: FolderOpen,    shortcut: 'Ctrl+O', onClick: cb.openFileDialog },
        { label: 'Close Tab',         icon: X,             shortcut: 'Ctrl+W', disabled: !cb.documentState },
        { separator: true },
        { label: 'Save',              icon: Save,          shortcut: 'Ctrl+S', disabled: true },
        { label: 'Save As…',          icon: FilePen,       shortcut: 'Ctrl+Shift+S', disabled: true },
        { separator: true },
        {
          label: 'Export', icon: Download,
          submenu: [
            { label: 'Export as PDF',        icon: FileText,      onClick: cb.handleExportPdf },
            { label: 'Export Flattened PDF', icon: Lock,          disabled: true },
            { label: 'Export as PDF/A',      icon: ClipboardList, disabled: true },
            { separator: true },
            { label: 'Compress & Export…',   icon: Package,       disabled: true },
          ],
        },
        { separator: true },
        { label: 'Print…', icon: Printer, shortcut: 'Ctrl+P', disabled: true },
      ],
    },
    {
      label: 'Edit',
      items: [
        { label: 'Undo', icon: Undo2, shortcut: 'Ctrl+Z', onClick: cb.handleUndo },
        { label: 'Redo', icon: Redo2, shortcut: 'Ctrl+Y', onClick: cb.handleRedo },
        { separator: true },
        { label: 'Copy Selected Text', icon: Copy,   shortcut: 'Ctrl+C', disabled: true },
        { label: 'Select All',         icon: Square, shortcut: 'Ctrl+A', disabled: true },
        { separator: true },
        {
          label: 'Find & Replace', icon: Search,
          submenu: [
            { label: 'Find…',    shortcut: 'Ctrl+F', disabled: true },
            { label: 'Replace…', shortcut: 'Ctrl+H', disabled: true },
          ],
        },
      ],
    },
    {
      label: 'View',
      items: [
        { label: 'Toggle Sidebar',    icon: PanelLeft,         shortcut: 'Ctrl+B', onClick: () => cb.setShowThumbnails(v => !v) },
        { label: 'Toggle Properties', icon: SlidersHorizontal, shortcut: 'Ctrl+E', onClick: () => cb.setRightPanelOpen(v => !v) },
        { separator: true },
        { label: 'Zoom In',           icon: ZoomIn,  shortcut: 'Ctrl++', onClick: cb.zoomIn },
        { label: 'Zoom Out',          icon: ZoomOut, shortcut: 'Ctrl+-', onClick: cb.zoomOut },
        { label: 'Actual Size (100%)',               onClick: cb.zoomReset },
        { separator: true },
        {
          label: 'Theme', icon: Palette,
          submenu: THEMES.map(th => ({
            label: th.label,
            icon: th.id === cb.themeId ? Check : undefined,
            onClick: () => cb.setTheme(th.id),
          })),
        },
      ],
    },
    {
      label: 'Insert',
      items: [
        { label: 'Hyperlink…',      icon: Link2,     disabled: true },
        { label: 'Bookmark…',       icon: Bookmark,  disabled: true },
        { separator: true },
        { label: 'Blank Page',      icon: FilePlus,  disabled: true },
        {
          label: 'Image…', icon: Image,
          submenu: [
            { label: 'From File…',     disabled: true },
            { label: 'From Clipboard', disabled: true },
          ],
        },
        { separator: true },
        { label: 'Signature Field…', icon: PenLine, disabled: true },
        { label: 'Form Field…',      icon: Square,  disabled: true },
      ],
    },
    {
      label: 'Tools',
      items: [
        {
          label: 'Read Aloud', icon: BookOpen,
          submenu: [
            { label: 'Read Current Page', icon: Volume2, onClick: cb.handleReadPage },
            { label: 'Read Selection',    icon: Volume1, onClick: cb.handleReadSelection },
            { label: 'Stop Reading',      icon: Square,  onClick: cb.ttsStop },
          ],
        },
        { separator: true },
        { label: 'OCR (Recognize Text)…', icon: ScanText, disabled: true },
        { label: 'Protect / Encrypt…',    icon: Lock,     disabled: true },
        { label: 'Compress Document…',    icon: Zap,      disabled: true },
      ],
    },
    {
      label: 'Help',
      items: [
        { label: 'Documentation',       icon: BookMarked, disabled: true },
        { label: 'Keyboard Shortcuts…', icon: Keyboard,   disabled: true },
        { separator: true },
        { label: 'About PDFEdit', icon: Info, onClick: () => alert('PDFEdit — Professional PDF Editor') },
      ],
    },
  ];
}