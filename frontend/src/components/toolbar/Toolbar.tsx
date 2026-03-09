// components/toolbar/Toolbar.tsx — Ribbon-style tabbed toolbar.
// Active tool tab: text turns blue instead of showing a dot indicator.

import { Undo2, Redo2, Volume2, Minus, Plus } from 'lucide-react';
import { useState } from 'react';
import { TOOL_DEFS, type ToolId } from '../../constants/tools';

export type { ToolId };

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

type TabId = 'view' | 'edit' | 'comment' | 'pages';

const TABS: { id: TabId; label: string }[] = [
  { id: 'view',    label: 'View'    },
  { id: 'edit',    label: 'Edit'    },
  { id: 'comment', label: 'Comment' },
  { id: 'pages',   label: 'Pages'   },
];

// ── Tall tool button ──────────────────────────────────────────────────────────

const ToolBtn = ({
  icon: Icon, label, isActive, onClick,
}: {
  icon: React.ComponentType<{ size?: number }>;
  label: string;
  isActive: boolean;
  onClick: () => void;
}) => (
  <button
    onClick={onClick}
    title={label}
    className={`flex flex-col items-center justify-center gap-1.5 px-4 rounded-lg transition-all duration-100 flex-shrink-0 h-full min-w-[60px]
      ${isActive
        ? 'bg-[#4a90e2] text-white shadow-sm'
        : 'text-gray-300 hover:bg-[#3d4449] hover:text-white'
      }`}
  >
    <Icon size={19} />
    <span className={`text-[11px] font-normal leading-none whitespace-nowrap`}>{label}</span>
  </button>
);

// ── Small stacked button ──────────────────────────────────────────────────────

const SmallToolBtn = ({
  icon: Icon, label, isActive, onClick, disabled,
}: {
  icon: React.ComponentType<{ size?: number }>;
  label: string;
  isActive: boolean;
  onClick: () => void;
  disabled?: boolean;
}) => (
  <button
    onClick={onClick}
    disabled={disabled}
    title={label}
    className={`flex items-center gap-2 px-3 py-[6px] rounded transition-all duration-100 w-full
      ${disabled
        ? 'opacity-30 cursor-not-allowed text-gray-500'
        : isActive
          ? 'bg-[#4a90e2] text-white'
          : 'text-gray-300 hover:bg-[#3d4449] hover:text-white'
      }`}
  >
    <Icon size={14} />
    <span className="text-[11px] font-normal leading-none whitespace-nowrap">{label}</span>
  </button>
);

// ── Vertical rule ─────────────────────────────────────────────────────────────

const Rule = () => (
  <div className="w-px bg-[#1e2327] mx-3 my-2 flex-shrink-0 self-stretch" />
);

// ── Pair column ───────────────────────────────────────────────────────────────

const PairCol = ({ tools, activeTool, onToolChange }: {
  tools: (typeof TOOL_DEFS[number])[];
  activeTool: ToolId;
  onToolChange: (id: ToolId) => void;
}) => (
  <div className="flex flex-col gap-0.5 justify-center h-full py-1.5 min-w-[110px]">
    {tools.map(t => (
      <SmallToolBtn
        key={t.id}
        icon={t.icon}
        label={t.label}
        isActive={activeTool === t.id}
        onClick={() => onToolChange(t.id)}
      />
    ))}
  </div>
);

const byId = (ids: ToolId[]) =>
  ids.map(id => TOOL_DEFS.find(t => t.id === id)!).filter(Boolean);

// ── Tab content ───────────────────────────────────────────────────────────────

function ViewTab({ activeTool, onToolChange, scale, onZoomIn, onZoomOut, onZoomReset }: {
  activeTool: ToolId; onToolChange: (id: ToolId) => void;
  scale: number; onZoomIn: () => void; onZoomOut: () => void; onZoomReset: () => void;
}) {
  return (
    <>
      {byId(['hand', 'select', 'zoom']).map(t => (
        <ToolBtn key={t.id} icon={t.icon} label={t.label}
          isActive={activeTool === t.id} onClick={() => onToolChange(t.id)} />
      ))}
      <Rule />
      <div className="flex items-center gap-0.5 bg-[#1e2327] rounded-lg px-1.5 self-center">
        <button onClick={onZoomOut} disabled={scale <= 0.25}
          className="w-7 h-7 flex items-center justify-center rounded text-gray-400 hover:bg-[#3d4449] hover:text-white disabled:opacity-30 transition-colors">
          <Minus size={13} />
        </button>
        <button onClick={onZoomReset}
          className="min-w-[46px] h-7 text-white text-[11px] font-semibold font-mono px-1 hover:bg-[#3d4449] rounded transition-colors">
          {Math.round(scale * 100)}%
        </button>
        <button onClick={onZoomIn} disabled={scale >= 4.0}
          className="w-7 h-7 flex items-center justify-center rounded text-gray-400 hover:bg-[#3d4449] hover:text-white disabled:opacity-30 transition-colors">
          <Plus size={13} />
        </button>
      </div>
    </>
  );
}

