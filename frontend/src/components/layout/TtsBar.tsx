// components/layout/TtsBar.tsx
import { X, Volume2, Loader2, Pause, Play, Square } from 'lucide-react';
import { useTheme } from '../../theme';

interface TtsBarProps {
  visible: boolean; status?: string; phase?: 'loading' | 'playing';
  progress?: { pct: number }; isPaused?: boolean; speed?: number;
  onStop: () => void; onPauseResume: () => void; onSpeedChange: (s: number) => void;
}

export function TtsBar({ visible, status, phase, progress, isPaused, speed = 1, onStop, onPauseResume, onSpeedChange }: TtsBarProps) {
  const { theme: t } = useTheme();
  if (!visible) return null;

  const sep = <div style={{ width: '1px', height: '20px', backgroundColor: t.colors.borderMid, flexShrink: 0 }} />;

  return (
    <div style={{
      height: '40px', backgroundColor: t.colors.bgBase, borderTop: `1px solid ${t.colors.border}`,
      display: 'flex', alignItems: 'center', gap: 0, flexShrink: 0,
      boxShadow: t.shadow.panel, fontFamily: t.fonts.ui,
    }}>
      <button onClick={onStop} title="Stop" style={{
        width: 40, height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: t.colors.textMuted, background: 'none', border: 'none', cursor: 'pointer', flexShrink: 0,
      }}
        onMouseEnter={e => (e.currentTarget.style.color = t.colors.textPrimary)}
        onMouseLeave={e => (e.currentTarget.style.color = t.colors.textMuted)}>
        <X size={14} />
      </button>
      {sep}
      <span style={{ fontSize: '12px', fontWeight: 600, color: t.colors.accent, padding: '0 12px', fontFamily: t.fonts.mono, whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: '6px' }}>
        {phase === 'loading' ? <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> : isPaused ? <Pause size={12} /> : <Volume2 size={12} />}
        {status}
      </span>
      {sep}
      {phase === 'loading' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '0 12px', flex: 1 }}>
          <div style={{ flex: 1, maxWidth: 160, height: 4, backgroundColor: t.colors.bgRaised, borderRadius: t.radius.pill, overflow: 'hidden' }}>
            <div style={{ height: '100%', backgroundColor: t.colors.accent, width: `${progress?.pct ?? 0}%`, transition: 'width 0.2s' }} />
          </div>
          <span style={{ fontSize: '10px', color: t.colors.textMuted, fontFamily: t.fonts.mono }}>{progress?.pct ?? 0}%</span>
        </div>
      )}
      {phase === 'playing' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '0 12px' }}>
          <button onClick={onPauseResume} style={{
            height: 24, padding: '0 12px', borderRadius: t.radius.sm, fontSize: '12px', fontWeight: 500,
            display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', border: '1px solid',
            backgroundColor: isPaused ? 'rgba(34,197,94,0.1)' : `${t.colors.accent}1a`,
            borderColor: isPaused ? 'rgba(34,197,94,0.3)' : `${t.colors.accent}4d`,
            color: isPaused ? '#4ade80' : t.colors.accent,
          }}>
            {isPaused ? <><Play size={11} /> Resume</> : <><Pause size={11} /> Pause</>}
          </button>
          <button onClick={onStop} style={{
            height: 24, padding: '0 12px', borderRadius: t.radius.sm, fontSize: '12px', fontWeight: 500,
            display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', border: '1px solid',
            backgroundColor: 'rgba(239,68,68,0.1)', borderColor: 'rgba(239,68,68,0.3)', color: '#f87171',
          }}>
            <Square size={10} /> Stop
          </button>
          <div style={{ width: '1px', height: 16, backgroundColor: t.colors.border, margin: '0 4px', flexShrink: 0 }} />
          <span style={{ fontSize: '11px', color: t.colors.textMuted }}>Speed</span>
          <input type="range" min={0.25} max={4} step={0.25} value={speed}
            onChange={e => onSpeedChange(parseFloat(e.target.value))}
            style={{ width: 80, accentColor: t.colors.accent, cursor: 'pointer' }} />
          <span style={{ fontSize: '12px', fontWeight: 600, color: t.colors.textPrimary, fontFamily: t.fonts.mono, minWidth: 28 }}>{speed}×</span>
        </div>
      )}
    </div>
  );
}