// components/TabBar.jsx
// Document tab strip supporting multiple open files.
// Currently scaffolded — single-tab mode. Extend tabs state as backend supports it.

import React, { useState } from 'react';
import theme from '../theme';
import { IconButton } from './Primitives';
const t = theme;

const Tab = ({ tab, isActive, onClick, onClose }) => {
    const [hov, setHov] = useState(false);

    return (
        <div
            onClick={onClick}
            onMouseEnter={() => setHov(true)}
            onMouseLeave={() => setHov(false)}
            title={tab.fullName}
            style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                height: '100%',
                padding: '0 10px 0 12px',
                maxWidth: '200px',
                minWidth: '100px',
                backgroundColor: isActive ? t.colors.bgSurface : hov ? t.colors.bgRaised : 'transparent',
                borderRight: `1px solid ${t.colors.border}`,
                borderBottom: isActive ? `1px solid ${t.colors.bgSurface}` : '1px solid transparent',
                borderTop: isActive ? `1px solid ${t.colors.accent}` : '1px solid transparent',
                cursor: 'pointer',
                position: 'relative',
                flexShrink: 0,
                transition: t.t.fast,
                userSelect: 'none',
            }}
        >
            <span style={{ fontSize: '11px', flexShrink: 0, opacity: 0.6 }}>📄</span>
            <span style={{
                fontSize: '12px',
                fontWeight: isActive ? '500' : '400',
                color: isActive ? t.colors.textPrimary : t.colors.textSecondary,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                flex: 1,
                fontFamily: t.fonts.ui,
            }}>
                {tab.modified && <span style={{ color: t.colors.warning, marginRight: '3px' }}>●</span>}
                {tab.name}
            </span>
            {(hov || isActive) && (
                <button
                    onClick={(e) => { e.stopPropagation(); onClose?.(tab.id); }}
                    title="Close tab"
                    style={{
                        width: '16px', height: '16px', flexShrink: 0,
                        borderRadius: '3px', border: 'none',
                        backgroundColor: hov ? t.colors.bgActive : 'transparent',
                        color: t.colors.textSecondary,
                        cursor: 'pointer', fontSize: '10px',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}
                >✕</button>
            )}
        </div>
    );
};

export const TabBar = ({ tabs, activeTabId, onTabClick, onTabClose, onNewTab }) => {
    return (
        <div
            className="no-select"
            style={{
                height: t.layout.tabBarH,
                backgroundColor: t.colors.bgBase,
                borderBottom: `1px solid ${t.colors.border}`,
                display: 'flex',
                alignItems: 'flex-end',
                flexShrink: 0,
                overflow: 'hidden',
            }}
        >
            {/* Tab list */}
            <div style={{
                display: 'flex',
                alignItems: 'flex-end',
                flex: 1,
                height: '100%',
                overflow: 'hidden',
            }}>
                {tabs.map(tab => (
                    <Tab
                        key={tab.id}
                        tab={tab}
                        isActive={tab.id === activeTabId}
                        onClick={() => onTabClick?.(tab.id)}
                        onClose={onTabClose}
                    />
                ))}

                {/* New tab button */}
                <button
                    onClick={onNewTab}
                    title="Open new file (Ctrl+O)"
                    style={{
                        width: '28px', height: '28px', flexShrink: 0,
                        border: 'none', background: 'transparent',
                        color: t.colors.textMuted, cursor: 'pointer',
                        fontSize: '16px', display: 'flex',
                        alignItems: 'center', justifyContent: 'center',
                        borderRadius: t.radius.sm,
                        transition: t.t.fast,
                        alignSelf: 'center', marginLeft: '2px',
                    }}
                >+</button>
            </div>
        </div>
    );
};