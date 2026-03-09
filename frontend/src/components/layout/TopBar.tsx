// components/layout/TopBar.tsx
// Same dark bg as sidebar rail (#1e2327). Hamburger + undo/redo flush left, file tabs center, search right.

import { Search, Minimize2, Maximize2, X, Undo2, Redo2, Menu, Lightbulb } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import type { MenuDef, MenuAction } from '../../constants/menuDefs';

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
  onUndo?: () => void;
  onRedo?: () => void;
  menus?: MenuDef[];
}

// ── Dropdown helpers ──────────────────────────────────────────────────────────

const Kbd = ({ children }: { children: string }) => (
  <span className="text-[10px] font-mono text-gray-500 bg-black/30 border border-white/5 rounded px-1 py-0.5 flex-shrink-0">
    {children}
  </span>
);

const DropdownItem = ({ item, onClose }: { item: MenuAction; onClose: () => void }) => {
  const [subOpen, setSubOpen] = useState(false);
  const hasSub = (item.submenu?.length ?? 0) > 0;
  const Icon = item.icon;
  if (item.separator) return <div className="h-px bg-white/5 my-1 mx-1" />;
  return (
    <div className="relative"
      onMouseEnter={() => hasSub && setSubOpen(true)}
      onMouseLeave={() => hasSub && setSubOpen(false)}>
      <div
        onClick={() => { if (item.disabled || hasSub) return; item.onClick?.(); onClose(); }}
        className={`flex items-center gap-2 px-2 py-1.5 rounded text-sm transition-colors cursor-pointer
          ${item.disabled ? 'text-gray-600 cursor-not-allowed' : 'text-gray-300 hover:bg-[#3d4449] hover:text-white'}`}
      >
        <span className="w-4 flex items-center justify-center flex-shrink-0 opacity-60">
          {Icon && <Icon size={13} />}
        </span>
        <span className="flex-1 whitespace-nowrap">{item.label}</span>
        {item.shortcut && <Kbd>{item.shortcut}</Kbd>}
        {hasSub && <span className="text-gray-500 text-xs ml-1">›</span>}
      </div>
      {hasSub && subOpen && (
        <div className="absolute left-full top-0 z-[9001]">
          <DropdownPanel items={item.submenu!} onClose={onClose} />
        </div>
      )}
    </div>
  );
};

const DropdownPanel = ({ items, onClose }: { items: MenuAction[]; onClose: () => void }) => (
  <div className="min-w-[220px] bg-[#2d3338] border border-white/[0.07] rounded-lg shadow-2xl p-1 animate-slide-down">
    {items.map((item, i) => <DropdownItem key={i} item={item} onClose={onClose} />)}
  </div>
);

const AppMenu = ({ menus, onClose }: { menus: MenuDef[]; onClose: () => void }) => (
  <div className="min-w-[240px] bg-[#2d3338] border border-white/[0.07] rounded-lg shadow-2xl p-1 animate-slide-down">
    {menus.map((menu, mi) => (
      <div key={mi}>
        {mi > 0 && <div className="h-px bg-white/5 my-1 mx-1" />}
        <div className="px-3 py-1.5">
          <span className="text-[10px] uppercase tracking-widest font-semibold text-gray-500">{menu.label}</span>
        </div>
        {menu.items.map((item, ii) => <DropdownItem key={ii} item={item} onClose={onClose} />)}
      </div>
    ))}
  </div>
);

// ── File Tab ──────────────────────────────────────────────────────────────────

