// components/ui/Button.tsx — Reusable button primitives.
// IconButton: square icon-only button.
// Button: text button with optional leading icon (LucideIcon).
// All variants use design tokens via Tailwind arbitrary values.

import { useState } from 'react';
import type { LucideIcon } from 'lucide-react';

// ── Shared types ──────────────────────────────────────────────────────────────

type ButtonVariant = 'ghost' | 'solid' | 'accent' | 'danger' | 'success';
type ButtonSize    = 'xs' | 'sm' | 'md' | 'lg';

// ── IconButton ────────────────────────────────────────────────────────────────
// Square icon-only button. Pass a Lucide component as `icon`.

interface IconButtonProps {
  icon: LucideIcon;
  onClick?: () => void;
  title?: string;
  disabled?: boolean;
  variant?: ButtonVariant;
  size?: ButtonSize;
  active?: boolean;
  className?: string;
}

const ICON_SIZE_PX: Record<ButtonSize, number> = { xs: 22, sm: 26, md: 30, lg: 34 };
const ICON_FS_PX:   Record<ButtonSize, number> = { xs: 11, sm: 13, md: 15, lg: 17 };

export function IconButton({
  icon: Icon,
  onClick,
  title,
  disabled = false,
  variant = 'ghost',
  size = 'md',
  active = false,
  className = '',
}: IconButtonProps) {
  const [hov, setHov] = useState(false);
  const dim = ICON_SIZE_PX[size];
  const fs  = ICON_FS_PX[size];

  const bg = {
    ghost:   active      ? 'bg-[#3d4449]'        : hov && !disabled ? 'bg-[#2d3338]'        : 'bg-transparent',
    solid:   hov && !disabled ? 'bg-[#3d4449]'   : 'bg-[#2d3338]',
    accent:  active || (hov && !disabled) ? 'bg-[#4a90e2]' : 'bg-[#4a90e2]/15',
    danger:  hov && !disabled ? 'bg-red-500/20'  : 'bg-transparent',
    success: hov && !disabled ? 'bg-green-600'   : 'bg-green-500',
  }[variant];

  const textColor = disabled ? 'text-gray-600' : {
    ghost:   active      ? 'text-white'     : hov ? 'text-white'     : 'text-gray-400',
    solid:   'text-white',
    accent:  active || hov ? 'text-white'   : 'text-[#4a90e2]',
    danger:  'text-red-400',
    success: 'text-[#0a1f17]',
  }[variant];

  const border = active && variant === 'ghost' ? 'border border-white/10' : 'border border-transparent';

  return (
    <button
      title={title}
      disabled={disabled}
      onClick={disabled ? undefined : onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{ width: dim, height: dim, minWidth: dim }}
      className={`flex items-center justify-center rounded transition-colors flex-shrink-0
        ${bg} ${textColor} ${border}
        ${disabled ? 'cursor-not-allowed' : 'cursor-pointer'}
        ${className}`}
    >
      <Icon size={fs} />
    </button>
  );
}

// ── Button ────────────────────────────────────────────────────────────────────
// Text button with optional leading Lucide icon.

interface ButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  title?: string;
  disabled?: boolean;
  icon?: LucideIcon;
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
}

const BTN_H:  Record<ButtonSize, string> = { xs: 'h-6',  sm: 'h-7',  md: 'h-8',  lg: 'h-9'  };
const BTN_FS: Record<ButtonSize, string> = { xs: 'text-[10px]', sm: 'text-[11px]', md: 'text-xs', lg: 'text-sm' };
const BTN_PX: Record<ButtonSize, string> = { xs: 'px-2', sm: 'px-2.5', md: 'px-3', lg: 'px-4' };

const ICON_PX: Record<ButtonSize, number> = { xs: 11, sm: 12, md: 13, lg: 15 };

export function Button({
  children,
  onClick,
  title,
  disabled = false,
  icon: Icon,
  variant = 'ghost',
  size = 'md',
  className = '',
}: ButtonProps) {
  const [hov, setHov] = useState(false);

  const styles: Record<ButtonVariant, { bg: string; text: string; border: string }> = {
    ghost: {
      bg:     hov && !disabled ? 'bg-[#2d3338]'    : 'bg-transparent',
      text:   disabled ? 'text-gray-600' : hov      ? 'text-white' : 'text-gray-400',
      border: 'border border-transparent',
    },
    solid: {
      bg:     hov && !disabled ? 'bg-[#3d4449]'    : 'bg-[#2d3338]',
      text:   disabled ? 'text-gray-600'            : 'text-white',
      border: 'border border-white/10',
    },
    accent: {
      bg:     hov && !disabled ? 'bg-[#5a9fe8]'    : 'bg-[#4a90e2]',
      text:   'text-white',
      border: 'border border-transparent',
    },
    danger: {
      bg:     hov && !disabled ? 'bg-red-600'       : 'bg-red-500',
      text:   'text-white',
      border: 'border border-transparent',
    },
    success: {
      bg:     hov && !disabled ? 'bg-green-600'     : 'bg-green-500',
      text:   'text-[#0a1f17]',
      border: 'border border-transparent',
    },
  };

  const s = styles[variant];

  return (
    <button
      title={title}
      disabled={disabled}
      onClick={disabled ? undefined : onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      className={`inline-flex items-center gap-1.5 rounded-md font-medium transition-colors whitespace-nowrap flex-shrink-0
        ${BTN_H[size]} ${BTN_FS[size]} ${BTN_PX[size]}
        ${s.bg} ${s.text} ${s.border}
        ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}
        ${className}`}
    >
      {Icon && <Icon size={ICON_PX[size]} className="flex-shrink-0" />}
      {children}
    </button>
  );
}