// frontend/src/components/toolbar/Toolbar.tsx
import { Undo2, Redo2, Volume2, Minus, Plus, ScanText, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { TOOL_DEFS, type ToolId } from '../../constants/tools';
import { useTheme } from '../../theme';

export type { ToolId };

interface ToolbarProps {
  activeTool: ToolId; onToolChange: (tool: ToolId) => void;
  scale: number; onZoomIn: () => void; onZoomOut: () => void; onZoomReset: () => void;
  onUndo: () => void; onRedo: () => void;
  onReadPage: () => void; onReadSelection: () => void;
  hasSelection: boolean; ttsActive: boolean;
  pageInfo?: { current: number; total: number } | null;
  onRunOcr?: () => void; isOcrProcessing?: boolean;
}

type TabId = 'view' | 'edit' | 'comment' | 'pages';
const TABS: { id: TabId; label: string }[] = [
  { id: 'view', label: 'View' }, { id: 'edit', label: 'Edit' },
  { id: 'comment', label: 'Comment' }, { id: 'pages', label: 'Pages' },
];

const ToolBtn = ({ icon: Icon, label, isActive, onClick }: {
  icon: React.ComponentType<{ size?: number }>; label: string; isActive: boolean; onClick: () => void;
}) => {
  const { theme: t } = useTheme();
  const [hov, setHov] = useState(false);
  return (
    <button onClick={onClick} title={label}
      onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        gap: '6px', padding: '0 16px', borderRadius: t.radius.md, flexShrink: 0, height: '100%',
        minWidth: '64px', border: 'none', cursor: 'pointer', transition: t.t.fast, // slightly larger minWidth for touch targets
        backgroundColor: isActive ? t.colors.accent : hov ? t.colors.bgHover : 'transparent',
        color: isActive ? '#fff' : hov ? t.colors.textPrimary : t.colors.textSecondary,
      }}>
      <Icon size={19} />
      <span style={{ fontSize: '11px', lineHeight: 1, whiteSpace: 'nowrap' }}>{label}</span>
    </button>
  );
};

const SmallToolBtn = ({ icon: Icon, label, isActive, onClick, disabled }: {
  icon: React.ComponentType<{ size?: number }>; label: string;
  isActive: boolean; onClick: () => void; disabled?: boolean;
}) => {
  const { theme: t } = useTheme();
  const [hov, setHov] = useState(false);
  return (
    <button onClick={onClick} disabled={disabled} title={label}
      onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 12px',
        borderRadius: t.radius.sm, width: '100%', border: 'none', cursor: disabled ? 'not-allowed' : 'pointer',
        transition: t.t.fast, opacity: disabled ? 0.3 : 1, flexShrink: 0,
        backgroundColor: isActive ? t.colors.accent : hov && !disabled ? t.colors.bgHover : 'transparent',
        color: isActive ? '#fff' : hov && !disabled ? t.colors.textPrimary : t.colors.textSecondary,
      }}>
      <Icon size={14} />
      <span style={{ fontSize: '11px', lineHeight: 1, whiteSpace: 'nowrap' }}>{label}</span>
    </button>
  );
};

const Rule = () => {
  const { theme: t } = useTheme();
  return <div style={{ width: '1px', backgroundColor: t.colors.border, margin: '8px 12px', flexShrink: 0, alignSelf: 'stretch' }} />;
};

const PairCol = ({ tools, activeTool, onToolChange }: {
  tools: (typeof TOOL_DEFS[number])[]; activeTool: ToolId; onToolChange: (id: ToolId) => void;
}) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', justifyContent: 'center', height: '100%', padding: '6px 0', minWidth: '110px', flexShrink: 0 }}>
    {tools.map(t => (
      <SmallToolBtn key={t.id} icon={t.icon} label={t.label}
        isActive={activeTool === t.id} onClick={() => onToolChange(t.id)} />
    ))}
  </div>
);

const byId = (ids: ToolId[]) => ids.map(id => TOOL_DEFS.find(t => t.id === id)!).filter(Boolean);

