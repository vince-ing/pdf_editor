// components/layout/TopBar.tsx
import { Search, Minimize2, Maximize2, X, Undo2, Redo2, Menu, Lightbulb } from 'lucide-react';
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
  menus?: MenuDef[];
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

  // Clean up timer on unmount
  useEffect(() => () => { if (leaveTimer.current) clearTimeout(leaveTimer.current); }, []);

  if (item.separator) return (
    <div style={{ height: '1px', backgroundColor: t.colors.border, margin: '3px 4px' }} />
  );

  return (
    <div ref={rowRef}
      onMouseEnter={showSub}
      onMouseLeave={schedulHide}
    >
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

// ── DropdownPanel — scrollable ────────────────────────────────────────────────

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

// ── AppMenu — all menus grouped, scrollable ───────────────────────────────────

const AppMenu = ({ menus, onClose }: { menus: MenuDef[]; onClose: () => void }) => {
  const { theme: t } = useTheme();
  return (
    // Outer shell: overflow VISIBLE so absolute submenus aren't clipped
    <div style={{
      minWidth: '240px',
      backgroundColor: t.colors.bgRaised,
      border: `1px solid ${t.colors.borderMid}`,
      borderRadius: t.radius.md,
      boxShadow: t.shadow.menu,
      overflow: 'visible',
    }}>
      {/* Inner scroll wrapper — only this scrolls */}
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
        display: 'flex', alignItems: 'center', gap: '8px',
        padding: '5px 10px', borderRadius: t.radius.md,
        border: `1px solid ${isActive ? t.colors.borderMid : 'transparent'}`,
        backgroundColor: isActive ? t.colors.bgRaised : hov ? t.colors.bgHover : 'transparent',
        color: isActive ? t.colors.textPrimary : t.colors.textSecondary,
        cursor: 'pointer', flexShrink: 0, maxWidth: '220px',
        transition: t.t.fast, userSelect: 'none',
      }}
    >
      <svg width="13" height="14" viewBox="0 0 13 14" fill="none" style={{ flexShrink: 0 }}>
        <path d="M2 1h6.5l3 3V13a.5.5 0 01-.5.5H2A.5.5 0 011.5 13V1.5A.5.5 0 012 1z" fill="#ef4444" opacity="0.9"/>
        <path d="M8.5 1v3.5h3" fill="none" stroke="rgba(0,0,0,0.3)" strokeWidth="0.5"/>
      </svg>
      <span style={{ fontSize: '13px', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: isActive ? 500 : 400 }}>
        {tab.modified && <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#f59e0b', marginRight: '6px', verticalAlign: 'middle' }} />}
        {tab.name}
      </span>
      <button
        onClick={e => { e.stopPropagation(); onClose(tab.id); }}
        style={{
          width: '16px', height: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: t.colors.textMuted, background: 'none', border: 'none', cursor: 'pointer',
          borderRadius: t.radius.xs, flexShrink: 0, padding: 0,
        }}
      >
        <X size={11} />
      </button>
    </div>
  );
};

// ── TopBar ────────────────────────────────────────────────────────────────────

export function TopBar({
  tabs = [], activeTabId = null,
  onTabClick, onTabClose, onNewTab,
  onUndo, onRedo,
  menus = [],
}: TopBarProps) {
  const { theme: t } = useTheme();
  const [menuOpen, setMenuOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const helpRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      // Ignore clicks inside portalled submenus (they are stamped with data-submenu-portal)
      if ((e.target as HTMLElement)?.closest?.('[data-submenu-portal]')) return;
      if (menuRef.current && !menuRef.current.contains(target)) setMenuOpen(false);
      if (helpRef.current && !helpRef.current.contains(target)) setHelpOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const helpMenu = menus.find(m => m.label === 'Help');
  const appMenus = menus.filter(m => m.label !== 'Help');

  return (
    <div style={{
      height: '48px',
      backgroundColor: t.colors.bgBase,
      borderBottom: `1px solid ${t.colors.border}`,
      display: 'flex', alignItems: 'center', gap: '4px',
      padding: '0 8px', flexShrink: 0, userSelect: 'none',
    }}>

      {/* ── Hamburger ── */}
      <div ref={menuRef} style={{ position: 'relative', flexShrink: 0 }}>
        <TopBarBtn onClick={() => setMenuOpen(o => !o)} title="Menu" active={menuOpen} size={36}>
          <Menu size={18} />
        </TopBarBtn>
        {menuOpen && (
          <div style={{ position: 'absolute', top: '100%', left: 0, marginTop: '4px', zIndex: 9000 }}>
            <AppMenu menus={appMenus} onClose={() => setMenuOpen(false)} />
          </div>
        )}
      </div>

      {/* ── Undo / Redo ── */}
      <TopBarBtn onClick={onUndo} title="Undo (Ctrl+Z)"><Undo2 size={16} /></TopBarBtn>
      <TopBarBtn onClick={onRedo} title="Redo (Ctrl+Y)"><Redo2 size={16} /></TopBarBtn>

      <div style={{ width: '1px', height: '20px', backgroundColor: t.colors.border, margin: '0 8px', flexShrink: 0 }} />

      {/* ── File tabs ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flex: 1, minWidth: 0, overflow: 'hidden' }}>
        {tabs.map(tab => (
          <Tab key={tab.id} tab={tab}
            isActive={tab.id === activeTabId}
            onClick={() => onTabClick?.(tab.id)}
            onClose={id => onTabClose?.(id)}
          />
        ))}
        <TopBarBtn onClick={onNewTab} title="Open file (Ctrl+O)" style={{ fontSize: '18px' }}>+</TopBarBtn>
      </div>

      {/* ── Right side ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>

        {/* Search */}
        <div style={{ position: 'relative' }}>
          <input
            type="text"
            placeholder="Global Search"
            style={{
              backgroundColor: t.colors.bgHover,
              color: t.colors.textPrimary,
              border: `1px solid ${t.colors.border}`,
              borderRadius: t.radius.sm,
              padding: '5px 28px 5px 10px',
              fontSize: '12px', width: '176px', outline: 'none',
              fontFamily: t.fonts.ui,
              transition: t.t.fast,
            }}
            onFocus={e => (e.currentTarget.style.borderColor = t.colors.accent)}
            onBlur={e => (e.currentTarget.style.borderColor = t.colors.border)}
          />
          <Search size={13} style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', color: t.colors.textMuted, pointerEvents: 'none' }} />
        </div>

        {/* Help / lightbulb */}
        {helpMenu && (
          <div ref={helpRef} style={{ position: 'relative', flexShrink: 0 }}>
            <TopBarBtn onClick={() => setHelpOpen(o => !o)} title="Help" active={helpOpen} accentColor="#f59e0b">
              <Lightbulb size={16} />
            </TopBarBtn>
            {helpOpen && (
              <div style={{ position: 'absolute', top: '100%', right: 0, marginTop: '4px', zIndex: 9000 }}>
                <DropdownPanel items={helpMenu.items} onClose={() => setHelpOpen(false)} />
              </div>
            )}
          </div>
        )}

        <div style={{ width: '1px', height: '20px', backgroundColor: t.colors.border, margin: '0 2px', flexShrink: 0 }} />

        {/* Window controls */}
        {[
          { Icon: Minimize2, title: 'Minimize', danger: false },
          { Icon: Maximize2, title: 'Maximize', danger: false },
          { Icon: X,         title: 'Close',    danger: true  },
        ].map(({ Icon, title, danger }) => (
          <TopBarBtn key={title} title={title} danger={danger}><Icon size={13} /></TopBarBtn>
        ))}
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