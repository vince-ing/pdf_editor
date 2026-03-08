// frontend/src/components/TtsBar.jsx
import React from 'react';

/**
 * TtsBar — slim playback control bar that slides in at the bottom of the viewport.
 *
 * States:
 *   hidden   → bar is not rendered
 *   loading  → audio is being generated; shows progress bar + percentage
 *   playing  → audio is playing; shows Pause / Stop / Speed
 */
export const TtsBar = ({
    visible,
    status,
    phase,         // 'loading' | 'playing'
    progress,      // { done, total, pct }
    isPaused,
    speed,
    onStop,
    onPauseResume,
    onSpeedChange,
}) => {
    if (!visible) return null;

    const barStyle = {
        display: 'flex',
        alignItems: 'center',
        gap: '0',
        height: '38px',
        backgroundColor: '#141e2e',
        borderTop: '1px solid #0d1520',
        flexShrink: 0,
        overflow: 'hidden',
        boxShadow: '0 -2px 8px rgba(0,0,0,0.35)',
        fontFamily: 'system-ui, sans-serif',
        fontSize: '13px',
    };

    const sep = (
        <div style={{ width: '1px', height: '20px', backgroundColor: 'rgba(255,255,255,0.1)', margin: '0 4px', flexShrink: 0 }} />
    );

    const btnStyle = (bg = '#2a3a50', fg = 'white') => ({
        padding: '5px 12px',
        border: 'none',
        borderRadius: '4px',
        backgroundColor: bg,
        color: fg,
        cursor: 'pointer',
        fontWeight: '600',
        fontSize: '12px',
        whiteSpace: 'nowrap',
        flexShrink: 0,
    });

    return (
        <div style={barStyle}>
            {/* Close / dismiss */}
            <button
                onClick={onStop}
                style={{ ...btnStyle('#141e2e', '#546e7a'), padding: '5px 10px', fontSize: '14px' }}
                title="Stop and close"
            >✕</button>

            {sep}

            {/* Status label */}
            <span style={{
                color: '#5dade2',
                fontFamily: 'monospace',
                fontSize: '12px',
                fontWeight: '600',
                padding: '0 10px',
                whiteSpace: 'nowrap',
                flexShrink: 0,
            }}>
                🔊 {status}
            </span>

            {sep}

            {/* Loading phase */}
            {phase === 'loading' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '0 8px', flex: 1 }}>
                    <div style={{
                        flex: 1, maxWidth: '180px', height: '6px',
                        backgroundColor: '#2a3a50', borderRadius: '3px', overflow: 'hidden',
                    }}>
                        <div style={{
                            width: `${progress?.pct ?? 0}%`,
                            height: '100%',
                            backgroundColor: '#2980b9',
                            borderRadius: '3px',
                            transition: 'width 0.2s ease',
                        }} />
                    </div>
                    <span style={{ color: '#7f8c8d', fontSize: '11px', whiteSpace: 'nowrap' }}>
                        {progress?.pct ?? 0}%
                        {progress?.total > 0 && ` (${progress.done}/${progress.total})`}
                    </span>
                </div>
            )}

            {/* Playback phase */}
            {phase === 'playing' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '0 4px' }}>
                    <button
                        onClick={onPauseResume}
                        style={btnStyle(isPaused ? '#27ae60' : '#2980b9')}
                        title={isPaused ? 'Resume' : 'Pause'}
                    >
                        {isPaused ? '▶ Resume' : '⏸ Pause'}
                    </button>

                    <button
                        onClick={onStop}
                        style={btnStyle('#7b2020', '#ffcccc')}
                        title="Stop"
                    >◼ Stop</button>

                    {sep}

                    <span style={{ color: '#7f8c8d', fontSize: '12px', whiteSpace: 'nowrap' }}>Speed:</span>

                    <input
                        type="range"
                        min={0.25} max={4.0} step={0.25}
                        value={speed}
                        onChange={e => onSpeedChange(parseFloat(e.target.value))}
                        style={{ width: '110px', cursor: 'pointer', accentColor: '#2980b9' }}
                        title={`Speed: ${speed}×`}
                    />

                    <span style={{
                        color: 'white', fontSize: '12px', fontWeight: '700',
                        minWidth: '36px', textAlign: 'left',
                    }}>
                        {speed}×
                    </span>
                </div>
            )}
        </div>
    );
};