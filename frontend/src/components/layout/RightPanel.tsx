// components/layout/RightPanel.tsx
// Collapsed by default. Active tool auto-expands the relevant section.
// Comments pinned at bottom. Everything else scrollable.
//
// Tool → section mapping:
//   addtext, edittext          → Text Properties
//   highlight, underline,
//   stickynote, stamp, redact  → Appearance
//   insert, delete, rotate,
//   extract, crop              → Page Properties
//   hand, select, zoom         → nothing (all collapsed)

import {
  ChevronDown, ChevronUp, AlignLeft, AlignCenter, AlignRight,
  MoreVertical, Sparkles, RotateCw, Crop, Maximize2, Minimize2,
} from 'lucide-react';
import { useState, useEffect } from 'react';
import type { ToolId } from '../../constants/tools';

// ── Types ─────────────────────────────────────────────────────────────────────

interface PageNode {
  id?: string;
  rotation?: number;
  metadata?: { width?: number; height?: number };
  crop_box?: unknown;
  children?: unknown[];
}

interface DocumentState {
  file_name?: string;
  file_size?: number;
  children?: PageNode[];
}

interface RightPanelProps {
  documentState?: DocumentState | null;
  activePage?: number;
  activeTool?: ToolId;
}

type SectionId = 'text' | 'page' | 'appearance';

// ── Which section should auto-open for each tool ──────────────────────────────

const TOOL_SECTION: Partial<Record<ToolId, SectionId>> = {
  addtext:    'text',
  edittext:   'text',
  highlight:  'appearance',
  underline:  'appearance',
  stickynote: 'appearance',
  stamp:      'appearance',
  redact:     'appearance',
  insert:     'page',
  delete:     'page',
  rotate:     'page',
  extract:    'page',
  crop:       'page',
};

// ── Helpers ───────────────────────────────────────────────────────────────────

const bytes = (n?: number) => {
  if (!n) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
};

const AUTHOR_COLORS: Record<string, string> = {
  JD: 'bg-amber-500',
  MK: 'bg-purple-500',
  AL: 'bg-green-500',
  SA: 'bg-[#4a90e2]',
};
const getAuthorColor = (a: string) => AUTHOR_COLORS[a] ?? 'bg-gray-500';

// ── Section wrapper ───────────────────────────────────────────────────────────

