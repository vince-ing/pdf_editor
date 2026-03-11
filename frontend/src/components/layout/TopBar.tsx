// frontend/src/components/layout/TopBar.tsx
import { Minimize2, Maximize2, X, Undo2, Redo2, Menu, Lightbulb, Save, Printer, Settings, PanelLeft, PanelRight } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import type { MenuDef, MenuAction } from '../../constants/menuDefs';
import { useTheme } from '../../theme';

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
  onSave?: () => void;
  onPrint?: () => void;
  onSettings?: () => void;
  menus?: MenuDef[];
  onToggleMobileSidebar?: () => void;
  onToggleMobileRightPanel?: () => void;
}

// ── Kbd ───────────────────────────────────────────────────────────────────────

const Kbd = ({ children }: { children: string }) => {
  const { theme: t } = useTheme();
  return (
    <span style={{
      fontSize: '10px', fontFamily: 'monospace',
      color: t.colors.textMuted,
      backgroundColor: 'rgba(0,0,0,0.3)',
      border: `1px solid ${t.colors.border}`,
      borderRadius: t.radius.xs,
      padding: '1px 4px', flexShrink: 0,
    }}>
      {children}
    </span>
  );
};

// ── DropdownItem ──────────────────────────────────────────────────────────────

const DropdownItem = ({ item, onClose, keepOpen = false }: { item: MenuAction; onClose: () => void; keepOpen?: boolean }) => {
  const { theme: t } = useTheme();
  const [hov, setHov] = useState(false);
  const [subPos, setSubPos] = useState<{ top: number; left: number; rowRight: number } | null>(null);
  const rowRef = useRef<HTMLDivElement>(null);
  const leaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hasSub = (item.submenu?.length ?? 0) > 0;
  const Icon = item.icon;

  const cancelLeave = () => { if (leaveTimer.current) { clearTimeout(leaveTimer.current); leaveTimer.current = null; } };

  const showSub = () => {
    cancelLeave();
    if (!hasSub || !rowRef.current) return;
    const rect = rowRef.current.getBoundingClientRect();
    setSubPos({ top: rect.top, left: rect.right, rowRight: rect.right });
    setHov(true);
  };

  const schedulHide = () => {
    leaveTimer.current = setTimeout(() => { setSubPos(null); setHov(false); }, 100);
  };

  useEffect(() => () => { if (leaveTimer.current) clearTimeout(leaveTimer.current); }, []);

  if (item.separator) return (
    <div style={{ height: '1px', backgroundColor: t.colors.border, margin: '3px 4px' }} />
  );

  return (
    <div ref={rowRef} onMouseEnter={showSub} onMouseLeave={schedulHide}>
      <div
        onClick={() => { if (item.disabled || hasSub) return; item.onClick?.(); if (!keepOpen) onClose(); }}
        style={{
          display: 'flex', alignItems: 'center', gap: '8px',
          padding: '5px 8px', borderRadius: t.radius.sm,
          backgroundColor: hov && !item.disabled ? t.colors.bgHover : 'transparent',
          color: item.disabled ? t.colors.textDisabled : t.colors.textPrimary,
          cursor: item.disabled ? 'not-allowed' : 'pointer',
          fontSize: '12px', transition: t.t.fast, userSelect: 'none',
        }}
      >
        <span style={{ width: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, opacity: 0.65 }}>
          {Icon && <Icon size={13} />}
        </span>
        <span style={{ flex: 1, whiteSpace: 'nowrap' }}>{item.label}</span>
        {item.shortcut && <Kbd>{item.shortcut}</Kbd>}
        {hasSub && <span style={{ color: t.colors.textMuted, fontSize: '10px', marginLeft: '4px' }}>›</span>}
      </div>

      {hasSub && subPos && createPortal(
        <div
          data-submenu-portal
          style={{ position: 'fixed', top: subPos.top, left: subPos.left, zIndex: 9999, paddingLeft: '6px' }}
          onMouseEnter={cancelLeave}
          onMouseLeave={schedulHide}
        >
          <DropdownPanel items={item.submenu!} onClose={onClose} keepOpenOnClick={true} />
        </div>,
        document.body
      )}
    </div>
  );
};

// ── DropdownPanel ─────────────────────────────────────────────────────────────

