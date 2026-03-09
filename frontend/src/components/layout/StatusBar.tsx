// components/layout/StatusBar.tsx
import { useTheme } from '../../theme';
import type { ToolId } from '../../constants/tools';

interface StatusBarProps {
  activeTool: ToolId; scale: number; activePage: number; pageCount: number;
  lastSelectedText?: string; documentState?: { file_name?: string } | null;
}

const Chip = ({ children, accent, t }: { children: React.ReactNode; accent?: boolean; t: any }) => (
  <span style={{ fontSize: '11px', fontFamily: t.fonts.mono, padding: '0 10px', color: accent ? t.colors.accent : t.colors.textSecondary }}>
    {children}
  </span>
);

const Sep = ({ t }: { t: any }) => (
  <span style={{ color: t.colors.bgRaised, fontSize: '10px', userSelect: 'none' }}>│</span>
);

export function StatusBar({ activeTool, scale, activePage, pageCount, lastSelectedText, documentState }: StatusBarProps) {
  const { theme: t } = useTheme();
  return (
    <div style={{
      height: '24px', backgroundColor: t.colors.bgBase, borderTop: `1px solid ${t.colors.border}`,
      display: 'flex', alignItems: 'center', padding: '0 12px', flexShrink: 0, overflow: 'hidden',
    }}>
      <Chip accent t={t}>{activeTool}</Chip>
      {documentState && (<>
        <Sep t={t} />
        <Chip t={t}>{Math.round(scale * 100)}%</Chip>
        <Sep t={t} />
        <Chip t={t}>p. <span style={{ color: t.colors.textPrimary, fontWeight: 600 }}>{activePage + 1}</span> / {pageCount}</Chip>
        {documentState.file_name && (<><Sep t={t} /><Chip t={t}>{documentState.file_name}</Chip></>)}
      </>)}
      {lastSelectedText && (
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
          <span style={{ fontSize: '10px', color: t.colors.textMuted, textTransform: 'uppercase', letterSpacing: '0.05em', flexShrink: 0 }}>Selected</span>
          <span style={{ fontSize: '11px', color: t.colors.accent, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '280px' }}>
            {lastSelectedText.length > 60 ? lastSelectedText.slice(0, 60) + '…' : lastSelectedText}
          </span>
        </div>
      )}
    </div>
  );
}