const Section = ({
  title, isOpen, onToggle, children,
}: {
  title: string;
  isOpen: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) => (
  <div className="border-b border-[#1e2327]">
    <button
      onClick={onToggle}
      className="w-full px-4 py-3 flex items-center justify-between hover:bg-[#2d3338]/40 transition-colors"
    >
      <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-wider">{title}</h3>
      {isOpen
        ? <ChevronUp size={14} className="text-gray-500 flex-shrink-0" />
        : <ChevronDown size={14} className="text-gray-500 flex-shrink-0" />
      }
    </button>
    {isOpen && (
      <div className="animate-fade-in">
        {children}
      </div>
    )}
  </div>
);

// ── Styled select ─────────────────────────────────────────────────────────────

const StyledSelect = ({ value, onChange, options, label }: {
  value: string; onChange: (v: string) => void; options: string[]; label: string;
}) => (
  <div>
    <label className="text-[11px] text-gray-500 mb-1.5 block">{label}</label>
    <div className="relative">
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full bg-[#1e2327] text-white px-3 py-2 rounded-md text-xs appearance-none cursor-pointer focus:outline-none focus:ring-1 focus:ring-[#4a90e2] transition-all"
      >
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

// ── Section content ───────────────────────────────────────────────────────────

const TextPropertiesContent = () => {
  const [font, setFont] = useState('Inter');
  const [fontWeight, setFontWeight] = useState('Semibold');
  const [fontSize, setFontSize] = useState('12pt');
  const [alignment, setAlignment] = useState<'left' | 'center' | 'right'>('left');

  return (
    <div className="px-4 pb-4 space-y-3">
      <StyledSelect label="Font" value={font} onChange={setFont}
        options={['Inter', 'DM Sans', 'Arial', 'Helvetica', 'Georgia', 'Times New Roman']} />
      <StyledSelect label="Weight" value={fontWeight} onChange={setFontWeight}
        options={['Regular', 'Medium', 'Semibold', 'Bold']} />
      <div>
        <label className="text-[11px] text-gray-500 mb-1.5 block">Size</label>
        <div className="flex items-center gap-2">
          <input
            type="text" value={fontSize} onChange={e => setFontSize(e.target.value)}
            className="flex-1 bg-[#1e2327] text-white px-3 py-2 rounded-md text-xs focus:outline-none focus:ring-1 focus:ring-[#4a90e2]"
          />
          <button className="bg-[#1e2327] text-gray-500 p-2 rounded-md hover:text-white hover:bg-[#3d4449] transition-colors"><Maximize2 size={13} /></button>
          <button className="bg-[#1e2327] text-gray-500 p-2 rounded-md hover:text-white hover:bg-[#3d4449] transition-colors"><Minimize2 size={13} /></button>
        </div>
      </div>
      <div>
        <label className="text-[11px] text-gray-500 mb-1.5 block">Alignment</label>
        <div className="grid grid-cols-3 gap-1.5">
          {([
            { id: 'left',   Icon: AlignLeft   },
            { id: 'center', Icon: AlignCenter  },
            { id: 'right',  Icon: AlignRight   },
          ] as const).map(({ id, Icon }) => (
            <button key={id} onClick={() => setAlignment(id)}
              className={`py-2 rounded-md flex items-center justify-center transition-colors
                ${alignment === id ? 'bg-[#4a90e2] text-white' : 'bg-[#1e2327] text-gray-500 hover:text-white hover:bg-[#3d4449]'}`}>
              <Icon size={14} />
            </button>
          ))}
        </div>
      </div>
      <div>
        <label className="text-[11px] text-gray-500 mb-1.5 block">Spacing</label>
        <div className="grid grid-cols-2 gap-1.5">
          <input defaultValue="12pt" className="bg-[#1e2327] text-white px-3 py-2 rounded-md text-xs focus:outline-none focus:ring-1 focus:ring-[#4a90e2]" />
          <input defaultValue="0" className="bg-[#1e2327] text-white px-3 py-2 rounded-md text-xs focus:outline-none focus:ring-1 focus:ring-[#4a90e2]" />
        </div>
      </div>
    </div>
  );
};

const PagePropertiesContent = ({ documentState, activePage }: {
  documentState?: DocumentState | null; activePage: number;
}) => {
  const page = documentState?.children?.[activePage];
  const w = page?.metadata?.width;
  const h = page?.metadata?.height;
  return (
    <div className="px-4 pb-3">
      <PropRow label="Number"    value={String(activePage + 1)} />
      <PropRow label="Size"      value={w && h ? `${Math.round(w)} × ${Math.round(h)} pt` : '—'} />
      <PropRow label="Rotation"  value={`${page?.rotation ?? 0}°`} />
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

const AppearanceContent = () => (
  <div className="px-4 pb-3">
    <label className="text-[11px] text-gray-500 mb-2 block">Highlight Color</label>
    <div className="flex gap-2 mb-3 flex-wrap">
      {['#f59e0b', '#4a90e2', '#22c55e', '#ef4444', '#a855f7', '#06b6d4'].map(c => (
        <div key={c} title={c}
          className="w-5 h-5 rounded cursor-pointer hover:ring-2 hover:ring-white/40 transition-all"
          style={{ backgroundColor: c }} />
      ))}
    </div>
    <label className="text-[11px] text-gray-500 mb-1.5 block">Opacity</label>
    <input type="range" min={0.1} max={1} step={0.05} defaultValue={0.45}
      className="w-full accent-[#4a90e2] cursor-pointer" />
  </div>
);

// ── RightPanel ────────────────────────────────────────────────────────────────

export function RightPanel({ documentState, activePage = 0, activeTool }: RightPanelProps) {
  const [openSection, setOpenSection] = useState<SectionId | null>(null);
  const [commentInput, setCommentInput] = useState('');

  // Auto-expand the relevant section when tool changes
  useEffect(() => {
    const section = activeTool ? TOOL_SECTION[activeTool] ?? null : null;
    setOpenSection(section);
  }, [activeTool]);

  const toggle = (id: SectionId) =>
    setOpenSection(prev => prev === id ? null : id);

  const recentComments = [
    { id: 1, author: 'JD', time: '2 hours ago', text: 'Lorem ipsum dolor sit amet.' },
    { id: 2, author: 'MK', time: '3 hours ago', text: 'Lorem ipsum dolor sit amet.' },
    { id: 3, author: 'AL', time: '4 hours ago', text: 'Lorem ipsum dolor sit amet.' },
  ];

  return (
    <div className="w-64 bg-[#25292d] border-l border-[#1e2327] flex flex-col flex-shrink-0 overflow-hidden">

      {/* ── Scrollable properties area ── */}
      <div className="flex-1 overflow-y-auto min-h-0">
        <Section title="Text Properties" isOpen={openSection === 'text'} onToggle={() => toggle('text')}>
          <TextPropertiesContent />
        </Section>

        <Section title="Page Properties" isOpen={openSection === 'page'} onToggle={() => toggle('page')}>
          <PagePropertiesContent documentState={documentState} activePage={activePage} />
        </Section>

        <Section title="Appearance" isOpen={openSection === 'appearance'} onToggle={() => toggle('appearance')}>
          <AppearanceContent />
        </Section>
      </div>

      {/* ── Comments — pinned at bottom ── */}
      <div className="flex flex-col border-t border-[#1e2327] flex-shrink-0" style={{ maxHeight: '45%' }}>
        {/* Header */}
        <div className="px-4 py-3 flex items-center justify-between flex-shrink-0">
          <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-wider">Comments</h3>
          <button className="text-gray-500 hover:text-white transition-colors">
            <MoreVertical size={14} />
          </button>
        </div>

        {/* Comment list — scrollable within its zone */}
        <div className="overflow-y-auto flex-1 min-h-0">
          {recentComments.map(comment => (
            <div key={comment.id}
              className="px-4 py-3 border-b border-[#1e2327] hover:bg-[#2d3338] cursor-pointer transition-colors">
              <div className="flex items-start gap-2">
                <div className={`w-6 h-6 rounded-full ${getAuthorColor(comment.author)} flex items-center justify-center flex-shrink-0`}>
                  <span className="text-white text-[10px] font-bold">{comment.author}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] text-gray-500 mb-0.5">{comment.time}</div>
                  <div className="text-xs text-white leading-snug">{comment.text}</div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Add comment input — always visible */}
        <div className="p-3 flex-shrink-0">
          <div className="relative">
            <input
              type="text" value={commentInput} onChange={e => setCommentInput(e.target.value)}
              placeholder="Add a comment…"
              className="w-full bg-[#1e2327] text-white placeholder-gray-600 px-3 py-2 pr-9 rounded-md text-xs focus:outline-none focus:ring-1 focus:ring-[#4a90e2] transition-all"
            />
            <button className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-[#4a90e2] transition-colors">
              <Sparkles size={14} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}