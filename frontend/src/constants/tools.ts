// frontend/src/constants/tools.ts

import {
  Hand, MousePointer2, ZoomIn, Type, FileText, Image, Link2,
  Highlighter, Underline, StickyNote, Stamp, FileDown,
  FilePlus, Trash2, RotateCw, Crop, PenTool
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

// ── Tool ID union ─────────────────────────────────────────────────────────────

export type ToolId =
  | 'hand' | 'select' | 'zoom'
  | 'addtext' | 'edittext' | 'addimage' | 'link'
  | 'highlight' | 'underline' | 'stickynote' | 'stamp' | 'redact' | 'draw'
  | 'insert' | 'delete' | 'rotate' | 'extract' | 'crop';

// ── Tool category ─────────────────────────────────────────────────────────────

export type ToolCategory = 'view' | 'edit' | 'comment' | 'pages';

// ── Right-panel section opened by the tool ────────────────────────────────────
// Colocated here so adding a new tool only requires editing this file.

export type PanelSection = 'text' | 'page' | 'appearance';

// ── Tool definition ───────────────────────────────────────────────────────────

export interface ToolDef {
  id: ToolId;
  icon: LucideIcon;
  label: string;
  category: ToolCategory;
  /** Which right-panel section this tool should open, if any. */
  panelSection?: PanelSection;
}

// ── All tools ─────────────────────────────────────────────────────────────────

export const TOOL_DEFS: ToolDef[] = [
  { id: 'hand',       icon: Hand,          label: 'Hand',        category: 'view'    },
  { id: 'select',     icon: MousePointer2, label: 'Select',      category: 'view'    },
  { id: 'zoom',       icon: ZoomIn,        label: 'Zoom',        category: 'view'    },
  { id: 'addtext',    icon: Type,          label: 'Add Text',    category: 'edit',    panelSection: 'text'       },
  { id: 'edittext',   icon: FileText,      label: 'Edit Text',   category: 'edit',    panelSection: 'text'       },
  { id: 'addimage',   icon: Image,         label: 'Add Image',   category: 'edit'    },
  { id: 'link',       icon: Link2,         label: 'Link',        category: 'edit'    },
  { id: 'highlight',  icon: Highlighter,   label: 'Highlight',   category: 'comment', panelSection: 'appearance' },
  { id: 'underline',  icon: Underline,     label: 'Underline',   category: 'comment', panelSection: 'appearance' },
  { id: 'stickynote', icon: StickyNote,    label: 'Sticky Note', category: 'comment', panelSection: 'appearance' },
  { id: 'stamp',      icon: Stamp,         label: 'Stamp',       category: 'comment', panelSection: 'appearance' },
  { id: 'redact',     icon: FileDown,      label: 'Redact',      category: 'comment', panelSection: 'appearance' },
  { id: 'draw',       icon: PenTool,       label: 'Draw',        category: 'comment', panelSection: 'appearance' },
  { id: 'insert',     icon: FilePlus,      label: 'Insert',      category: 'pages',   panelSection: 'page'       },
  { id: 'delete',     icon: Trash2,        label: 'Delete',      category: 'pages',   panelSection: 'page'       },
  { id: 'rotate',     icon: RotateCw,      label: 'Rotate',      category: 'pages',   panelSection: 'page'       },
  { id: 'extract',    icon: FileDown,      label: 'Extract',     category: 'pages',   panelSection: 'page'       },
  { id: 'crop',       icon: Crop,          label: 'Crop',        category: 'pages',   panelSection: 'page'       },
];

// ── Convenience lookup ────────────────────────────────────────────────────────

export const TOOL_BY_ID = Object.fromEntries(TOOL_DEFS.map(t => [t.id, t])) as Record<ToolId, ToolDef>;

/** Returns the right-panel section for a given tool, or null if none. */
export function getPanelSection(toolId: ToolId): PanelSection | null {
  return TOOL_BY_ID[toolId]?.panelSection ?? null;
}

// ── Cursor per tool ───────────────────────────────────────────────────────────

export const TOOL_CURSORS: Partial<Record<ToolId, string>> = {
  hand:      'grab',
  select:    'default',
  zoom:      'zoom-in',
  addtext:   'text',
  edittext:  'text',
  highlight: 'crosshair',
  redact:    'crosshair',
  crop:      'crosshair',
  underline: 'crosshair',
  draw:      'crosshair',
};

// ── Selection overlay color per tool ─────────────────────────────────────────

export const TOOL_SEL_COLOR: Partial<Record<ToolId, string>> = {
  highlight: 'rgba(245,158,11,0.25)',
  redact:    'rgba(239,68,68,0.25)',
  select:    'rgba(74,144,226,0.2)',
  crop:      'rgba(0,0,0,0)',
  underline: 'rgba(255,255,255,0.1)',
};

// ── Drag-capable tools ────────────────────────────────────────────────────────

export const DRAG_TOOLS: ToolId[] = ['highlight', 'redact', 'select', 'crop', 'underline', 'draw'];