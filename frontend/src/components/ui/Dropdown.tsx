// components/ui/Dropdown.tsx — Cascading dropdown menu primitive.
// Used by TopBar menu bar and any future context menus.
// Icons are LucideIcon components — no emoji strings.

import { useState, useRef, useEffect } from 'react';
import type { LucideIcon } from 'lucide-react';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface DropdownItem {
  label?: string;
  icon?: LucideIcon;
  shortcut?: string;
  onClick?: () => void;
  disabled?: boolean;
  separator?: true;
  submenu?: DropdownItem[];
}

interface DropdownMenuProps {
  items: DropdownItem[];
  onClose?: () => void;
  /** Tailwind/inline position override, e.g. 'top-full left-0' */
  className?: string;
}

// ── Keyboard shortcut badge ───────────────────────────────────────────────────

const Kbd = ({ children }: { children: string }) => (
  <span className="text-[10px] font-mono text-gray-500 bg-[#1e2327] border border-white/[0.06] rounded px-1 py-0.5 flex-shrink-0 leading-none">
    {children}
  </span>
);

// ── Single menu item ──────────────────────────────────────────────────────────

function MenuItem({ item, onClose }: { item: DropdownItem; onClose?: () => void }) {
  const [subOpen, setSubOpen] = useState(false);
  const [hov, setHov] = useState(false);
  const hasSub = (item.submenu?.length ?? 0) > 0;
  const Icon = item.icon;

  if (item.separator) {
    return <div className="h-px bg-white/[0.06] my-1 mx-1" />;
  }

  return (
    <div
      className="relative"
      onMouseEnter={() => { setHov(true);  if (hasSub) setSubOpen(true);  }}
      onMouseLeave={() => { setHov(false); if (hasSub) setSubOpen(false); }}
    >
      <div
        role="menuitem"
        tabIndex={item.disabled ? -1 : 0}
        onClick={() => {
          if (item.disabled || hasSub) return;
          item.onClick?.();
          onClose?.();
        }}
        onKeyDown={e => {
          if (e.key === 'Enter' || e.key === ' ') {
            if (item.disabled || hasSub) return;
            item.onClick?.();
            onClose?.();
          }
        }}
        className={`flex items-center gap-2 px-2 py-1.5 mx-0.5 rounded text-sm select-none transition-colors
          ${item.disabled
            ? 'text-gray-600 cursor-not-allowed'
            : hov
            ? 'bg-[#3d4449] text-white cursor-pointer'
            : 'text-gray-300 cursor-pointer'
          }`}
      >
        {/* Icon slot — fixed width so labels stay aligned */}
        <span className="w-4 h-4 flex items-center justify-center flex-shrink-0 opacity-60">
          {Icon && <Icon size={13} />}
        </span>

        <span className="flex-1 whitespace-nowrap">{item.label}</span>

        {item.shortcut && <Kbd>{item.shortcut}</Kbd>}
        {hasSub && <span className="text-gray-500 text-xs ml-0.5 leading-none">›</span>}
      </div>

      {/* Submenu */}
      {hasSub && subOpen && (
        <div className="absolute left-full top-0 z-[9001]">
          <DropdownMenu items={item.submenu!} onClose={onClose} />
        </div>
      )}
    </div>
  );
}

// ── DropdownMenu ──────────────────────────────────────────────────────────────

export function DropdownMenu({ items, onClose, className = '' }: DropdownMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose?.();
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose?.();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div
      ref={menuRef}
      role="menu"
      className={`min-w-[220px] bg-[#2d3338] border border-white/[0.07] rounded-lg shadow-2xl p-1 animate-slide-down ${className}`}
    >
      {items.map((item, i) => (
        <MenuItem key={i} item={item} onClose={onClose} />
      ))}
    </div>
  );
}

// ── DropdownTrigger ───────────────────────────────────────────────────────────
// Convenience wrapper: renders a button that toggles a DropdownMenu below it.

interface DropdownTriggerProps {
  label: React.ReactNode;
  items: DropdownItem[];
  /** Additional classes on the trigger button */
  buttonClassName?: string;
}

export function DropdownTrigger({ label, items, buttonClassName = '' }: DropdownTriggerProps) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={wrapRef} className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className={`h-7 px-2 rounded text-xs transition-colors
          ${open ? 'bg-[#3d4449] text-white' : 'text-gray-400 hover:text-white hover:bg-[#3d4449]'}
          ${buttonClassName}`}
      >
        {label}
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-0.5 z-[9000]">
          <DropdownMenu items={items} onClose={() => setOpen(false)} />
        </div>
      )}
    </div>
  );
}