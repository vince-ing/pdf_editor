// components/layout/TopBar.tsx — h-14 top bar: logo + cascading menus + file tabs + search + avatar
// All icons are Lucide React — no emoji anywhere.

import { Search, Minimize2, Maximize2, X } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import type { MenuDef, MenuAction } from '../../constants/menuDefs';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface FileTab {
  id: string;
  name: string;
  fullName?: string;
  modified?: boolean;
}

interface TopBarProps {
  tabs?: FileTab[];
  activeTabId?: string | null;
  onTabClick?: (id: string) => void;
  onTabClose?: (id: string) => void;
  onNewTab?: () => void;
  menus?: MenuDef[];
}

// ── Keyboard shortcut badge ───────────────────────────────────────────────────

const Kbd = ({ children }: { children: string }) => (
  <span className="text-[10px] font-mono text-gray-500 bg-[#1e2327] border border-white/5 rounded px-1 py-0.5 flex-shrink-0">
    {children}
  </span>
);

// ── Single dropdown menu item ─────────────────────────────────────────────────

const DropdownItem = ({ item, onClose }: { item: MenuAction; onClose: () => void }) => {
  const [subOpen, setSubOpen] = useState(false);
  const hasSub = (item.submenu?.length ?? 0) > 0;
  const Icon = item.icon;

  if (item.separator) {
    return <div className="h-px bg-white/5 my-1 mx-1" />;
  }

  return (
    <div
      className="relative"
      onMouseEnter={() => hasSub && setSubOpen(true)}
      onMouseLeave={() => hasSub && setSubOpen(false)}
    >
      <div
        onClick={() => {
          if (item.disabled || hasSub) return;
          item.onClick?.();
          onClose();
        }}
        className={`flex items-center gap-2 px-2 py-1.5 rounded text-sm transition-colors cursor-pointer
          ${item.disabled
            ? 'text-gray-600 cursor-not-allowed'
            : 'text-gray-300 hover:bg-[#3d4449] hover:text-white'
          }`}
      >
        <span className="w-4 flex items-center justify-center flex-shrink-0 opacity-60">
          {Icon && <Icon size={13} />}
        </span>
        <span className="flex-1 whitespace-nowrap">{item.label}</span>
        {item.shortcut && <Kbd>{item.shortcut}</Kbd>}
        {hasSub && <span className="text-gray-500 text-xs ml-1">›</span>}
      </div>

      {hasSub && subOpen && (
        <div className="absolute left-full top-0 z-[9001] animate-slide-down">
          <DropdownMenuPanel items={item.submenu!} onClose={onClose} />
        </div>
      )}
    </div>
  );
};

// ── Dropdown menu container ───────────────────────────────────────────────────

const DropdownMenuPanel = ({ items, onClose }: { items: MenuAction[]; onClose: () => void }) => (
  <div className="min-w-[220px] bg-[#2d3338] border border-white/[0.07] rounded-lg shadow-2xl p-1 animate-slide-down">
    {items.map((item, i) => (
      <DropdownItem key={i} item={item} onClose={onClose} />
    ))}
  </div>
);

// ── Top-level menu trigger ────────────────────────────────────────────────────

const MenuTrigger = ({
  menu, isOpen, onOpen, onClose, anyOpen,
}: {
  menu: MenuDef;
  isOpen: boolean;
  onOpen: () => void;
  onClose: () => void;
  anyOpen: boolean;
}) => (
  <div className="relative h-full flex items-center">
    <button
      onMouseDown={onOpen}
      onMouseEnter={() => anyOpen && onOpen()}
      className={`h-7 px-2 rounded text-xs font-normal transition-colors cursor-pointer border-none
        ${isOpen ? 'bg-[#3d4449] text-white' : 'text-gray-400 hover:text-white hover:bg-[#3d4449]'}`}
    >
      {menu.label}
    </button>
    {isOpen && (
      <div className="absolute top-full left-0 mt-0.5 z-[9000]">
        <DropdownMenuPanel items={menu.items} onClose={onClose} />
      </div>
    )}
  </div>
);

// ── File Tab ──────────────────────────────────────────────────────────────────