function ViewTab({ activeTool, onToolChange, scale, onZoomIn, onZoomOut, onZoomReset }: {
  activeTool: ToolId; onToolChange: (id: ToolId) => void;
  scale: number; onZoomIn: () => void; onZoomOut: () => void; onZoomReset: () => void;
}) {
  const { theme: t } = useTheme();
  const [hovOut, setHovOut] = useState(false);
  const [hovReset, setHovReset] = useState(false);
  const [hovIn, setHovIn] = useState(false);
  return (
    <>
      {byId(['hand', 'select', 'zoom']).map(t2 => (
        <ToolBtn key={t2.id} icon={t2.icon} label={t2.label}
          isActive={activeTool === t2.id} onClick={() => onToolChange(t2.id)} />
      ))}
      <Rule />
      <div style={{ display: 'flex', alignItems: 'center', gap: '2px', backgroundColor: t.colors.bgBase, borderRadius: t.radius.md, padding: '0 6px', alignSelf: 'center', flexShrink: 0 }}>
        <button onClick={onZoomOut} disabled={scale <= 0.25}
          onMouseEnter={() => setHovOut(true)} onMouseLeave={() => setHovOut(false)}
          style={{ width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: t.radius.sm, border: 'none', cursor: scale <= 0.25 ? 'not-allowed' : 'pointer', opacity: scale <= 0.25 ? 0.3 : 1, backgroundColor: hovOut ? t.colors.bgHover : 'transparent', color: t.colors.textSecondary, transition: t.t.fast, flexShrink: 0 }}>
          <Minus size={13} />
        </button>
        <button onClick={onZoomReset}
          onMouseEnter={() => setHovReset(true)} onMouseLeave={() => setHovReset(false)}
          style={{ minWidth: 46, height: 32, fontSize: '11px', fontWeight: 600, fontFamily: t.fonts.mono, padding: '0 4px', borderRadius: t.radius.sm, border: 'none', cursor: 'pointer', backgroundColor: hovReset ? t.colors.bgHover : 'transparent', color: t.colors.textPrimary, transition: t.t.fast, flexShrink: 0 }}>
          {Math.round(scale * 100)}%
        </button>
        <button onClick={onZoomIn} disabled={scale >= 4.0}
          onMouseEnter={() => setHovIn(true)} onMouseLeave={() => setHovIn(false)}
          style={{ width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: t.radius.sm, border: 'none', cursor: scale >= 4.0 ? 'not-allowed' : 'pointer', opacity: scale >= 4.0 ? 0.3 : 1, backgroundColor: hovIn ? t.colors.bgHover : 'transparent', color: t.colors.textSecondary, transition: t.t.fast, flexShrink: 0 }}>
          <Plus size={13} />
        </button>
      </div>
    </>
  );
}

function EditTab({ activeTool, onToolChange, onUndo, onRedo }: {
  activeTool: ToolId; onToolChange: (id: ToolId) => void; onUndo: () => void; onRedo: () => void;
}) {
  return (
    <>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', justifyContent: 'center', height: '100%', padding: '6px 0', minWidth: '90px', flexShrink: 0 }}>
        <SmallToolBtn icon={Undo2} label="Undo" isActive={false} onClick={onUndo} />
        <SmallToolBtn icon={Redo2} label="Redo" isActive={false} onClick={onRedo} />
      </div>
      <Rule />
      {byId(['addtext', 'edittext']).map(t => (
        <ToolBtn key={t.id} icon={t.icon} label={t.label} isActive={activeTool === t.id} onClick={() => onToolChange(t.id)} />
      ))}
      <Rule />
      <PairCol tools={byId(['addimage', 'link'])} activeTool={activeTool} onToolChange={onToolChange} />
    </>
  );
}

function CommentTab({ activeTool, onToolChange, onReadPage, onReadSelection, ttsActive, hasSelection }: {
  activeTool: ToolId; onToolChange: (id: ToolId) => void;
  onReadPage: () => void; onReadSelection: () => void; ttsActive: boolean; hasSelection: boolean;
}) {
  return (
    <>
      {byId(['highlight', 'underline']).map(t => (
        <ToolBtn key={t.id} icon={t.icon} label={t.label} isActive={activeTool === t.id} onClick={() => onToolChange(t.id)} />
      ))}
      <Rule />
      <PairCol tools={byId(['stickynote', 'stamp'])} activeTool={activeTool} onToolChange={onToolChange} />
      <ToolBtn icon={TOOL_DEFS.find(t => t.id === 'redact')!.icon} label="Redact"
        isActive={activeTool === 'redact'} onClick={() => onToolChange('redact')} />
      <Rule />
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', justifyContent: 'center', height: '100%', padding: '6px 0', minWidth: '120px', flexShrink: 0 }}>
        <SmallToolBtn icon={Volume2} label="Read Page" isActive={false} onClick={onReadPage} disabled={ttsActive} />
        <SmallToolBtn icon={Volume2} label="Read Selection" isActive={false} onClick={onReadSelection} disabled={ttsActive || !hasSelection} />
      </div>
    </>
  );
}

