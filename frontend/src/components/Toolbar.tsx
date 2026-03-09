// Toolbar.tsx — h-20 tool strip.
// Tool buttons: lucide icon + label, grouped by category with dividers.
// Active tool = bg-[#4a90e2]. Category label below.

import {
  Hand, MousePointer2, ZoomIn, Type, FileText, Image, Link2,
  Highlighter, Underline, StickyNote, Stamp, FilePlus, Trash2,
  RotateCw, FileDown, Undo2, Redo2, Volume2, Minus, Plus,
} from 'lucide-react';
import { useState } from 'react';

// ── Types ─────────────────────────────────────────────────────────────────────

export type ToolId =
  | 'hand' | 'select' | 'zoom'
  | 'addtext' | 'edittext' | 'addimage' | 'link'
  | 'highlight' | 'underline' | 'stickynote' | 'stamp' | 'redact'
  | 'insert' | 'delete' | 'rotate' | 'extract' | 'crop';

interface ToolDef {
  id: ToolId;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  icon: any;
  label: string;
  category: 'view' | 'edit' | 'comment' | 'pages';
}

interface ToolbarProps {
  activeTool: ToolId;
  onToolChange: (tool: ToolId) => void;
  scale: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onZoomReset: () => void;
  onUndo: () => void;
  onRedo: () => void;
  onReadPage: () => void;
  onReadSelection: () => void;
  hasSelection: boolean;
  ttsActive: boolean;
  pageInfo?: { current: number; total: number } | null;
}

// ── Tool definitions — add new tools here ─────────────────────────────────────
const TOOLS: ToolDef[] = [
  { id: 'hand',      icon: Hand,          label: 'Hand',       category: 'view'    },
  { id: 'select',    icon: MousePointer2, label: 'Select',     category: 'view'    },
  { id: 'zoom',      icon: ZoomIn,        label: 'Zoom',       category: 'view'    },
  { id: 'addtext',   icon: Type,          label: 'Add Text',   category: 'edit'    },
  { id: 'edittext',  icon: FileText,      label: 'Edit Text',  category: 'edit'    },
  { id: 'addimage',  icon: Image,         label: 'Add Image',  category: 'edit'    },
  { id: 'link',      icon: Link2,         label: 'Link',       category: 'edit'    },
  { id: 'highlight', icon: Highlighter,   label: 'Highlight',  category: 'comment' },
  { id: 'underline', icon: Underline,     label: 'Underline',  category: 'comment' },
  { id: 'stickynote',icon: StickyNote,    label: 'Sticky Note',category: 'comment' },
  { id: 'stamp',     icon: Stamp,         label: 'Stamp',      category: 'comment' },
  { id: 'redact',    icon: FileDown,      label: 'Redact',     category: 'comment' },
  { id: 'insert',    icon: FilePlus,      label: 'Insert',     category: 'pages'   },
  { id: 'delete',    icon: Trash2,        label: 'Delete',     category: 'pages'   },
  { id: 'rotate',    icon: RotateCw,      label: 'Rotate',     category: 'pages'   },
  { id: 'extract',   icon: FileDown,      label: 'Extract',    category: 'pages'   },
];

// ── Small zoom button ─────────────────────────────────────────────────────────
const ZBtn = ({ children, onClick, disabled }: { children: React.ReactNode; onClick: () => void; disabled?: boolean }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    className="w-7 h-7 flex items-center justify-center rounded text-gray-400 hover:bg-[#2d3338] hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
  >
    {children}
  </button>
);