const DropdownPanel = ({ items, onClose, keepOpenOnClick = false }: { items: MenuAction[]; onClose: () => void; keepOpenOnClick?: boolean }) => {
  const { theme: t } = useTheme();
  return (
    <div style={{
      minWidth: '220px',
      backgroundColor: t.colors.bgRaised,
      border: `1px solid ${t.colors.borderMid}`,
      borderRadius: t.radius.md,
      boxShadow: t.shadow.menu,
      overflow: 'visible',
    }}>
      <div style={{ maxHeight: '60vh', overflowY: 'auto', padding: '4px', borderRadius: t.radius.md }}>
        {items.map((item, i) => <DropdownItem key={i} item={item} onClose={onClose} keepOpen={keepOpenOnClick} />)}
      </div>
    </div>
  );
};

// ── AppMenu ───────────────────────────────────────────────────────────────────

const AppMenu = ({ menus, onClose }: { menus: MenuDef[]; onClose: () => void }) => {
  const { theme: t } = useTheme();
  return (
    <div style={{
      minWidth: '240px',
      backgroundColor: t.colors.bgRaised,
      border: `1px solid ${t.colors.borderMid}`,
      borderRadius: t.radius.md,
      boxShadow: t.shadow.menu,
      overflow: 'visible',
    }}>
      <div style={{ maxHeight: '70vh', overflowY: 'auto', padding: '4px', borderRadius: t.radius.md }}>
        {menus.map((menu, mi) => (
          <div key={mi}>
            {mi > 0 && <div style={{ height: '1px', backgroundColor: t.colors.border, margin: '3px 4px' }} />}
            <div style={{ padding: '5px 10px 3px' }}>
              <span style={{
                fontSize: '10px', textTransform: 'uppercase',
                letterSpacing: '0.08em', fontWeight: 600,
                color: t.colors.textMuted,
              }}>
                {menu.label}
              </span>
            </div>
            {menu.items.map((item, ii) => <DropdownItem key={ii} item={item} onClose={onClose} />)}
          </div>
        ))}
      </div>
    </div>
  );
};

// ── Tab ───────────────────────────────────────────────────────────────────────

