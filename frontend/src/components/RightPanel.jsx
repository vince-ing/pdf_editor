// components/RightPanel.jsx
// Properties panel — context-sensitive, shows document/page/annotation info.
// Add new property sections by adding PanelSection blocks.
// Scaffolded sections will show "coming soon" until backend provides data.

import React from 'react';
import theme from '../theme';
import { PanelSection, PropRow } from './Primitives';
const t = theme;

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────
const bytes = (n) => {
    if (!n) return '—';
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / 1024 / 1024).toFixed(2)} MB`;
};

const ColorSwatch = ({ color, label }) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <div style={{ width: '12px', height: '12px', borderRadius: t.radius.xs, background: color, border: `1px solid ${t.colors.borderMid}`, flexShrink: 0 }} />
        <span style={{ fontSize: '11px', fontFamily: t.fonts.mono, color: t.colors.textPrimary }}>{label ?? color}</span>
    </div>
);

const ComingSoon = ({ icon = '🔧', label = 'Available in a future update' }) => (
    <div style={{ fontSize: '11px', color: t.colors.textMuted, padding: '6px 0', display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span style={{ fontSize: '13px' }}>{icon}</span>
        {label}
    </div>
);

const MiniBtn = ({ children, onClick, disabled }) => {
    const [hov, setHov] = React.useState(false);
    return (
        <button onClick={disabled ? undefined : onClick}
            onMouseEnter={() => setHov(true)}
            onMouseLeave={() => setHov(false)}
            style={{
                flex: 1, height: '24px', border: `1px solid ${t.colors.border}`,
                borderRadius: t.radius.sm,
                background: hov && !disabled ? t.colors.bgHover : t.colors.bgRaised,
                color: disabled ? t.colors.textDisabled : t.colors.textPrimary,
                fontSize: '11px', cursor: disabled ? 'not-allowed' : 'pointer',
                fontFamily: t.fonts.ui, transition: t.t.fast,
            }}>
            {children}
        </button>
    );
};

// ─────────────────────────────────────────────────────────────────────────────
// Panel sections
// ─────────────────────────────────────────────────────────────────────────────
const DocumentSection = ({ doc }) => {
    if (!doc) return (
        <PanelSection title="Document">
            <div style={{ fontSize: '11px', color: t.colors.textMuted, padding: '4px 0' }}>No document open</div>
        </PanelSection>
    );

    return (
        <PanelSection title="Document">
            <PropRow label="File">{doc.file_name}</PropRow>
            <PropRow label="Pages">{doc.children?.length ?? '—'}</PropRow>
            <PropRow label="Version">PDF 1.7</PropRow>
            <PropRow label="Size">{bytes(doc.file_size)}</PropRow>
        </PanelSection>
    );
};

const PageSection = ({ page, pageIndex }) => {
    if (!page) return null;
    const w = page.metadata?.width  ?? '—';
    const h = page.metadata?.height ?? '—';

    return (
        <PanelSection title="Page" collapsible>
            <PropRow label="Number">{pageIndex + 1}</PropRow>
            <PropRow label="Size">{w !== '—' ? `${Math.round(w)} × ${Math.round(h)} pt` : '—'}</PropRow>
            <PropRow label="Rotation">{page.rotation ?? 0}°</PropRow>
            <PropRow label="Crop">{page.crop_box ? 'Applied' : 'None'}</PropRow>
            <div style={{ display: 'flex', gap: '4px', marginTop: '6px' }}>
                <MiniBtn>↻ Rotate</MiniBtn>
                <MiniBtn>⬚ Crop</MiniBtn>
            </div>
        </PanelSection>
    );
};

const AnnotationSection = ({ annotations }) => (
    <PanelSection title="Annotations" collapsible>
        {(!annotations || annotations.length === 0) ? (
            <div style={{ fontSize: '11px', color: t.colors.textMuted, padding: '4px 0' }}>None on this page</div>
        ) : (
            <PropRow label="Count">{annotations.length}</PropRow>
        )}
    </PanelSection>
);

const AppearanceSection = () => (
    <PanelSection title="Appearance" collapsible>
        <div style={{ marginBottom: '8px' }}>
            <div style={{ fontSize: '11px', color: t.colors.textSecondary, marginBottom: '5px' }}>Highlight Color</div>
            <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                {['#e0aa3e', '#4f7ef7', '#3ecba0', '#d45c5c', '#b06cf3'].map(c => (
                    <div key={c} title={c} style={{ width: '18px', height: '18px', borderRadius: t.radius.xs, background: c, cursor: 'pointer', border: `1px solid transparent`, transition: t.t.fast }} />
                ))}
            </div>
        </div>
        <div>
            <div style={{ fontSize: '11px', color: t.colors.textSecondary, marginBottom: '5px' }}>Opacity</div>
            <input type="range" min={0.1} max={1} step={0.05} defaultValue={0.45}
                style={{ width: '100%', accentColor: t.colors.accent, cursor: 'pointer' }} />
        </div>
    </PanelSection>
);

const SecuritySection = () => (
    <PanelSection title="Security" collapsible>
        <PropRow label="Encrypted">No</PropRow>
        <PropRow label="Permissions">All allowed</PropRow>
        <div style={{ marginTop: '6px' }}>
            <MiniBtn disabled>🔒 Protect…</MiniBtn>
        </div>
    </PanelSection>
);

const MetadataSection = () => (
    <PanelSection title="Metadata" collapsible>
        <PropRow label="Title"><ComingSoon icon="" label="—" /></PropRow>
        <PropRow label="Author">—</PropRow>
        <PropRow label="Created">—</PropRow>
        <PropRow label="Modified">—</PropRow>
        <div style={{ marginTop: '6px' }}>
            <MiniBtn disabled>✏ Edit Metadata…</MiniBtn>
        </div>
    </PanelSection>
);

const LinksSection = () => (
    <PanelSection title="Links & Bookmarks" collapsible>
        <ComingSoon icon="🔗" label="Link insertion coming soon" />
        <ComingSoon icon="🔖" label="Bookmark manager coming soon" />
    </PanelSection>
);

// ─────────────────────────────────────────────────────────────────────────────
// RightPanel
// ─────────────────────────────────────────────────────────────────────────────
export const RightPanel = ({ documentState, activePage }) => {
    const page = documentState?.children?.[activePage] ?? null;

    return (
        <div style={{
            width: t.layout.rightPanelW,
            backgroundColor: t.colors.bgSurface,
            borderLeft: `1px solid ${t.colors.border}`,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            flexShrink: 0,
        }}>
            {/* Header */}
            <div style={{
                height: '34px',
                padding: '0 12px',
                display: 'flex', alignItems: 'center',
                borderBottom: `1px solid ${t.colors.border}`,
                flexShrink: 0,
            }}>
                <span style={{ fontSize: '11px', fontWeight: '600', color: t.colors.textSecondary, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                    Properties
                </span>
            </div>

            {/* Sections */}
            <div style={{ flex: 1, overflowY: 'auto' }}>
                <DocumentSection   doc={documentState} />
                <PageSection       page={page} pageIndex={activePage} />
                <AnnotationSection annotations={page?.children} />
                <AppearanceSection />
                <LinksSection />
                <SecuritySection />
                <MetadataSection />
            </div>
        </div>
    );
};