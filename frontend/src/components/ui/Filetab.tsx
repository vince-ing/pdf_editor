// components/ui/FileTab.tsx — Document tab strip.
// Supports multiple open files, modified indicator, close button.
// No emoji — PDF icon is a minimal inline SVG, close is Lucide X.

import { useState } from 'react';
import { X, Plus } from 'lucide-react';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface FileTab {
  id: string;
  name: string;
  fullName?: string;
  modified?: boolean;
}

interface TabProps {
  tab: FileTab;
  isActive: boolean;
  onClick: () => void;
  onClose: (id: string) => void;
}

interface TabStripProps {
  tabs: FileTab[];
  activeTabId: string | null;
  onTabClick: (id: string) => void;
  onTabClose: (id: string) => void;
  onNewTab?: () => void;
}

// ── PdfIcon — minimal inline SVG, no emoji ────────────────────────────────────

const PdfIcon = () => (
  <svg
    width="13"
    height="14"
    viewBox="0 0 13 14"
    fill="none"
    className="flex-shrink-0"
    aria-hidden="true"
  >
    <path
      d="M2 1h6.5l3 3V13a.5.5 0 01-.5.5H2A.5.5 0 011.5 13V1.5A.5.5 0 012 1z"
      fill="#ef4444"
      opacity="0.85"
    />
    <path
      d="M8.5 1v3.5h3"
      fill="none"
      stroke="rgba(0,0,0,0.25)"
      strokeWidth="0.5"
    />
    <text
      x="3.5"
      y="11"
      fontSize="3.5"
      fontWeight="700"
      fill="white"
      fontFamily="system-ui"
      opacity="0.9"
    >
      PDF
    </text>
  </svg>
);

// ── Tab ───────────────────────────────────────────────────────────────────────

function Tab({ tab, isActive, onClick, onClose }: TabProps) {
  const [hov, setHov] = useState(false);
  const showClose = hov || isActive;

  return (
    <div
      role="tab"
      aria-selected={isActive}
      tabIndex={0}
      onClick={onClick}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') onClick(); }}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      title={tab.fullName ?? tab.name}
      className={`group flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all cursor-pointer
        flex-shrink-0 max-w-[220px] min-w-[80px] select-none outline-none
        focus-visible:ring-1 focus-visible:ring-[#4a90e2]
        ${isActive
          ? 'bg-[#3d4449] border-white/[0.07] text-white shadow-sm'
          : 'border-transparent text-gray-400 hover:bg-[#3d4449]/60 hover:text-gray-200'
        }`}
    >
      <PdfIcon />

      {/* Name + modified dot */}
      <span className={`text-[13px] truncate flex-1 leading-none ${isActive ? 'font-medium' : 'font-normal'}`}>
        {tab.modified && (
          <span
            className="inline-block w-1.5 h-1.5 rounded-full bg-amber-400 mr-1.5 mb-px align-middle"
            title="Unsaved changes"
          />
        )}
        {tab.name}
      </span>

      {/* Close button — always reserves space to prevent layout shift */}
      <button
        onClick={e => { e.stopPropagation(); onClose(tab.id); }}
        tabIndex={-1}
        title="Close tab"
        aria-label={`Close ${tab.name}`}
        className={`w-4 h-4 flex items-center justify-center rounded transition-all flex-shrink-0
          ${showClose
            ? 'text-gray-400 hover:text-white hover:bg-white/10 opacity-100'
            : 'opacity-0 pointer-events-none'
          }`}
      >
        <X size={11} />
      </button>
    </div>
  );
}

// ── TabStrip ──────────────────────────────────────────────────────────────────

export function TabStrip({
  tabs,
  activeTabId,
  onTabClick,
  onTabClose,
  onNewTab,
}: TabStripProps) {
  return (
    <div
      role="tablist"
      className="flex items-center gap-1.5 flex-1 min-w-0 overflow-hidden"
    >
      {tabs.map(tab => (
        <Tab
          key={tab.id}
          tab={tab}
          isActive={tab.id === activeTabId}
          onClick={() => onTabClick(tab.id)}
          onClose={onTabClose}
        />
      ))}

      {onNewTab && (
        <button
          onClick={onNewTab}
          title="Open file (Ctrl+O)"
          aria-label="Open new file"
          className="w-7 h-7 flex items-center justify-center text-gray-500
            hover:text-white hover:bg-[#3d4449] rounded transition-colors
            flex-shrink-0"
        >
          <Plus size={15} />
        </button>
      )}
    </div>
  );
}