function EditTab({ activeTool, onToolChange, onUndo, onRedo }: {
  activeTool: ToolId; onToolChange: (id: ToolId) => void;
  onUndo: () => void; onRedo: () => void;
}) {
  return (
    <>
      <div className="flex flex-col gap-0.5 justify-center h-full py-1.5 min-w-[90px]">
        <SmallToolBtn icon={Undo2} label="Undo" isActive={false} onClick={onUndo} />
        <SmallToolBtn icon={Redo2} label="Redo" isActive={false} onClick={onRedo} />
      </div>
      <Rule />
      {byId(['addtext', 'edittext']).map(t => (
        <ToolBtn key={t.id} icon={t.icon} label={t.label}
          isActive={activeTool === t.id} onClick={() => onToolChange(t.id)} />
      ))}
      <Rule />
      <PairCol tools={byId(['addimage', 'link'])} activeTool={activeTool} onToolChange={onToolChange} />
    </>
  );
}

function CommentTab({ activeTool, onToolChange, onReadPage, onReadSelection, ttsActive, hasSelection }: {
  activeTool: ToolId; onToolChange: (id: ToolId) => void;
  onReadPage: () => void; onReadSelection: () => void;
  ttsActive: boolean; hasSelection: boolean;
}) {
  return (
    <>
      {byId(['highlight', 'underline']).map(t => (
        <ToolBtn key={t.id} icon={t.icon} label={t.label}
          isActive={activeTool === t.id} onClick={() => onToolChange(t.id)} />
      ))}
      <Rule />
      <PairCol tools={byId(['stickynote', 'stamp'])} activeTool={activeTool} onToolChange={onToolChange} />
      <ToolBtn icon={TOOL_DEFS.find(t => t.id === 'redact')!.icon} label="Redact"
        isActive={activeTool === 'redact'} onClick={() => onToolChange('redact')} />
      <Rule />
      <div className="flex flex-col gap-0.5 justify-center h-full py-1.5 min-w-[110px]">
        <SmallToolBtn icon={Volume2} label="Read Page"
          isActive={false} onClick={onReadPage} disabled={ttsActive} />
        <SmallToolBtn icon={Volume2} label="Read Selection"
          isActive={false} onClick={onReadSelection} disabled={ttsActive || !hasSelection} />
      </div>
    </>
  );
}

function PagesTab({ activeTool, onToolChange }: {
  activeTool: ToolId; onToolChange: (id: ToolId) => void;
}) {
  return (
    <>
      {byId(['insert', 'delete']).map(t => (
        <ToolBtn key={t.id} icon={t.icon} label={t.label}
          isActive={activeTool === t.id} onClick={() => onToolChange(t.id)} />
      ))}
      <Rule />
      <PairCol tools={byId(['rotate', 'extract'])} activeTool={activeTool} onToolChange={onToolChange} />
      <ToolBtn icon={TOOL_DEFS.find(t => t.id === 'crop')!.icon} label="Crop"
        isActive={activeTool === 'crop'} onClick={() => onToolChange('crop')} />
    </>
  );
}

// ── Toolbar root ──────────────────────────────────────────────────────────────

export function Toolbar({
  activeTool, onToolChange,
  scale, onZoomIn, onZoomOut, onZoomReset,
  onUndo, onRedo,
  onReadPage, onReadSelection,
  hasSelection, ttsActive,
  pageInfo,
}: ToolbarProps) {
  const [activeTab, setActiveTab] = useState<TabId>('view');

  const handleToolChange = (id: ToolId) => {
    onToolChange(id);
    const cat = TOOL_DEFS.find(t => t.id === id)?.category as TabId | undefined;
    if (cat && TABS.some(t => t.id === cat)) setActiveTab(cat);
  };

  return (
    <div className="bg-[#2d3338] border-b border-[#1e2327] flex-shrink-0 flex flex-col">

      {/* ── Tab strip ── */}
      <div className="flex items-end px-3 pt-1.5 gap-0.5">
        {TABS.map(tab => {
          const hasActiveTool = TOOL_DEFS.some(t => t.category === tab.id && t.id === activeTool);
          const isOpen = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-1.5 text-xs font-medium rounded-t-md transition-all duration-100 border-t border-x flex-shrink-0
                ${isOpen
                  ? 'bg-[#252a2e] border-[#1e2327] text-white'
                  : hasActiveTool
                    ? 'bg-transparent border-transparent text-[#4a90e2] hover:bg-[#252a2e]/40'
                    : 'bg-transparent border-transparent text-gray-500 hover:text-gray-300 hover:bg-[#252a2e]/40'
                }`}
            >
              {tab.label}
            </button>
          );
        })}

        {pageInfo && (
          <div className="ml-auto flex items-center pb-1.5 pr-1">
            <span className="text-[12px] text-gray-500 font-mono">
              <span className="text-gray-200 font-semibold">{pageInfo.current}</span>
              {' / '}{pageInfo.total}
            </span>
          </div>
        )}
      </div>

      {/* ── Ribbon body ── */}
      <div className="bg-[#252a2e] border-t border-[#1e2327] px-4 flex items-stretch h-[58px] gap-1">
        {activeTab === 'view'    && <ViewTab    activeTool={activeTool} onToolChange={handleToolChange} scale={scale} onZoomIn={onZoomIn} onZoomOut={onZoomOut} onZoomReset={onZoomReset} />}
        {activeTab === 'edit'    && <EditTab    activeTool={activeTool} onToolChange={handleToolChange} onUndo={onUndo} onRedo={onRedo} />}
        {activeTab === 'comment' && <CommentTab activeTool={activeTool} onToolChange={handleToolChange} onReadPage={onReadPage} onReadSelection={onReadSelection} ttsActive={ttsActive} hasSelection={hasSelection} />}
        {activeTab === 'pages'   && <PagesTab   activeTool={activeTool} onToolChange={handleToolChange} />}
      </div>

    </div>
  );
}