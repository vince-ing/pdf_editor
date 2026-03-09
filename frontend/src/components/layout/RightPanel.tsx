// components/layout/RightPanel.tsx

import { ChevronDown, ChevronUp, MoreVertical, Sparkles, RotateCw, Crop } from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';
import type { ToolId } from '../../constants/tools';
import { DEFAULT_TEXT_PROPS, FONT_OPTIONS, type TextProps } from '../../types/textProps';

// ── Types ──────────────────────────────────────────────────────────────────────

interface PageNode {
  id?: string; rotation?: number;
  metadata?: { width?: number; height?: number };
  crop_box?: unknown; children?: unknown[];
}
interface DocumentState {
  file_name?: string; file_size?: number; children?: PageNode[];
}
interface RightPanelProps {
  documentState?:    DocumentState | null;
  activePage?:       number;
  activeTool?:       ToolId;
  textProps:         TextProps;
  onTextPropsChange: (p: TextProps) => void;
  highlightColor?: string;
  highlightOpacity?: number;
  onHighlightColorChange?: (color: string) => void;
  onHighlightOpacityChange?: (opacity: number) => void;
}

type SectionId = 'text' | 'page' | 'appearance';

const TOOL_SECTION: Partial<Record<ToolId, SectionId>> = {
  addtext: 'text', edittext: 'text',
  highlight: 'appearance', underline: 'appearance', stickynote: 'appearance',
  stamp: 'appearance', redact: 'appearance',
  insert: 'page', delete: 'page', rotate: 'page', extract: 'page', crop: 'page',
};

// ── Helpers ───────────────────────────────────────────────────────────────────

const bytes = (n?: number) => {
  if (!n) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
};

const AUTHOR_COLORS: Record<string, string> = {
  JD: 'bg-amber-500', MK: 'bg-purple-500', AL: 'bg-green-500', SA: 'bg-[#4a90e2]',
};
const getAuthorColor = (a: string) => AUTHOR_COLORS[a] ?? 'bg-gray-500';

// ── Section wrapper ────────────────────────────────────────────────────────────

const Section = ({ title, isOpen, onToggle, children }: {
  title: string; isOpen: boolean; onToggle: () => void; children: React.ReactNode;
}) => (
  <div className="border-b border-[#1e2327]">
    <button onClick={onToggle}
      className="w-full px-4 py-3 flex items-center justify-between hover:bg-[#2d3338]/40 transition-colors">
      <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-wider">{title}</h3>
      {isOpen
        ? <ChevronUp   size={14} className="text-gray-500 flex-shrink-0" />
        : <ChevronDown size={14} className="text-gray-500 flex-shrink-0" />}
    </button>
    {isOpen && <div className="animate-fade-in">{children}</div>}
  </div>
);

const StyledSelect = ({ value, onChange, options, label }: {
  value: string; onChange: (v: string) => void; options: string[]; label: string;
}) => (
  <div>
    <label className="text-[11px] text-gray-500 mb-1.5 block">{label}</label>
    <div className="relative">
      <select value={value} onChange={e => onChange(e.target.value)}
        className="w-full bg-[#1e2327] text-white px-3 py-2 rounded-md text-xs appearance-none cursor-pointer focus:outline-none focus:ring-1 focus:ring-[#4a90e2] transition-all">
        {options.map(o => <option key={o}>{o}</option>)}
      </select>
      <ChevronDown size={12} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
    </div>
  </div>
);

const PropRow = ({ label, value }: { label: string; value: string }) => (
  <div className="flex items-center justify-between gap-2 mb-1.5">
    <span className="text-[11px] text-gray-500 flex-shrink-0">{label}</span>
    <span className="text-[11px] text-gray-200 font-mono text-right truncate">{value}</span>
  </div>
);

// ── Text color swatches ────────────────────────────────────────────────────────

const TEXT_COLOR_SWATCHES = [
  '#000000', '#ffffff', '#ef4444', '#f59e0b',
  '#22c55e', '#4a90e2', '#a855f7', '#ec4899',
];

// ── TextPropertiesContent ──────────────────────────────────────────────────────

