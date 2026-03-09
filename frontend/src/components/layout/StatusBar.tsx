// components/layout/StatusBar.tsx — 24px bottom strip.
// Shows: active tool | zoom % | page N/total | selected text preview
// No emoji — tool displayed as text label, separators are styled divs.

import type { ToolId } from '../../constants/tools';

interface StatusBarProps {
  activeTool: ToolId;
  scale: number;
  activePage: number;
  pageCount: number;
  lastSelectedText?: string;
  documentState?: { file_name?: string } | null;
}

const Chip = ({ children, accent }: { children: React.ReactNode; accent?: boolean }) => (
  <span className={`text-[11px] font-mono px-2.5 ${accent ? 'text-[#4a90e2]' : 'text-gray-400'}`}>
    {children}
  </span>
);

const Sep = () => <span className="text-[#2d3338] text-[10px] select-none">│</span>;

export function StatusBar({
  activeTool, scale, activePage, pageCount, lastSelectedText, documentState,
}: StatusBarProps) {
  return (
    <div className="h-6 bg-[#1e2327] border-t border-white/[0.04] flex items-center px-3 flex-shrink-0 overflow-hidden">
      <Chip accent>{activeTool}</Chip>

      {documentState && (
        <>
          <Sep />
          <Chip>{Math.round(scale * 100)}%</Chip>
          <Sep />
          <Chip>
            p.{' '}
            <span className="text-white font-semibold">{activePage + 1}</span>
            {' '}/ {pageCount}
          </Chip>
          {documentState.file_name && (
            <>
              <Sep />
              <Chip>{documentState.file_name}</Chip>
            </>
          )}
        </>
      )}

      {lastSelectedText && (
        <div className="ml-auto flex items-center gap-2 overflow-hidden">
          <span className="text-[10px] text-gray-600 uppercase tracking-wider flex-shrink-0">Selected</span>
          <span className="text-[11px] text-[#4a90e2] truncate max-w-[280px]">
            {lastSelectedText.length > 60
              ? lastSelectedText.slice(0, 60) + '…'
              : lastSelectedText}
          </span>
        </div>
      )}
    </div>
  );
}