// ── Toolbar ───────────────────────────────────────────────────────────────────
export function Toolbar({
  activeTool, onToolChange,
  scale, onZoomIn, onZoomOut, onZoomReset,
  onUndo, onRedo,
  onReadPage, onReadSelection,
  hasSelection, ttsActive,
  pageInfo,
}: ToolbarProps) {
  const [localActive, setLocalActive] = useState<ToolId>(activeTool);

  const handleTool = (id: ToolId) => {
    setLocalActive(id);
    onToolChange(id);
  };

  const effectiveTool = activeTool ?? localActive;
  const activeCategory = TOOLS.find(t => t.id === effectiveTool)?.category ?? 'view';

  return (
    <div className="h-20 bg-[#2d3338] border-b border-[#1e2327] flex flex-col flex-shrink-0">

      {/* ── Tool buttons ── */}
      <div className="flex items-center gap-0.5 px-3 py-2 flex-1">

        {/* Undo / Redo */}
        <button
          onClick={onUndo}
          title="Undo (Ctrl+Z)"
          className="w-9 h-9 flex items-center justify-center rounded text-gray-400 hover:bg-[#3d4449] hover:text-white transition-colors"
        >
          <Undo2 size={17} />
        </button>
        <button
          onClick={onRedo}
          title="Redo (Ctrl+Y)"
          className="w-9 h-9 flex items-center justify-center rounded text-gray-400 hover:bg-[#3d4449] hover:text-white transition-colors"
        >
          <Redo2 size={17} />
        </button>
        <div className="w-px h-8 bg-[#1e2327] mx-1.5 flex-shrink-0" />

        {/* Tool buttons with category dividers */}
        {TOOLS.map((tool, idx) => {
          const Icon = tool.icon;
          const isActive = effectiveTool === tool.id;
          const prevTool = TOOLS[idx - 1];
          const showDivider = idx > 0 && prevTool.category !== tool.category;

          return (
            <div key={tool.id} className="flex items-center">
              {showDivider && (
                <div className="w-px h-8 bg-[#1e2327] mx-1.5 flex-shrink-0" />
              )}
              <button
                onClick={() => handleTool(tool.id)}
                title={tool.label}
                className={`flex flex-col items-center justify-center gap-0.5 px-2.5 py-1.5 rounded-lg transition-colors
                  ${isActive
                    ? 'bg-[#4a90e2] text-white'
                    : 'text-gray-300 hover:bg-[#3d4449] hover:text-white'
                  }`}
              >
                <Icon size={17} />
                <span className="text-[10px] font-normal leading-none whitespace-nowrap">
                  {tool.label}
                </span>
              </button>
            </div>
          );
        })}

        <div className="w-px h-8 bg-[#1e2327] mx-1.5 flex-shrink-0" />

        {/* Zoom control */}
        <div className="flex items-center gap-0.5 bg-[#3d4449] rounded-lg px-1 h-9">
          <ZBtn onClick={onZoomOut} disabled={scale <= 0.25}><Minus size={13} /></ZBtn>
          <button
            onClick={onZoomReset}
            title="Reset zoom (100%)"
            className="min-w-[46px] h-7 text-white text-[11px] font-semibold font-mono px-1 hover:bg-[#2d3338] rounded transition-colors"
          >
            {Math.round(scale * 100)}%
          </button>
          <ZBtn onClick={onZoomIn} disabled={scale >= 4.0}><Plus size={13} /></ZBtn>
        </div>

        <div className="w-px h-8 bg-[#1e2327] mx-1.5 flex-shrink-0" />

        {/* Read aloud */}
        <button
          onClick={onReadPage}
          disabled={ttsActive}
          title="Read current page aloud"
          className={`flex flex-col items-center justify-center gap-0.5 px-2.5 py-1.5 rounded-lg transition-colors
            ${ttsActive ? 'opacity-40 cursor-not-allowed' : 'text-gray-300 hover:bg-[#3d4449] hover:text-white'}`}
        >
          <Volume2 size={17} />
          <span className="text-[10px] font-normal leading-none">Read Page</span>
        </button>
        <button
          onClick={onReadSelection}
          disabled={ttsActive || !hasSelection}
          title="Read selection"
          className={`flex flex-col items-center justify-center gap-0.5 px-2.5 py-1.5 rounded-lg transition-colors
            ${ttsActive || !hasSelection ? 'opacity-30 cursor-not-allowed' : 'text-gray-300 hover:bg-[#3d4449] hover:text-white'}`}
        >
          <Volume2 size={17} />
          <span className="text-[10px] font-normal leading-none">Selection</span>
        </button>

        {/* Page info — far right */}
        {pageInfo && (
          <div className="ml-auto flex items-center pl-2">
            <span className="text-[12px] text-gray-400 font-mono">
              <span className="text-white font-semibold">{pageInfo.current}</span>
              {' / '}
              {pageInfo.total}
            </span>
          </div>
        )}
      </div>

      {/* ── Category label ── */}
      <div className="px-4 pb-1.5 text-[10px] text-gray-500 uppercase tracking-wider font-medium">
        {activeCategory}
      </div>
    </div>
  );
}
