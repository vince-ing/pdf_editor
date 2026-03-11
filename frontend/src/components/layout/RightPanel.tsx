// components/layout/RightPanel.tsx
import { ChevronDown, ChevronUp, MoreVertical, Sparkles, RotateCw, Crop, ScanText, Loader2 } from 'lucide-react';
import { useState, useCallback, useEffect } from 'react'
import type { ToolId } from '../../constants/tools';
import { DEFAULT_TEXT_PROPS, FONT_OPTIONS, type TextProps } from '../../types/textProps';
import { useTheme } from '../../theme';

interface PageNode { id?: string; rotation?: number; metadata?: { width?: number; height?: number }; crop_box?: unknown; children?: unknown[]; }
interface DocumentState { file_name?: string; file_size?: number; children?: PageNode[]; }
interface RightPanelProps {
  documentState?: DocumentState | null; activePage?: number; activeTool?: ToolId;
  textProps: TextProps; onTextPropsChange: (p: TextProps) => void;
  highlightColor?: string; highlightOpacity?: number;
  onHighlightColorChange?: (color: string) => void; onHighlightOpacityChange?: (opacity: number) => void;
  sessionId?: string | null;
  onDocumentChanged?: () => void;
  onRunOcr?: () => void; isOcrProcessing?: boolean; ocrError?: string | null;
  openSection?: SectionId | null; onSectionChange?: (s: SectionId | null) => void;
}

type SectionId = 'text' | 'page' | 'appearance';

const bytes = (n?: number) => {
  if (!n) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
};

const AUTHOR_COLORS: Record<string, string> = { JD: '#f59e0b', MK: '#a855f7', AL: '#22c55e', SA: '#4a90e2' };
const getAuthorColor = (a: string) => AUTHOR_COLORS[a] ?? '#6b7280';

// ── Small extracted components (hooks cannot be called inside .map or IIFEs) ──