function PagesTab({ activeTool, onToolChange, onRunOcr, isOcrProcessing }: {
  activeTool: ToolId; onToolChange: (id: ToolId) => void;
  onRunOcr?: () => void; isOcrProcessing?: boolean;
}) {
  const { theme: t } = useTheme();
  const [hovOcr, setHovOcr] = useState(false);
  return (
    <>
      {byId(['insert', 'delete']).map(td => (
        <ToolBtn key={td.id} icon={td.icon} label={td.label} isActive={activeTool === td.id} onClick={() => onToolChange(td.id)} />
      ))}
      <Rule />
      <PairCol tools={byId(['rotate', 'extract'])} activeTool={activeTool} onToolChange={onToolChange} />
      <ToolBtn icon={TOOL_DEFS.find(td => td.id === 'crop')!.icon} label="Crop"
        isActive={activeTool === 'crop'} onClick={() => onToolChange('crop')} />
      <Rule />
      <button
        onClick={onRunOcr}
        disabled={isOcrProcessing || !onRunOcr}
        title="Run OCR on current page to extract text from scanned content"
        onMouseEnter={() => setHovOcr(true)}
        onMouseLeave={() => setHovOcr(false)}
        style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          gap: '6px', padding: '0 16px', borderRadius: t.radius.md, flexShrink: 0, height: '100%',
          minWidth: '64px', border: 'none', cursor: isOcrProcessing || !onRunOcr ? 'not-allowed' : 'pointer',
          transition: t.t.fast, opacity: !onRunOcr ? 0.4 : 1,
          backgroundColor: hovOcr && !isOcrProcessing && onRunOcr ? t.colors.bgHover : 'transparent',
          color: isOcrProcessing ? t.colors.accent : hovOcr && onRunOcr ? t.colors.textPrimary : t.colors.textSecondary,
        }}>
        {isOcrProcessing
          ? <Loader2 size={19} style={{ animation: 'spin 1s linear infinite' }} />
          : <ScanText size={19} />}
        <span style={{ fontSize: '11px', lineHeight: 1, whiteSpace: 'nowrap' }}>
          {isOcrProcessing ? 'Running…' : 'OCR'}
        </span>
      </button>
    </>
  );
}

export function Toolbar({
  activeTool, onToolChange, scale, onZoomIn, onZoomOut, onZoomReset,
  onUndo, onRedo, onReadPage, onReadSelection, hasSelection, ttsActive, pageInfo,
  onRunOcr, isOcrProcessing,
}: ToolbarProps) {
  const { theme: t } = useTheme();
  const [activeTab, setActiveTab] = useState<TabId>('view');

  const handleToolChange = (id: ToolId) => {
    onToolChange(id);
    const cat = TOOL_DEFS.find(t2 => t2.id === id)?.category as TabId | undefined;
    if (cat && TABS.some(t2 => t2.id === cat)) setActiveTab(cat);
  };

  return (
    <div style={{ backgroundColor: t.colors.bgRaised, borderBottom: `1px solid ${t.colors.bgBase}`, flexShrink: 0, display: 'flex', flexDirection: 'column', minWidth: 0 }}>

      {/* Ribbon body (Tools) - Added scrollbar-hide and overflow-x-auto for mobile */}
      <div className="scrollbar-hide" style={{ padding: '0 16px', display: 'flex', alignItems: 'stretch', height: '58px', gap: '4px', overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
        {activeTab === 'view'    && <ViewTab    activeTool={activeTool} onToolChange={handleToolChange} scale={scale} onZoomIn={onZoomIn} onZoomOut={onZoomOut} onZoomReset={onZoomReset} />}
        {activeTab === 'edit'    && <EditTab    activeTool={activeTool} onToolChange={handleToolChange} onUndo={onUndo} onRedo={onRedo} />}
        {activeTab === 'comment' && <CommentTab activeTool={activeTool} onToolChange={handleToolChange} onReadPage={onReadPage} onReadSelection={onReadSelection} ttsActive={ttsActive} hasSelection={hasSelection} />}
        {activeTab === 'pages'   && <PagesTab   activeTool={activeTool} onToolChange={handleToolChange} onRunOcr={onRunOcr} isOcrProcessing={isOcrProcessing} />}
      </div>

      {/* Tab strip - Added scrollbar-hide and overflow-x-auto */}
      <div className="scrollbar-hide" style={{ display: 'flex', alignItems: 'flex-start', padding: '0 12px 0px', gap: '4px', overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
        <div style={{ display: 'flex', flexShrink: 0, gap: '4px' }}>
          {TABS.map(tab => {
            const hasActiveTool = TOOL_DEFS.some(t2 => t2.category === tab.id && t2.id === activeTool);
            const isOpen = activeTab === tab.id;
            const [hov, setHov] = useState(false);
            return (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
                style={{
                  padding: '6px 16px', 
                  fontSize: '12px', 
                  fontWeight: isOpen ? 600 : 500,
                  borderRadius: t.radius.sm,
                  border: 'none', 
                  flexShrink: 0, 
                  cursor: 'pointer', 
                  transition: t.t.fast,
                  backgroundColor: isOpen ? t.colors.bgBase : hov ? t.colors.bgHover : 'transparent',
                  color: isOpen ? t.colors.textPrimary : hasActiveTool ? t.colors.accent : hov ? t.colors.textSecondary : t.colors.textMuted,
                  fontFamily: t.fonts.ui,
                }}>
                {tab.label}
              </button>
            );
          })}
        </div>
        
        {pageInfo && (
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', paddingTop: '6px', paddingRight: '12px', flexShrink: 0 }}>
            <span style={{ fontSize: '12px', color: t.colors.textMuted, fontFamily: t.fonts.mono }}>
              <span style={{ color: t.colors.textPrimary, fontWeight: 600 }}>{pageInfo.current}</span>
              {' / '}{pageInfo.total}
            </span>
          </div>
        )}
      </div>

    </div>
  );
}