const Tab = ({ tab, isActive, onClick, onClose }: {
  tab: FileTab; isActive: boolean; onClick: () => void; onClose: (id: string) => void;
}) => (
  <div
    onClick={onClick}
    title={tab.fullName ?? tab.name}
    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-colors cursor-pointer flex-shrink-0 max-w-[220px]
      ${isActive
        ? 'bg-[#2d3338] border-white/[0.07] text-white'
        : 'border-transparent text-gray-400 hover:bg-[#2d3338] hover:text-white'
      }`}
  >
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
  tabs = [], activeTabId = null,
  onTabClick, onTabClose, onNewTab,
  onUndo, onRedo,
  menus = [],
}: TopBarProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const helpRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
      if (helpRef.current && !helpRef.current.contains(e.target as Node)) setHelpOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const helpMenu = menus.find(m => m.label === 'Help');
  const appMenus = menus.filter(m => m.label !== 'Help');

  return (
    // Same dark color as the sidebar icon rail (#1e2327)
    <div className="h-12 bg-[#1e2327] border-b border-black/30 flex items-center gap-1 px-2 flex-shrink-0 select-none">

      {/* ── Hamburger ── */}
      <div ref={menuRef} className="relative flex-shrink-0">
        <button
          onClick={() => setMenuOpen(o => !o)}
          title="Menu"
          className={`w-9 h-9 flex items-center justify-center rounded transition-colors
            ${menuOpen ? 'bg-[#2d3338] text-white' : 'text-gray-500 hover:bg-[#2d3338] hover:text-white'}`}
        >
          <Menu size={18} />
        </button>
        {menuOpen && (
          <div className="absolute top-full left-0 mt-1 z-[9000]">
            <AppMenu menus={appMenus} onClose={() => setMenuOpen(false)} />
          </div>
        )}
      </div>

      {/* ── Undo / Redo ── */}
      <button onClick={onUndo} title="Undo (Ctrl+Z)"
        className="w-8 h-8 flex items-center justify-center rounded text-gray-500 hover:bg-[#2d3338] hover:text-white transition-colors flex-shrink-0">
        <Undo2 size={16} />
      </button>
      <button onClick={onRedo} title="Redo (Ctrl+Y)"
        className="w-8 h-8 flex items-center justify-center rounded text-gray-500 hover:bg-[#2d3338] hover:text-white transition-colors flex-shrink-0">
        <Redo2 size={16} />
      </button>

      <div className="w-px h-5 bg-white/[0.06] mx-2 flex-shrink-0" />

      {/* ── File tabs ── */}
      <div className="flex items-center gap-1.5 flex-1 min-w-0 overflow-hidden">
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
          className="w-7 h-7 flex items-center justify-center text-gray-500 hover:text-white hover:bg-[#2d3338] rounded transition-colors flex-shrink-0 text-lg leading-none"
        >
          +
        </button>
      </div>

      {/* ── Right: Search + lightbulb + window controls ── */}
      <div className="flex items-center gap-1.5 flex-shrink-0">

        {/* Search — lighter grey like the reference */}
        <div className="relative">
          <input
            type="text"
            placeholder="Global Search"
            className="bg-[#3d4449] text-gray-200 placeholder-gray-400 px-3 py-1.5 pr-8 rounded-md text-[12px] w-44 focus:outline-none focus:ring-1 focus:ring-[#4a90e2] transition-all"
          />
          <Search size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
        </div>

        {/* Lightbulb / help */}
        {helpMenu && (
          <div ref={helpRef} className="relative flex-shrink-0">
            <button
              onClick={() => setHelpOpen(o => !o)}
              title="Help"
              className={`w-8 h-8 flex items-center justify-center rounded transition-colors
                ${helpOpen ? 'bg-[#2d3338] text-amber-400' : 'text-gray-500 hover:bg-[#2d3338] hover:text-amber-400'}`}
            >
              <Lightbulb size={16} />
            </button>
            {helpOpen && (
              <div className="absolute top-full right-0 mt-1 z-[9000]">
                <DropdownPanel items={helpMenu.items} onClose={() => setHelpOpen(false)} />
              </div>
            )}
          </div>
        )}

        <div className="w-px h-5 bg-white/[0.06] mx-0.5 flex-shrink-0" />

        {/* Window controls */}
        {[
          { Icon: Minimize2, title: 'Minimize', danger: false },
          { Icon: Maximize2, title: 'Maximize', danger: false },
          { Icon: X,         title: 'Close',    danger: true  },
        ].map(({ Icon, title, danger }) => (
          <button key={title} title={title}
            className={`w-8 h-8 flex items-center justify-center rounded text-gray-500 transition-colors
              ${danger ? 'hover:bg-red-500/20 hover:text-red-400' : 'hover:bg-[#2d3338] hover:text-white'}`}>
            <Icon size={13} />
          </button>
        ))}
      </div>
    </div>
  );
}