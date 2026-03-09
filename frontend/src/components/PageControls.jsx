// components/PageControls.jsx
import React from 'react';
import theme from '../theme';
const t = theme;

const Btn = ({ children, onClick, title, danger, disabled }) => {
    const [h, setH] = React.useState(false);
    return (
        <button title={title} onClick={onClick} disabled={disabled}
            onMouseEnter={() => setH(true)} onMouseLeave={() => setH(false)}
            style={{
                width: 26, height: 26, borderRadius: t.radius.sm,
                border: `1px solid ${disabled ? 'transparent' : t.colors.borderMid}`,
                background: disabled ? 'transparent' : h ? (danger ? t.colors.dangerBg : t.colors.bgHover) : t.colors.bgRaised,
                color: disabled ? t.colors.textDisabled : danger ? t.colors.danger : h ? t.colors.textPrimary : t.colors.textSecondary,
                fontSize: 13, cursor: disabled ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: t.t.fast, flexShrink: 0,
            }}>
            {children}
        </button>
    );
};

const Sep = () => <div style={{ width: 1, height: 14, background: t.colors.border, margin: '0 2px' }} />;

export const PageControls = ({ pageIndex, totalPages, onRotateCW, onRotateCCW, onDelete, onMoveUp, onMoveDown }) => (
    <div style={{
        position: 'absolute', top: '-36px', left: '50%',
        transform: 'translateX(-50%)',
        display: 'flex', gap: '3px', alignItems: 'center',
        background: t.colors.bgSurface,
        border: `1px solid ${t.colors.borderMid}`,
        borderRadius: t.radius.md,
        padding: '4px 6px',
        boxShadow: t.shadow.md,
        zIndex: 30, whiteSpace: 'nowrap',
        animation: 'pageCtrlIn 0.12s ease',
    }}>
        <Btn onClick={onMoveUp}    title="Move up"    disabled={pageIndex === 0}>↑</Btn>
        <Btn onClick={onMoveDown}  title="Move down"  disabled={pageIndex >= totalPages - 1}>↓</Btn>
        <Sep />
        <Btn onClick={onRotateCW}  title="Rotate CW" >↻</Btn>
        <Btn onClick={onRotateCCW} title="Rotate CCW">↺</Btn>
        <Sep />
        <Btn onClick={onDelete} title="Delete page" danger disabled={totalPages <= 1}>✕</Btn>
    </div>
);