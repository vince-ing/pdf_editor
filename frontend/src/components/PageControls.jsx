import React from 'react';

const CtrlBtn = ({ children, onClick, title, color, disabled }) => (
    <button title={title} onClick={onClick} disabled={disabled} style={{
        width: '26px', height: '26px', borderRadius: '5px', border: 'none',
        backgroundColor: disabled ? 'rgba(255,255,255,0.06)' : color,
        color: disabled ? '#3d5166' : 'white', fontSize: '14px', fontWeight: '700',
        cursor: disabled ? 'not-allowed' : 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1, padding: 0,
    }}>{children}</button>
);

const Divider = () => (
    <div style={{ width: '1px', height: '16px', backgroundColor: 'rgba(255,255,255,0.12)' }} />
);

export const PageControls = ({ pageIndex, totalPages, onRotateCW, onRotateCCW, onDelete, onMoveUp, onMoveDown }) => (
    <div style={{
        position: 'absolute', top: '10px', left: '50%', transform: 'translateX(-50%)',
        display: 'flex', gap: '6px', alignItems: 'center',
        backgroundColor: 'rgba(15,23,35,0.88)', backdropFilter: 'blur(6px)',
        borderRadius: '8px', padding: '5px 10px', zIndex: 30,
        boxShadow: '0 2px 12px rgba(0,0,0,0.5)', border: '1px solid rgba(255,255,255,0.1)',
        pointerEvents: 'auto', whiteSpace: 'nowrap',
    }}>
        <CtrlBtn onClick={onMoveUp}    disabled={pageIndex === 0}             title="Move up"    color="#546e7a">↑</CtrlBtn>
        <CtrlBtn onClick={onMoveDown}  disabled={pageIndex >= totalPages - 1} title="Move down"  color="#546e7a">↓</CtrlBtn>
        <Divider />
        <CtrlBtn onClick={onRotateCW}  title="Rotate CW"  color="#2980b9">↻</CtrlBtn>
        <CtrlBtn onClick={onRotateCCW} title="Rotate CCW" color="#2980b9">↺</CtrlBtn>
        <Divider />
        <CtrlBtn onClick={onDelete} disabled={totalPages <= 1} title="Delete page" color="#c0392b">✕</CtrlBtn>
    </div>
);