const HoverButton = ({ icon: Icon, label, t }: { icon: React.ComponentType<{ size?: number }>; label: string; t: any }) => {
  const [hov, setHov] = useState(false);
  return (
    <button onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{ flex: 1, height: 28, fontSize: '11px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, border: 'none', borderRadius: t.radius.md, cursor: 'pointer', transition: t.t.fast, backgroundColor: hov ? t.colors.bgHover : t.colors.bgBase, color: hov ? t.colors.textPrimary : t.colors.textMuted }}>
      <Icon size={12} /> {label}
    </button>
  );
};

const OcrButton = ({ onRunOcr, isOcrProcessing, ocrError, t }: {
  onRunOcr?: () => void; isOcrProcessing?: boolean; ocrError?: string | null; t: any;
}) => {
  const [hov, setHov] = useState(false);
  return (
    <div style={{ marginTop: 6 }}>
      <button
        onClick={onRunOcr}
        disabled={isOcrProcessing || !onRunOcr}
        onMouseEnter={() => setHov(true)}
        onMouseLeave={() => setHov(false)}
        title="Extract text from scanned page using OCR"
        style={{
          width: '100%', height: 28, fontSize: '11px',
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
          border: `1px solid ${isOcrProcessing ? t.colors.accent : t.colors.border}`,
          borderRadius: t.radius.md,
          cursor: isOcrProcessing || !onRunOcr ? 'not-allowed' : 'pointer',
          transition: t.t.fast, opacity: !onRunOcr ? 0.4 : 1,
          backgroundColor: isOcrProcessing ? `${t.colors.accent}18` : hov && onRunOcr ? t.colors.bgHover : t.colors.bgBase,
          color: isOcrProcessing ? t.colors.accent : hov && onRunOcr ? t.colors.textPrimary : t.colors.textSecondary,
          fontFamily: t.fonts.ui,
        }}>
        {isOcrProcessing ? <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> : <ScanText size={12} />}
        {isOcrProcessing ? 'Running OCR…' : 'Run OCR'}
      </button>
      {ocrError && (
        <p style={{ fontSize: '10px', color: t.colors.danger, marginTop: 4, lineHeight: 1.4, fontFamily: t.fonts.ui }}>
          {ocrError}
        </p>
      )}
    </div>
  );
};

const CommentRow = ({ c, t }: { c: { id: number; author: string; time: string; text: string }; t: any }) => {
  const [hov, setHov] = useState(false);
  return (
    <div onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{ padding: '10px 16px', borderBottom: `1px solid ${t.colors.bgBase}`, cursor: 'pointer', backgroundColor: hov ? t.colors.bgHover : 'transparent', transition: t.t.fast }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
        <div style={{ width: 24, height: 24, borderRadius: '50%', backgroundColor: getAuthorColor(c.author), display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <span style={{ color: '#fff', fontSize: '10px', fontWeight: 700 }}>{c.author}</span>
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: '10px', color: t.colors.textMuted, marginBottom: 2 }}>{c.time}</div>
          <div style={{ fontSize: '12px', color: t.colors.textPrimary, lineHeight: 1.4 }}>{c.text}</div>
        </div>
      </div>
    </div>
  );
};

const Section = ({ title, isOpen, onToggle, children, t }: {
  title: string; isOpen: boolean; onToggle: () => void; children: React.ReactNode; t: any;
}) => {
  const [hov, setHov] = useState(false);
  return (
    <div style={{ borderBottom: `1px solid ${t.colors.bgBase}` }}>
      <button onClick={onToggle}
        onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
        style={{ width: '100%', padding: '10px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: hov ? `${t.colors.bgRaised}60` : 'none', border: 'none', cursor: 'pointer', transition: t.t.fast }}>
        <h3 style={{ fontSize: '11px', fontWeight: 600, color: t.colors.textSecondary, textTransform: 'uppercase', letterSpacing: '0.07em', fontFamily: t.fonts.ui }}>{title}</h3>
        {isOpen ? <ChevronUp size={14} style={{ color: t.colors.textMuted, flexShrink: 0 }} /> : <ChevronDown size={14} style={{ color: t.colors.textMuted, flexShrink: 0 }} />}
      </button>
      {isOpen && <div>{children}</div>}
    </div>
  );
};

const StyledSelect = ({ value, onChange, options, label, t }: { value: string; onChange: (v: string) => void; options: string[]; label: string; t: any }) => (
  <div>
    <label style={{ fontSize: '11px', color: t.colors.textMuted, marginBottom: 6, display: 'block', fontFamily: t.fonts.ui }}>{label}</label>
    <div style={{ position: 'relative' }}>
      <select value={value} onChange={e => onChange(e.target.value)}
        style={{ width: '100%', backgroundColor: t.colors.bgBase, color: t.colors.textPrimary, padding: '6px 28px 6px 10px', borderRadius: t.radius.md, fontSize: '12px', appearance: 'none', cursor: 'pointer', outline: 'none', border: `1px solid ${t.colors.border}`, fontFamily: t.fonts.ui }}>
        {value === '' && <option value="" disabled hidden>Mixed</option>}
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
      <ChevronDown size={12} style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', color: t.colors.textMuted, pointerEvents: 'none' }} />
    </div>
  </div>
);

const PropRowInner = ({ label, value, t }: { label: string; value: string; t: any }) => (
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 6 }}>
    <span style={{ fontSize: '11px', color: t.colors.textMuted, flexShrink: 0, fontFamily: t.fonts.ui }}>{label}</span>
    <span style={{ fontSize: '11px', color: t.colors.textSecondary, fontFamily: t.fonts.mono, textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis' }}>{value}</span>
  </div>
);

const TEXT_COLOR_SWATCHES = ['#000000', '#ffffff', '#ef4444', '#f59e0b', '#22c55e', '#4a90e2', '#a855f7', '#ec4899'];

function TextPropertiesContent({ props, onChange, t }: { props: TextProps; onChange: (p: TextProps) => void; t: any }) {
  const set = useCallback(<K extends keyof TextProps>(key: K, val: TextProps[K]) => onChange({ ...props, [key]: val }), [props, onChange]);
  const [sizeInput, setSizeInput] = useState(props.fontSize === '' ? '' : String(props.fontSize));
  useEffect(() => { setSizeInput(props.fontSize === '' ? '' : String(props.fontSize)); }, [props.fontSize]);
  const commitSize = () => {
    const n = parseFloat(sizeInput);
    if (!isNaN(n) && n > 0) set('fontSize', Math.min(144, Math.max(4, n)));
    else setSizeInput(props.fontSize === '' ? '' : String(props.fontSize));
  };
  const adjustSize = (delta: number) => { 
    const base = typeof props.fontSize === 'number' ? props.fontSize : 12;
    const n = Math.min(144, Math.max(4, base + delta)); 
    set('fontSize', n); 
    setSizeInput(String(n)); 
  };
  const previewCss: React.CSSProperties = {
    fontFamily: props.fontFamily === 'Times New Roman' ? '"Times New Roman", Times, serif' : props.fontFamily === 'Courier' ? '"Courier New", Courier, monospace' : 'Helvetica, Arial, sans-serif',
    fontWeight: props.isBold === true ? 'bold' : 'normal', fontStyle: props.isItalic === true ? 'italic' : 'normal',
    fontSize: Math.min(typeof props.fontSize === 'number' ? props.fontSize : 12, 18), color: props.color || '#000000', lineHeight: 1.3,
  };

  const inputStyle = { backgroundColor: t.colors.bgBase, color: t.colors.textPrimary, border: `1px solid ${t.colors.border}`, borderRadius: t.radius.md, fontSize: '12px', fontFamily: t.fonts.mono, outline: 'none' };
  const btnStyle = (active: boolean) => ({ width: 32, height: 32, borderRadius: t.radius.md, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '13px', fontWeight: 700, cursor: 'pointer', border: 'none', flexShrink: 0, transition: t.t.fast, backgroundColor: active ? t.colors.accent : t.colors.bgBase, color: active ? '#fff' : t.colors.textSecondary });

  return (
    <div style={{ padding: '0 16px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}
      onMouseDown={e => { const target = e.target as HTMLElement; if (!(target.tagName === 'INPUT' && (target as HTMLInputElement).type === 'text')) e.preventDefault(); }}>
      <StyledSelect label="Font" value={props.fontFamily} onChange={v => set('fontFamily', v)} options={FONT_OPTIONS} t={t} />
      <div>
        <label style={{ fontSize: '11px', color: t.colors.textMuted, marginBottom: 6, display: 'block', fontFamily: t.fonts.ui }}>Style &amp; Size</label>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <button onClick={() => set('isBold', props.isBold !== true)} title="Bold" style={btnStyle(props.isBold === true)}>B</button>
          <button onClick={() => set('isItalic', props.isItalic !== true)} title="Italic" style={{ ...btnStyle(props.isItalic === true), fontStyle: 'italic', fontFamily: 'serif' }}>I</button>
          <div style={{ width: 1, height: 20, backgroundColor: t.colors.border, flexShrink: 0 }} />
          <input type="text" value={sizeInput} onChange={e => setSizeInput(e.target.value)} onBlur={commitSize} onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur(); }} placeholder={props.fontSize === '' ? '-' : ''}
            style={{ ...inputStyle, width: 56, padding: '6px 8px', textAlign: 'center' }} />
          {[{ delta: -1, path: "M2 4l4 4 4-4" }, { delta: 1, path: "M2 8l4-4 4 4" }].map(({ delta, path }, idx) => (
            <button key={idx} onClick={() => adjustSize(delta)}
              style={{ width: 32, height: 32, backgroundColor: t.colors.bgBase, border: 'none', borderRadius: t.radius.md, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: t.colors.textSecondary, flexShrink: 0 }}>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d={path} stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
            </button>
          ))}
        </div>
      </div>
      <div>
        <label style={{ fontSize: '11px', color: t.colors.textMuted, marginBottom: 8, display: 'block', fontFamily: t.fonts.ui }}>Color</label>
        <div style={{ display: 'flex', gap: 6, marginBottom: 8, flexWrap: 'wrap' }}>
          {TEXT_COLOR_SWATCHES.map(c => (
            <button key={c} title={c} onClick={() => set('color', c)}
              style={{ width: 20, height: 20, borderRadius: t.radius.xs, backgroundColor: c, cursor: 'pointer', flexShrink: 0, border: 'none', outline: props.color === c ? `2px solid ${t.colors.accent}` : 'none', outlineOffset: 1 }} />
          ))}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ position: 'relative', flexShrink: 0 }}
            onMouseDown={e => e.preventDefault()}>
            <div style={{ width: 32, height: 32, borderRadius: t.radius.md, border: `1px solid ${t.colors.border}`, backgroundColor: props.color || 'transparent', cursor: 'pointer' }} />
            <input type="color" value={props.color || '#000000'} onChange={e => set('color', e.target.value)} style={{ position: 'absolute', inset: 0, opacity: 0, cursor: 'pointer', width: '100%', height: '100%' }} />
          </div>
          <input type="text" value={props.color} maxLength={7}
            onChange={e => { if (e.target.value === '' || /^#[0-9a-fA-F]{0,6}$/.test(e.target.value)) set('color', e.target.value); }}
            onBlur={e => { if (e.target.value !== '' && !/^#[0-9a-fA-F]{6}$/.test(e.target.value)) set('color', props.color); }}
            style={{ ...inputStyle, flex: 1, padding: '6px 10px', minWidth: 0 }} />
        </div>
      </div>
      <div>
        <label style={{ fontSize: '11px', color: t.colors.textMuted, marginBottom: 6, display: 'block', fontFamily: t.fonts.ui }}>Preview</label>
        <div style={{ backgroundColor: 'white', borderRadius: t.radius.md, padding: '6px 10px', overflow: 'hidden', minHeight: 36 }}>
          <span style={previewCss}>The quick brown fox</span>
        </div>
      </div>
    </div>
  );
}

const HIGHLIGHT_SWATCHES = ['#FFFF00', '#f59e0b', '#4a90e2', '#22c55e', '#ef4444', '#a855f7'];

const AppearanceContent = ({ color = '#FFFF00', opacity = 0.4, onColorChange, onOpacityChange, t }: {
  color?: string; opacity?: number; onColorChange?: (c: string) => void; onOpacityChange?: (o: number) => void; t: any;
}) => (
  <div style={{ padding: '0 16px 12px' }}>
    <label style={{ fontSize: '11px', color: t.colors.textMuted, marginBottom: 8, display: 'block' }}>Highlight Color</label>
    <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
      {HIGHLIGHT_SWATCHES.map(c => (
        <button key={c} title={c} onClick={() => onColorChange?.(c)}
          style={{ width: 20, height: 20, borderRadius: t.radius.xs, backgroundColor: c, cursor: 'pointer', border: 'none', outline: color === c ? `2px solid ${t.colors.accent}` : 'none', outlineOffset: 1 }} />
      ))}
    </div>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
      <div style={{ position: 'relative', flexShrink: 0 }}>
        <div style={{ width: 32, height: 32, borderRadius: t.radius.md, border: `1px solid ${t.colors.border}`, backgroundColor: color }} />
        <input type="color" value={color} onChange={e => onColorChange?.(e.target.value)} style={{ position: 'absolute', inset: 0, opacity: 0, cursor: 'pointer', width: '100%', height: '100%' }} />
      </div>
      <input type="text" value={color} maxLength={7}
        onChange={e => { if (/^#[0-9a-fA-F]{0,6}$/.test(e.target.value)) onColorChange?.(e.target.value); }}
        style={{ flex: 1, backgroundColor: t.colors.bgBase, color: t.colors.textPrimary, border: `1px solid ${t.colors.border}`, borderRadius: t.radius.md, padding: '6px 10px', fontSize: '12px', fontFamily: t.fonts.mono, outline: 'none' }} />
    </div>
    <label style={{ fontSize: '11px', color: t.colors.textMuted, marginBottom: 6, display: 'block' }}>Opacity — {Math.round(opacity * 100)}%</label>
    <input type="range" min={0.1} max={1} step={0.05} value={opacity}
      onChange={e => onOpacityChange?.(parseFloat(e.target.value))}
      style={{ width: '100%', accentColor: t.colors.accent, cursor: 'pointer' }} />
  </div>
);

export function RightPanel({
  documentState, activePage = 0, activeTool, textProps, onTextPropsChange,
  highlightColor, highlightOpacity, onHighlightColorChange, onHighlightOpacityChange,
  onRunOcr, isOcrProcessing, ocrError,
  openSection: controlledSection, onSectionChange,
}: RightPanelProps) {
  const { theme: t } = useTheme();
  const openSection = controlledSection ?? null;
  const toggle = (id: SectionId) => onSectionChange?.(openSection === id ? null : id);

  const [commentInput, setCommentInput] = useState('');

  const recentComments = [
    { id: 1, author: 'JD', time: '2 hours ago', text: 'Lorem ipsum dolor sit amet.' },
    { id: 2, author: 'MK', time: '3 hours ago', text: 'Lorem ipsum dolor sit amet.' },
    { id: 3, author: 'AL', time: '4 hours ago', text: 'Lorem ipsum dolor sit amet.' },
  ];

  const pageProps = documentState?.children?.[activePage];
  const w = (pageProps as any)?.metadata?.width, h = (pageProps as any)?.metadata?.height;

  return (
    <div id="text-props-panel" style={{ width: 256, backgroundColor: t.colors.bgRaised, borderLeft: `1px solid ${t.colors.bgBase}`, display: 'flex', flexDirection: 'column', flexShrink: 0, overflow: 'hidden', fontFamily: t.fonts.ui }}>
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        <Section title="Text Properties" isOpen={openSection === 'text'} onToggle={() => toggle('text')} t={t}>
          <TextPropertiesContent props={textProps} onChange={onTextPropsChange} t={t} />
        </Section>
        <Section title="Page Properties" isOpen={openSection === 'page'} onToggle={() => toggle('page')} t={t}>
          <div style={{ padding: '0 16px 12px' }}>
            {[['Number', String(activePage + 1)], ['Size', w && h ? `${Math.round(w)} × ${Math.round(h)} pt` : '—'], ['Rotation', `${(pageProps as any)?.rotation ?? 0}°`], ['Document', documentState?.file_name ?? 'None'], ['Pages', String(documentState?.children?.length ?? '—')], ['File size', bytes(documentState?.file_size)]].map(([label, value]) => (
              <PropRowInner key={label} label={label} value={value} t={t} />
            ))}
            <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
              <HoverButton icon={RotateCw} label="Rotate" t={t} />
              <HoverButton icon={Crop} label="Crop" t={t} />
            </div>
            <OcrButton onRunOcr={onRunOcr} isOcrProcessing={isOcrProcessing} ocrError={ocrError} t={t} />
          </div>
        </Section>
        <Section title="Appearance" isOpen={openSection === 'appearance'} onToggle={() => toggle('appearance')} t={t}>
          <AppearanceContent color={highlightColor} opacity={highlightOpacity} onColorChange={onHighlightColorChange} onOpacityChange={onHighlightOpacityChange} t={t} />
        </Section>
      </div>

      {/* Comments */}
      <div style={{ display: 'flex', flexDirection: 'column', borderTop: `1px solid ${t.colors.bgBase}`, flexShrink: 0, maxHeight: '45%' }}>
        <div style={{ padding: '10px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
          <h3 style={{ fontSize: '11px', fontWeight: 600, color: t.colors.textSecondary, textTransform: 'uppercase', letterSpacing: '0.07em' }}>Comments</h3>
          <button style={{ color: t.colors.textMuted, background: 'none', border: 'none', cursor: 'pointer', display: 'flex' }}
            onMouseEnter={e => (e.currentTarget.style.color = t.colors.textPrimary)}
            onMouseLeave={e => (e.currentTarget.style.color = t.colors.textMuted)}>
            <MoreVertical size={14} />
          </button>
        </div>
        <div style={{ overflowY: 'auto', flex: 1, minHeight: 0 }}>
          {recentComments.map(c => <CommentRow key={c.id} c={c} t={t} />)}
        </div>
        <div style={{ padding: 12, flexShrink: 0 }}>
          <div style={{ position: 'relative' }}>
            <input type="text" value={commentInput} onChange={e => setCommentInput(e.target.value)}
              placeholder="Add a comment…"
              style={{ width: '100%', backgroundColor: t.colors.bgBase, color: t.colors.textPrimary, border: `1px solid ${t.colors.border}`, borderRadius: t.radius.md, padding: '7px 32px 7px 10px', fontSize: '12px', outline: 'none', fontFamily: t.fonts.ui, boxSizing: 'border-box' }}
              onFocus={e => (e.currentTarget.style.borderColor = t.colors.accent)}
              onBlur={e => (e.currentTarget.style.borderColor = t.colors.border)} />
            <button style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', color: t.colors.textMuted, background: 'none', border: 'none', cursor: 'pointer', display: 'flex' }}
              onMouseEnter={e => (e.currentTarget.style.color = t.colors.accent)}
              onMouseLeave={e => (e.currentTarget.style.color = t.colors.textMuted)}>
              <Sparkles size={14} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}