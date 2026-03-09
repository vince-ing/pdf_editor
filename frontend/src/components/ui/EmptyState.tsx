// components/canvas/EmptyState.tsx — Shown when no document is loaded.
// Lucide icon instead of emoji. Clean, professional.

import { FileText } from 'lucide-react';

interface EmptyStateProps {
  onOpen?: () => void;
}

const FEATURE_TAGS = [
  'Highlight · Redact',
  'Add Text · Images',
  'Reorder · Rotate',
  'Read Aloud · Export',
];

export function EmptyState({ onOpen }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-5 select-none">
      {/* Icon */}
      <div className="w-16 h-16 bg-[#2d3338] rounded-xl flex items-center justify-center border border-white/[0.05] shadow-2xl">
        <FileText size={28} className="text-gray-500" />
      </div>

      {/* Heading */}
      <div className="text-center">
        <div className="text-base font-semibold text-white mb-1">Open a document to begin</div>
        <div className="text-sm text-gray-500">File → Open, or press Ctrl+O</div>
      </div>

      {/* Optional open button */}
      {onOpen && (
        <button
          onClick={onOpen}
          className="h-8 px-5 bg-[#4a90e2] text-white text-xs font-medium rounded-md hover:bg-[#5a9fe8] transition-colors shadow-lg"
        >
          Open PDF…
        </button>
      )}

      {/* Feature tags */}
      <div className="flex flex-wrap gap-1.5 justify-center max-w-xs">
        {FEATURE_TAGS.map(f => (
          <span
            key={f}
            className="text-[11px] text-gray-500 bg-[#2d3338] border border-white/[0.05] rounded-full px-3 py-1"
          >
            {f}
          </span>
        ))}
      </div>
    </div>
  );
}