function TextPropertiesContent({ props, onChange }: {
  props: TextProps; onChange: (p: TextProps) => void;
}) {
  const set = useCallback(<K extends keyof TextProps>(key: K, val: TextProps[K]) => {
    onChange({ ...props, [key]: val });
  }, [props, onChange]);

  const [sizeInput, setSizeInput] = useState(String(props.fontSize));
  useEffect(() => { setSizeInput(String(props.fontSize)); }, [props.fontSize]);

  const commitSize = () => {
    const n = parseFloat(sizeInput);
    if (!isNaN(n) && n > 0) set('fontSize', Math.min(144, Math.max(4, n)));
    else setSizeInput(String(props.fontSize));
  };

  const adjustSize = (delta: number) => {
    const n = Math.min(144, Math.max(4, props.fontSize + delta));
    set('fontSize', n);
    setSizeInput(String(n));
  };

  // CSS for live preview
  const previewCss: React.CSSProperties = {
    fontFamily: props.fontFamily === 'Times New Roman'
      ? '"Times New Roman", Times, serif'
      : props.fontFamily === 'Courier'
        ? '"Courier New", Courier, monospace'
        : 'Helvetica, Arial, sans-serif',
    fontWeight:  props.isBold   ? 'bold'   : 'normal',
    fontStyle:   props.isItalic ? 'italic' : 'normal',
    fontSize:    Math.min(props.fontSize, 18),
    color:       props.color,
    lineHeight:  1.3,
  };

  return (
    <div
      className="px-4 pb-4 space-y-3"
      onMouseDown={e => {
        // Prevent any click in the panel from stealing focus from the canvas editor,
        // EXCEPT clicks on actual text inputs (hex field, size field) which need focus.
        const target = e.target as HTMLElement;
        const isTextInput = target.tagName === 'INPUT' && (target as HTMLInputElement).type === 'text';
        if (!isTextInput) e.preventDefault();
      }}
    >

      {/* Font family */}
      <StyledSelect label="Font" value={props.fontFamily}
        onChange={v => set('fontFamily', v)} options={FONT_OPTIONS} />

      {/* Size + B + I in one row */}
      <div>
        <label className="text-[11px] text-gray-500 mb-1.5 block">Style &amp; Size</label>
        <div className="flex items-center gap-1.5">

          {/* Bold toggle */}
          <button
            onClick={() => set('isBold', !props.isBold)}
            title="Bold"
            className={`w-8 h-8 rounded-md flex items-center justify-center text-sm font-bold transition-colors flex-shrink-0
              ${props.isBold
                ? 'bg-[#4a90e2] text-white'
                : 'bg-[#1e2327] text-gray-400 hover:text-white hover:bg-[#3d4449]'}`}
          >B</button>

          {/* Italic toggle */}
          <button
            onClick={() => set('isItalic', !props.isItalic)}
            title="Italic"
            className={`w-8 h-8 rounded-md flex items-center justify-center text-sm italic font-serif transition-colors flex-shrink-0
              ${props.isItalic
                ? 'bg-[#4a90e2] text-white'
                : 'bg-[#1e2327] text-gray-400 hover:text-white hover:bg-[#3d4449]'}`}
          >I</button>

          {/* Divider */}
          <div className="w-px h-5 bg-white/10 flex-shrink-0" />

          {/* Size input */}
          <input
            type="text"
            value={sizeInput}
            onChange={e => setSizeInput(e.target.value)}
            onBlur={commitSize}
            onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur(); }}
            className="w-14 bg-[#1e2327] text-white px-2 py-2 rounded-md text-xs text-center focus:outline-none focus:ring-1 focus:ring-[#4a90e2] flex-shrink-0"
          />

          {/* Down arrow */}
          <button onClick={() => adjustSize(-1)} title="Decrease size"
            className="w-8 h-8 bg-[#1e2327] text-gray-400 hover:text-white hover:bg-[#3d4449] rounded-md flex items-center justify-center transition-colors flex-shrink-0">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>

          {/* Up arrow */}
          <button onClick={() => adjustSize(1)} title="Increase size"
            className="w-8 h-8 bg-[#1e2327] text-gray-400 hover:text-white hover:bg-[#3d4449] rounded-md flex items-center justify-center transition-colors flex-shrink-0">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M2 8l4-4 4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>

        </div>
      </div>

      {/* Color */}
      <div>
        <label className="text-[11px] text-gray-500 mb-2 block">Color</label>
        <div className="flex gap-1.5 mb-2 flex-wrap">
          {TEXT_COLOR_SWATCHES.map(c => (
            <button key={c} title={c} onClick={() => set('color', c)}
              style={{ backgroundColor: c }}
              className={`w-5 h-5 rounded transition-all flex-shrink-0
                ${props.color === c
                  ? 'ring-2 ring-[#4a90e2] ring-offset-1 ring-offset-[#25292d]'
                  : 'hover:ring-2 hover:ring-white/40'}
                ${c === '#ffffff' ? 'border border-white/20' : ''}`}
            />
          ))}
        </div>
        <div className="flex items-center gap-2">
          <div className="relative flex-shrink-0">
            <div className="w-8 h-8 rounded-md border border-white/10 cursor-pointer"
              style={{ backgroundColor: props.color }} />
            <input type="color" value={props.color} onChange={e => set('color', e.target.value)}
              className="absolute inset-0 opacity-0 cursor-pointer w-full h-full" title="Custom color" />
          </div>
          <input type="text" value={props.color}
            onChange={e => { if (/^#[0-9a-fA-F]{0,6}$/.test(e.target.value)) set('color', e.target.value); }}
            onBlur={e => { if (!/^#[0-9a-fA-F]{6}$/.test(e.target.value)) set('color', props.color); }}
            maxLength={7}
            className="flex-1 bg-[#1e2327] text-white px-3 py-2 rounded-md text-xs font-mono focus:outline-none focus:ring-1 focus:ring-[#4a90e2] min-w-0"
            placeholder="#000000" />
        </div>
      </div>

      {/* Live preview */}
      <div>
        <label className="text-[11px] text-gray-500 mb-1.5 block">Preview</label>
        <div className="bg-white rounded-md px-3 py-2 overflow-hidden min-h-[36px]">
          <span style={previewCss}>The quick brown fox</span>
        </div>
      </div>

    </div>
  );
}

// ── PagePropertiesContent ──────────────────────────────────────────────────────

const PagePropertiesContent = ({ documentState, activePage }: {
  documentState?: DocumentState | null; activePage: number;
}) => {
  const page = documentState?.children?.[activePage];
  const w = page?.metadata?.width, h = page?.metadata?.height;
  return (
    <div className="px-4 pb-3">
      <PropRow label="Number"    value={String(activePage + 1)} />
      <PropRow label="Size"      value={w && h ? `${Math.round(w)} × ${Math.round(h)} pt` : '—'} />
      <PropRow label="Rotation"  value={`${(page as any)?.rotation ?? 0}°`} />
      <PropRow label="Document"  value={documentState?.file_name ?? 'None'} />
      <PropRow label="Pages"     value={String(documentState?.children?.length ?? '—')} />
      <PropRow label="File size" value={bytes(documentState?.file_size)} />
      <div className="flex gap-1.5 mt-2">
        <button className="flex-1 h-7 text-[11px] bg-[#1e2327] text-gray-500 hover:text-white hover:bg-[#3d4449] rounded-md transition-colors flex items-center justify-center gap-1.5">
          <RotateCw size={12} /> Rotate
        </button>
        <button className="flex-1 h-7 text-[11px] bg-[#1e2327] text-gray-500 hover:text-white hover:bg-[#3d4449] rounded-md transition-colors flex items-center justify-center gap-1.5">
          <Crop size={12} /> Crop
        </button>
      </div>
    </div>
  );
};

// ── AppearanceContent ──────────────────────────────────────────────────────────

const HIGHLIGHT_SWATCHES = ['#FFFF00', '#f59e0b', '#4a90e2', '#22c55e', '#ef4444', '#a855f7'];

const AppearanceContent = ({ color = '#FFFF00', opacity = 0.4, onColorChange, onOpacityChange }: {
  color?: string; opacity?: number;
  onColorChange?: (c: string) => void; onOpacityChange?: (o: number) => void;
}) => (
  <div className="px-4 pb-3">
    <label className="text-[11px] text-gray-500 mb-2 block">Highlight Color</label>
    <div className="flex gap-2 mb-3 flex-wrap">
      {HIGHLIGHT_SWATCHES.map(c => (
        <button key={c} title={c} onClick={() => onColorChange?.(c)}
          style={{ backgroundColor: c }}
          className={`w-5 h-5 rounded cursor-pointer transition-all flex-shrink-0
            ${color === c ? 'ring-2 ring-[#4a90e2] ring-offset-1 ring-offset-[#25292d]' : 'hover:ring-2 hover:ring-white/40'}`} />
      ))}
    </div>
    <div className="flex items-center gap-2 mb-3">
      <div className="relative flex-shrink-0">
        <div className="w-8 h-8 rounded-md border border-white/10" style={{ backgroundColor: color }} />
        <input type="color" value={color} onChange={e => onColorChange?.(e.target.value)}
          className="absolute inset-0 opacity-0 cursor-pointer w-full h-full" />
      </div>
      <input type="text" value={color} maxLength={7}
        onChange={e => { if (/^#[0-9a-fA-F]{0,6}$/.test(e.target.value)) onColorChange?.(e.target.value); }}
        className="flex-1 bg-[#1e2327] text-white px-3 py-2 rounded-md text-xs font-mono focus:outline-none focus:ring-1 focus:ring-[#4a90e2]" />
    </div>
    <label className="text-[11px] text-gray-500 mb-1.5 block">Opacity — {Math.round(opacity * 100)}%</label>
    <input type="range" min={0.1} max={1} step={0.05} value={opacity}
      onChange={e => onOpacityChange?.(parseFloat(e.target.value))}
      className="w-full accent-[#4a90e2] cursor-pointer" />
  </div>
);

// ── RightPanel ─────────────────────────────────────────────────────────────────

export function RightPanel({
  documentState, activePage = 0, activeTool, textProps, onTextPropsChange,
  highlightColor, highlightOpacity, onHighlightColorChange, onHighlightOpacityChange,
}: RightPanelProps) {
  const [openSection, setOpenSection] = useState<SectionId | null>(null);
  const [commentInput, setCommentInput] = useState('');

  useEffect(() => {
    setOpenSection(activeTool ? TOOL_SECTION[activeTool] ?? null : null);
  }, [activeTool]);

  const toggle = (id: SectionId) => setOpenSection(prev => prev === id ? null : id);

  const recentComments = [
    { id: 1, author: 'JD', time: '2 hours ago', text: 'Lorem ipsum dolor sit amet.' },
    { id: 2, author: 'MK', time: '3 hours ago', text: 'Lorem ipsum dolor sit amet.' },
    { id: 3, author: 'AL', time: '4 hours ago', text: 'Lorem ipsum dolor sit amet.' },
  ];

  return (
    <div id="text-props-panel" className="w-64 bg-[#25292d] border-l border-[#1e2327] flex flex-col flex-shrink-0 overflow-hidden">
      <div className="flex-1 overflow-y-auto min-h-0">

        <Section title="Text Properties" isOpen={openSection === 'text'} onToggle={() => toggle('text')}>
          <TextPropertiesContent props={textProps} onChange={onTextPropsChange} />
        </Section>

        <Section title="Page Properties" isOpen={openSection === 'page'} onToggle={() => toggle('page')}>
          <PagePropertiesContent documentState={documentState} activePage={activePage} />
        </Section>

        <Section title="Appearance" isOpen={openSection === 'appearance'} onToggle={() => toggle('appearance')}>
          <AppearanceContent
            color={highlightColor} opacity={highlightOpacity}
            onColorChange={onHighlightColorChange} onOpacityChange={onHighlightOpacityChange}
          />
        </Section>

      </div>

      {/* Comments */}
      <div className="flex flex-col border-t border-[#1e2327] flex-shrink-0" style={{ maxHeight: '45%' }}>
        <div className="px-4 py-3 flex items-center justify-between flex-shrink-0">
          <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-wider">Comments</h3>
          <button className="text-gray-500 hover:text-white transition-colors"><MoreVertical size={14} /></button>
        </div>
        <div className="overflow-y-auto flex-1 min-h-0">
          {recentComments.map(c => (
            <div key={c.id} className="px-4 py-3 border-b border-[#1e2327] hover:bg-[#2d3338] cursor-pointer transition-colors">
              <div className="flex items-start gap-2">
                <div className={`w-6 h-6 rounded-full ${getAuthorColor(c.author)} flex items-center justify-center flex-shrink-0`}>
                  <span className="text-white text-[10px] font-bold">{c.author}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] text-gray-500 mb-0.5">{c.time}</div>
                  <div className="text-xs text-white leading-snug">{c.text}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
        <div className="p-3 flex-shrink-0">
          <div className="relative">
            <input type="text" value={commentInput} onChange={e => setCommentInput(e.target.value)}
              placeholder="Add a comment…"
              className="w-full bg-[#1e2327] text-white placeholder-gray-600 px-3 py-2 pr-9 rounded-md text-xs focus:outline-none focus:ring-1 focus:ring-[#4a90e2] transition-all" />
            <button className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-[#4a90e2] transition-colors">
              <Sparkles size={14} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}