const Tab = ({
  tab, isActive, onClick, onClose,
}: {
  tab: FileTab;
  isActive: boolean;
  onClick: () => void;
  onClose: (id: string) => void;
}) => (
  <div
    onClick={onClick}
    title={tab.fullName ?? tab.name}
    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-colors cursor-pointer flex-shrink-0 max-w-[220px]
      ${isActive
        ? 'bg-[#3d4449] border-white/[0.07] text-white'
        : 'border-transparent text-gray-400 hover:bg-[#3d4449] hover:text-white'
      }`}
  >
    {/* PDF icon — minimal SVG, no emoji */}
    <svg width="13" height="14" viewBox="0 0 13 14" fill="none" className="flex-shrink-0">
      <path d="M2 1h6.5l3 3V13a.5.5 0 01-.5.5H2A.5.5 0 011.5 13V1.5A.5.5 0 012 1z" fill="#ef4444" opacity="0.9"/>
      <path d="M8.5 1v3.5h3" fill="none" stroke="rgba(0,0,0,0.3)" strokeWidth="0.5"/>
    </svg>
    <span className={`text-[13px] truncate flex-1 ${isActive ? 'font-medium' : 'font-normal'}`}>
      {tab.modified && <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-400 mr-1.5 mb-0.5 align-middle" />}
      {tab.name}
    </span>
    <button
      onClick={e => { e.stopPropagation(); onClose(tab.id); }}
      className="w-4 h-4 flex items-center justify-center text-gray-500 hover:text-white flex-shrink-0 rounded transition-colors"
    >
      <X size={11} />
    </button>
  </div>
);

// ── TopBar ────────────────────────────────────────────────────────────────────

export function TopBar({
  tabs = [],
  activeTabId = null,
  onTabClick,
  onTabClose,
  onNewTab,
  menus = [],
}: TopBarProps) {
  const [openMenuIdx, setOpenMenuIdx] = useState<number | null>(null);
  const barRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (barRef.current && !barRef.current.contains(e.target as Node)) {
        setOpenMenuIdx(null);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div className="h-14 bg-[#2d3338] border-b border-[#1e2327] flex items-center justify-between px-4 flex-shrink-0 select-none">

      {/* ── Left: Logo + menus ── */}
      <div className="flex items-center gap-4 flex-shrink-0">
        {/* Logo */}
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 bg-gradient-to-br from-blue-500 to-cyan-400 rounded-md flex items-center justify-center flex-shrink-0">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
              <path d="M8 2L3 5v6l5 3 5-3V5L8 2z" fill="white" opacity="0.9"/>
            </svg>
          </div>
          <span className="font-semibold text-white text-[14px]">
            PDF<span className="text-[#4a90e2]">Edit</span>
          </span>
        </div>

        {/* Menu bar */}
        {menus.length > 0 && (
          <div ref={barRef} className="flex items-center h-full">
            {menus.map((menu, idx) => (
              <MenuTrigger
                key={idx}
                menu={menu}
                isOpen={openMenuIdx === idx}
                anyOpen={openMenuIdx !== null}
                onOpen={() => setOpenMenuIdx(openMenuIdx === idx ? null : idx)}
                onClose={() => setOpenMenuIdx(null)}
              />
            ))}
          </div>
        )}
      </div>

      {/* ── Center: File tabs ── */}
      <div className="flex items-center gap-1.5 flex-1 mx-8 min-w-0 overflow-hidden max-w-2xl">
        {tabs.map(tab => (
          <Tab
            key={tab.id}
            tab={tab}
            isActive={tab.id === activeTabId}
            onClick={() => onTabClick?.(tab.id)}
            onClose={id => onTabClose?.(id)}
          />
        ))}
        <button
          onClick={onNewTab}
          title="Open file (Ctrl+O)"
          className="w-7 h-7 flex items-center justify-center text-gray-400 hover:text-white hover:bg-[#3d4449] rounded transition-colors flex-shrink-0 text-lg leading-none"
        >
          +
        </button>
      </div>

      {/* ── Right: Search + window controls + avatar ── */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <div className="relative">
          <input
            type="text"
            placeholder="Search"
            className="bg-[#1e2327] text-gray-300 placeholder-gray-500 px-3 py-1.5 pr-8 rounded-md text-[12px] w-40 focus:outline-none focus:ring-1 focus:ring-[#4a90e2] transition-all"
          />
          <Search size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
        </div>

        <div className="flex items-center gap-0.5">
          {[
            { Icon: Minimize2, title: 'Minimize', danger: false },
            { Icon: Maximize2, title: 'Maximize', danger: false },
            { Icon: X,         title: 'Close',    danger: true  },
          ].map(({ Icon, title, danger }) => (
            <button
              key={title}
              title={title}
              className={`w-8 h-8 flex items-center justify-center rounded text-gray-400 transition-colors
                ${danger ? 'hover:bg-red-500/20 hover:text-red-400' : 'hover:bg-[#3d4449] hover:text-white'}`}
            >
              <Icon size={13} />
            </button>
          ))}
        </div>

        {/* Avatar */}
        <div className="w-8 h-8 bg-[#4a90e2] rounded-full flex items-center justify-center flex-shrink-0 cursor-pointer">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="white">
            <circle cx="8" cy="6" r="3"/>
            <path d="M2 14c0-3.314 2.686-5 6-5s6 1.686 6 5"/>
          </svg>
        </div>
      </div>
    </div>
  );
}