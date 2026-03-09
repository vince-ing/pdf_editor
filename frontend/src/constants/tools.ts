// constants/tools.ts — Single source of truth for tool IDs, definitions, cursors.
// Import ToolId from here (not from Toolbar.tsx) to avoid circular deps.

import {
  Hand, MousePointer2, ZoomIn, Type, FileText, Image, Link2,
  Highlighter, Underline, StickyNote, Stamp, FileDown,
  FilePlus, Trash2, RotateCw, Crop,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

// ── Tool ID union ─────────────────────────────────────────────────────────────

export type ToolId =
  | 'hand' | 'select' | 'zoom'
  | 'addtext' | 'edittext' | 'addimage' | 'link'
  | 'highlight' | 'underline' | 'stickynote' | 'stamp' | 'redact'
  | 'insert' | 'delete' | 'rotate' | 'extract' | 'crop';

// ── Tool category ─────────────────────────────────────────────────────────────

export type ToolCategory = 'view' | 'edit' | 'comment' | 'pages';

// ── Tool definition ───────────────────────────────────────────────────────────

export interface ToolDef {
  id: ToolId;
  icon: LucideIcon;
  label: string;
  category: ToolCategory;
}

// ── All tools ─────────────────────────────────────────────────────────────────

export const TOOL_DEFS: ToolDef[] = [
  { id: 'hand',       icon: Hand,          label: 'Hand',        category: 'view'    },
  { id: 'select',     icon: MousePointer2, label: 'Select',      category: 'view'    },
  { id: 'zoom',       icon: ZoomIn,        label: 'Zoom',        category: 'view'    },
  { id: 'addtext',    icon: Type,          label: 'Add Text',    category: 'edit'    },
  { id: 'edittext',   icon: FileText,      label: 'Edit Text',   category: 'edit'    },
  { id: 'addimage',   icon: Image,         label: 'Add Image',   category: 'edit'    },
  { id: 'link',       icon: Link2,         label: 'Link',        category: 'edit'    },
  { id: 'highlight',  icon: Highlighter,   label: 'Highlight',   category: 'comment' },
  { id: 'underline',  icon: Underline,     label: 'Underline',   category: 'comment' },
  { id: 'stickynote', icon: StickyNote,    label: 'Sticky Note', category: 'comment' },
  { id: 'stamp',      icon: Stamp,         label: 'Stamp',       category: 'comment' },
  { id: 'redact',     icon: FileDown,      label: 'Redact',      category: 'comment' },
  { id: 'insert',     icon: FilePlus,      label: 'Insert',      category: 'pages'   },
  { id: 'delete',     icon: Trash2,        label: 'Delete',      category: 'pages'   },
  { id: 'rotate',     icon: RotateCw,      label: 'Rotate',      category: 'pages'   },
  { id: 'extract',    icon: FileDown,      label: 'Extract',     category: 'pages'   },
  { id: 'crop',       icon: Crop,          label: 'Crop',        category: 'pages'   },
];

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

export const DRAG_TOOLS: ToolId[] = ['highlight', 'redact', 'select', 'crop', 'underline'];