// components/canvas/PageControls.tsx — Hover controls above each page.
// Move up/down, rotate CW/CCW, delete. All Lucide icons — no emoji.

import {
  ArrowUp, ArrowDown, RotateCw, RotateCcw, X,
} from 'lucide-react';

interface PageControlsProps {
  pageIndex: number;
  totalPages: number;
  onRotateCW: () => void;
  onRotateCCW: () => void;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
}

interface CtrlBtnProps {
  icon: React.ReactNode;
  title: string;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
}

const CtrlBtn = ({ icon, title, onClick, disabled, danger }: CtrlBtnProps) => (
  <button
    title={title}
    disabled={disabled}
    onClick={onClick}
    className={`w-7 h-7 rounded flex items-center justify-center transition-colors
      ${danger
        ? 'text-red-400 hover:bg-red-500/20 disabled:opacity-30'
        : 'text-gray-400 hover:bg-[#3d4449] hover:text-white disabled:opacity-30'
      }
      disabled:cursor-not-allowed`}
  >
    {icon}
  </button>
);

const Sep = () => <div className="w-px h-4 bg-white/10 mx-0.5" />;

export function PageControls({
  pageIndex, totalPages,
  onRotateCW, onRotateCCW,
  onDelete, onMoveUp, onMoveDown,
}: PageControlsProps) {
  return (
    <div className="absolute -top-9 left-1/2 -translate-x-1/2 z-30 flex items-center gap-1 bg-[#2d3338] border border-white/[0.07] rounded-lg px-2 py-1.5 shadow-xl animate-ctrl-in">
      <CtrlBtn
        icon={<ArrowUp size={13} />}
        title="Move up"
        disabled={pageIndex === 0}
        onClick={onMoveUp}
      />
      <CtrlBtn
        icon={<ArrowDown size={13} />}
        title="Move down"
        disabled={pageIndex >= totalPages - 1}
        onClick={onMoveDown}
      />
      <Sep />
      <CtrlBtn
        icon={<RotateCw size={13} />}
        title="Rotate clockwise"
        onClick={onRotateCW}
      />
      <CtrlBtn
        icon={<RotateCcw size={13} />}
        title="Rotate counter-clockwise"
        onClick={onRotateCCW}
      />
      <Sep />
      <CtrlBtn
        icon={<X size={13} />}
        title="Delete page"
        danger
        disabled={totalPages <= 1}
        onClick={onDelete}
      />
    </div>
  );
}