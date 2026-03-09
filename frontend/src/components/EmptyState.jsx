// components/EmptyState.jsx
import React from 'react';
import theme from '../theme';
const t = theme;

export const EmptyState = ({ onOpen }) => (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: '20px', userSelect: 'none' }}>
        <div style={{ width: '64px', height: '64px', borderRadius: '16px', background: t.colors.bgRaised, border: `1px solid ${t.colors.border}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '28px', boxShadow: t.shadow.md }}>
            📄
        </div>
        <div style={{ textAlign: 'center', lineHeight: 1.7 }}>
            <div style={{ fontSize: '16px', fontWeight: '600', color: t.colors.textPrimary, marginBottom: '4px', fontFamily: t.fonts.ui }}>Open a document to begin</div>
            <div style={{ fontSize: '12px', color: t.colors.textMuted }}>File → Open,  or drag a PDF here</div>
        </div>
        <button onClick={onOpen} style={{
            height: '32px', padding: '0 18px',
            background: t.colors.accent, color: '#fff',
            border: 'none', borderRadius: t.radius.sm,
            fontFamily: t.fonts.ui, fontSize: '12px', fontWeight: '500',
            cursor: 'pointer', boxShadow: `0 2px 12px ${t.colors.accentGlow}`,
        }}>Open PDF…</button>
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', justifyContent: 'center', maxWidth: '340px' }}>
            {['Highlight · Redact · Annotate', 'Crop · Reorder · Rotate', 'Read Aloud · OCR', 'Export · Compress'].map(f => (
                <span key={f} style={{ fontSize: '10.5px', color: t.colors.textMuted, background: t.colors.bgRaised, border: `1px solid ${t.colors.border}`, borderRadius: t.radius.pill, padding: '2px 9px', fontFamily: t.fonts.ui }}>
                    {f}
                </span>
            ))}
        </div>
    </div>
);