const Tab = ({ tab, isActive, onClick, onClose }: {
  tab: FileTab; isActive: boolean; onClick: () => void; onClose: (id: string) => void;
}) => {
  const { theme: t } = useTheme();
  const [hov, setHov] = useState(false);
  
  return (
    <div
      onClick={onClick}
      title={tab.fullName ?? tab.name}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        position: 'relative',
        display: 'flex', alignItems: 'center', gap: '8px',
        padding: '8px 14px',
        borderRadius: '8px 8px 0 0',
        backgroundColor: isActive ? t.colors.bgRaised : hov ? t.colors.bgHover : 'transparent',
        color: isActive ? t.colors.textPrimary : t.colors.textSecondary,
        cursor: 'pointer', flexShrink: 0, maxWidth: '220px',
        transition: t.t.fast, userSelect: 'none',
        transform: isActive ? 'translateY(1px)' : 'none',
        zIndex: isActive ? 10 : 1,
        border: 'none',
      }}
    >
      {/* ── Outer flares (concave bottom curves) to bridge into the toolbar ── */}
      {isActive && (
        <>
          <div style={{
            position: 'absolute', bottom: 0, left: -8, width: 8, height: 8,
            backgroundImage: `radial-gradient(circle at 0% 0%, transparent 8px, ${t.colors.bgRaised} 8px)`,
            pointerEvents: 'none'
          }} />
          <div style={{
            position: 'absolute', bottom: 0, right: -8, width: 8, height: 8,
            backgroundImage: `radial-gradient(circle at 100% 0%, transparent 8px, ${t.colors.bgRaised} 8px)`,
            pointerEvents: 'none'
          }} />
        </>
      )}

      <svg width="13" height="14" viewBox="0 0 13 14" fill="none" style={{ flexShrink: 0 }}>
        <path d="M2 1h6.5l3 3V13a.5.5 0 01-.5.5H2A.5.5 0 011.5 13V1.5A.5.5 0 012 1z" fill="#ef4444" opacity="0.9"/>
        <path d="M8.5 1v3.5h3" fill="none" stroke="rgba(0,0,0,0.3)" strokeWidth="0.5"/>
      </svg>
      <span style={{ fontSize: '13px', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: isActive ? 600 : 500 }}>
        {tab.modified && <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#f59e0b', marginRight: '6px', verticalAlign: 'middle' }} />}
        {tab.name}
      </span>
      <button
        onClick={e => { e.stopPropagation(); onClose(tab.id); }}
        style={{
          width: '18px', height: '18px', display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: isActive ? t.colors.textSecondary : t.colors.textMuted, background: 'none', border: 'none', cursor: 'pointer',
          borderRadius: t.radius.sm, flexShrink: 0, padding: 0,
        }}
        onMouseEnter={e => { (e.currentTarget as HTMLElement).style.backgroundColor = 'rgba(0,0,0,0.08)'; (e.currentTarget as HTMLElement).style.color = t.colors.textPrimary; }}
        onMouseLeave={e => { (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'; (e.currentTarget as HTMLElement).style.color = isActive ? t.colors.textSecondary : t.colors.textMuted; }}
      >
        <X size={12} />
      </button>
    </div>
  );
};

// ── TopBar ────────────────────────────────────────────────────────────────────

export function TopBar({
  tabs = [], activeTabId = null,
  onTabClick, onTabClose, onNewTab,
  onUndo, onRedo, onSave, onPrint, onSettings,
  menus = [], onToggleMobileSidebar, onToggleMobileRightPanel
}: TopBarProps) {
  const { theme: t } = useTheme();
  
  // Track portaled menu coordinates instead of just booleans
  const [menuPos, setMenuPos] = useState<{ top: number; left: number } | null>(null);
  const [helpPos, setHelpPos] = useState<{ top: number; left: number } | null>(null);
  
  const menuRef = useRef<HTMLDivElement>(null);
  const helpRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      // Ignore clicks inside any portaled submenus or main menus
      if ((e.target as HTMLElement)?.closest?.('[data-submenu-portal]')) return;
      if ((e.target as HTMLElement)?.closest?.('[data-main-menu-portal]')) return;

      // Close if click is outside the trigger buttons
      if (menuRef.current && !menuRef.current.contains(target)) setMenuPos(null);
      if (helpRef.current && !helpRef.current.contains(target)) setHelpPos(null);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const helpMenu = menus.find(m => m.label === 'Help');
  const appMenus = menus.filter(m => m.label !== 'Help');

  const handleMenuClick = () => {
    if (menuPos) setMenuPos(null);
    else if (menuRef.current) {
      const rect = menuRef.current.getBoundingClientRect();
      setMenuPos({ top: rect.bottom + 4, left: Math.max(4, rect.left) });
    }
  };

  const handleHelpClick = () => {
    if (helpPos) setHelpPos(null);
    else if (helpRef.current) {
      const rect = helpRef.current.getBoundingClientRect();
      setHelpPos({ top: rect.bottom + 4, left: Math.max(4, rect.left - 100) }); // shift left so it doesn't overflow right edge
    }
  };

  return (
    <div className="w-full flex items-end shrink-0 select-none border-b" style={{
      height: '48px',
      backgroundColor: t.colors.bgBase,
      borderColor: t.colors.border,
    }}>

      {/* ── Left side tools (Scrollable on mobile, max 55% of screen width) ── */}
      <div className="w-auto md:w-[264px] h-full flex items-center px-2 shrink-0 box-border border-r border-transparent md:border-inherit overflow-x-auto scrollbar-hide max-w-[55vw] md:max-w-none">
        
        <div className="flex items-center gap-[2px] shrink-0">
          
          {/* Mobile Sidebar Toggle Button */}
          <div className="md:hidden flex items-center shrink-0">
            <TopBarBtn onClick={onToggleMobileSidebar} title="Files" size={32}>
              <PanelLeft size={18} />
            </TopBarBtn>
          </div>

          {/* Hamburger / App Menu (Portaled) */}
          <div ref={menuRef} className="relative shrink-0 flex items-center">
            <TopBarBtn onClick={handleMenuClick} title="Menu" active={!!menuPos} size={36}>
              <Menu size={18} />
            </TopBarBtn>
            {menuPos && createPortal(
              <div data-main-menu-portal style={{ position: 'fixed', top: menuPos.top, left: menuPos.left, zIndex: 9000 }}>
                <AppMenu menus={appMenus} onClose={() => setMenuPos(null)} />
              </div>,
              document.body
            )}
          </div>
          
          <div className="hidden md:block w-px h-4 bg-inherit border-l mx-1 shrink-0" style={{ borderColor: t.colors.border }} />

          {/* Undo / Redo - Hidden on mobile to save space (accessible via edit tools) */}
          <div className="hidden sm:flex items-center gap-[2px] shrink-0">
             <TopBarBtn onClick={onUndo} title="Undo (Ctrl+Z)"><Undo2 size={16} /></TopBarBtn>
             <TopBarBtn onClick={onRedo} title="Redo (Ctrl+Y)"><Redo2 size={16} /></TopBarBtn>
             <div className="w-px h-4 bg-inherit border-l mx-1 shrink-0" style={{ borderColor: t.colors.border }} />
          </div>

          {/* Save */}
          <TopBarBtn onClick={onSave} title="Save (Ctrl+S)"><Save size={16} /></TopBarBtn>
          
          {/* Print - Hidden on mobile */}
          <div className="hidden sm:flex shrink-0">
             <TopBarBtn onClick={onPrint} title="Print (Ctrl+P)"><Printer size={16} /></TopBarBtn>
          </div>

          {/* Settings - VISIBLE ON MOBILE */}
          <TopBarBtn onClick={onSettings} title="Settings"><Settings size={16} /></TopBarBtn>

          {/* Help - Portaled */}
          {helpMenu && (
            <div ref={helpRef} className="relative shrink-0 flex items-center">
              <TopBarBtn onClick={handleHelpClick} title="Help" active={!!helpPos} accentColor="#f59e0b">
                <Lightbulb size={16} />
              </TopBarBtn>
              {helpPos && createPortal(
                <div data-main-menu-portal style={{ position: 'fixed', top: helpPos.top, left: helpPos.left, zIndex: 9000 }}>
                  <DropdownPanel items={helpMenu.items} onClose={() => setHelpPos(null)} />
                </div>,
                document.body
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── File tabs (Scrollable) ── */}
      <div className="flex items-end gap-[2px] flex-1 min-w-0 overflow-x-auto overflow-y-hidden scrollbar-hide md:pl-4 px-2" style={{ WebkitOverflowScrolling: 'touch' }}>
        {tabs.map(tab => (
          <Tab key={tab.id} tab={tab}
            isActive={tab.id === activeTabId}
            onClick={() => onTabClick?.(tab.id)}
            onClose={id => onTabClose?.(id)}
          />
        ))}
        {/* Open new file button aligned center with tools */}
        <div className="flex items-center h-12 pl-[6px] shrink-0">
          <TopBarBtn onClick={onNewTab} title="Open file (Ctrl+O)" style={{ fontSize: '18px' }} size={32}>+</TopBarBtn>
        </div>
      </div>

      {/* ── Right side ── */}
      <div className="flex items-center h-12 gap-[6px] shrink-0 pr-2">
         {/* Mobile Right Panel Toggle */}
         <div className="md:hidden flex items-center ml-1 shrink-0">
            <TopBarBtn onClick={onToggleMobileRightPanel} title="Properties" size={32}>
               <PanelRight size={18} />
            </TopBarBtn>
         </div>

        {/* Window controls (hidden on small screens to save space) */}
        <div className="hidden sm:flex items-center gap-[6px] shrink-0">
            {[
            { Icon: Minimize2, title: 'Minimize', danger: false },
            { Icon: Maximize2, title: 'Maximize', danger: false },
            { Icon: X,         title: 'Close',    danger: true  },
            ].map(({ Icon, title, danger }) => (
            <TopBarBtn key={title} title={title} danger={danger}><Icon size={13} /></TopBarBtn>
            ))}
        </div>
      </div>
    </div>
  );
}

// ── Shared icon button for the top bar ───────────────────────────────────────

function TopBarBtn({ children, onClick, title, active = false, danger = false, accentColor, size = 32, style: sx }: {
  children: React.ReactNode;
  onClick?: () => void;
  title?: string;
  active?: boolean;
  danger?: boolean;
  accentColor?: string;
  size?: number;
  style?: React.CSSProperties;
}) {
  const { theme: t } = useTheme();
  const [hov, setHov] = useState(false);

  const bg = hov
    ? danger ? 'rgba(239,68,68,0.15)' : t.colors.bgHover
    : active ? t.colors.bgHover : 'transparent';

  const color = hov
    ? danger ? '#f87171' : accentColor ?? t.colors.textPrimary
    : active
      ? accentColor ?? t.colors.textPrimary
      : t.colors.textSecondary;

  return (
    <button
      onClick={onClick} title={title}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        width: size, height: size,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        borderRadius: t.radius.sm, border: 'none', cursor: 'pointer',
        backgroundColor: bg, color,
        transition: t.t.fast, flexShrink: 0,
        ...sx,
      }}
    >
      {children}
    </button>
  );
}