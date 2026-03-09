// components/TtsBar.jsx
import React from 'react';
import theme from '../theme';
const t = theme;

const barBtn = (color, bg) => ({
    height: '24px', padding: '0 10px',
    border: `1px solid ${color}44`, borderRadius: t.radius.sm,
    background: bg ?? 'transparent', color,
    cursor: 'pointer', fontWeight: '500', fontSize: '11px',
    fontFamily: t.fonts.ui, whiteSpace: 'nowrap', flexShrink: 0,
    transition: t.t.fast,
});

export const TtsBar = ({ visible, status, phase, progress, isPaused, speed, onStop, onPauseResume, onSpeedChange }) => {
    if (!visible) return null;
    return (
        <div style={{
            height: '38px',
            backgroundColor: t.colors.bgBase,
            borderTop: `1px solid ${t.colors.border}`,
            display: 'flex', alignItems: 'center', gap: '0',
            flexShrink: 0, zIndex: 200,
            animation: 'slideUp 0.15s ease',
            fontFamily: t.fonts.ui,
            boxShadow: '0 -2px 12px rgba(0,0,0,0.35)',
        }}>
            <button onClick={onStop} style={{ ...barBtn(t.colors.textMuted, 'transparent'), borderColor: 'transparent', width: '36px', justifyContent: 'center', display: 'flex', alignItems: 'center' }}>✕</button>
            <span style={{ width: '1px', height: '18px', background: t.colors.border, flexShrink: 0 }} />
            <span style={{ fontSize: '11px', fontWeight: '600', color: t.colors.accent, padding: '0 12px', fontFamily: t.fonts.mono, whiteSpace: 'nowrap' }}>
                {phase === 'loading' ? '⏳' : isPaused ? '⏸' : '🔊'} {status}
            </span>
            <span style={{ width: '1px', height: '18px', background: t.colors.border, flexShrink: 0 }} />

            {phase === 'loading' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '0 12px', flex: 1 }}>
                    <div style={{ flex: 1, maxWidth: '180px', height: '3px', background: t.colors.bgRaised, borderRadius: '99px', overflow: 'hidden' }}>
                        <div style={{ width: `${progress?.pct ?? 0}%`, height: '100%', background: t.colors.accent, transition: 'width 0.25s ease', borderRadius: '99px' }} />
                    </div>
                    <span style={{ fontSize: '10px', color: t.colors.textMuted, fontFamily: t.fonts.mono }}>{progress?.pct ?? 0}%</span>
                </div>
            )}

            {phase === 'playing' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '0 10px' }}>
                    <button onClick={onPauseResume} style={barBtn(isPaused ? t.colors.success : t.colors.accent, isPaused ? t.colors.successBg : t.colors.accentSubtle)}>
                        {isPaused ? '▶ Resume' : '⏸ Pause'}
                    </button>
                    <button onClick={onStop} style={barBtn(t.colors.danger, t.colors.dangerBg)}>◼ Stop</button>
                    <span style={{ width: '1px', height: '18px', background: t.colors.border, flexShrink: 0, margin: '0 4px' }} />
                    <span style={{ fontSize: '10px', color: t.colors.textMuted }}>Speed</span>
                    <input type="range" min={0.25} max={4} step={0.25} value={speed} onChange={e => onSpeedChange(parseFloat(e.target.value))} style={{ width: '90px', accentColor: t.colors.accent, cursor: 'pointer' }} />
                    <span style={{ fontSize: '11px', fontWeight: '600', color: t.colors.textPrimary, fontFamily: t.fonts.mono, minWidth: '30px' }}>{speed}×</span>
                </div>
            )}
        </div>
    );
};