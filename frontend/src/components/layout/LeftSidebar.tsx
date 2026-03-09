// components/layout/LeftSidebar.tsx
import {
  FileText, Bookmark, MessageSquare, Layers, Search, ChevronRight, RotateCw, GripVertical,
} from 'lucide-react';
import { useState, useEffect, useRef, useCallback } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import { useTheme } from '../../theme';

export type SidebarView = 'pages' | 'bookmarks' | 'annotations' | 'layers' | 'search' | null;

interface PageNode { id: string; page_number?: number; rotation?: number; children?: unknown[]; }
interface DocumentState { children?: PageNode[]; }
interface LeftSidebarProps {
  showThumbnails: boolean; onToggleThumbnails: () => void;
  pdfDoc?: pdfjsLib.PDFDocumentProxy | null; documentState?: DocumentState | null;
  activePage?: number; activeView?: SidebarView; onViewChange?: (v: SidebarView) => void;
  onPageClick?: (index: number) => void; onDocumentChanged?: () => Promise<void>;
}

const Thumbnail = ({ pdfDoc, pageNumber, rotation }: {
  pdfDoc: pdfjsLib.PDFDocumentProxy; pageNumber: number; rotation: number;
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const W = 100;
  useEffect(() => {
    let alive = true; let task: pdfjsLib.RenderTask | null = null;
    (async () => {
      try {
        const page = await pdfDoc.getPage(pageNumber + 1);
        if (!alive) return;
        const vp0 = page.getViewport({ scale: 1, rotation });
        const vp = page.getViewport({ scale: W / vp0.width, rotation });
        const cv = canvasRef.current; if (!cv) return;
        cv.width = vp.width; cv.height = vp.height;
        task = page.render({ canvasContext: cv.getContext('2d')!, viewport: vp });
        await task.promise;
      } catch (e: unknown) { if ((e as Error)?.name !== 'RenderingCancelledException') console.error(e); }
    })();
    return () => { alive = false; task?.cancel(); };
  }, [pdfDoc, pageNumber, rotation]);
  return <canvas ref={canvasRef} style={{ width: W, display: 'block', borderRadius: 3 }} />;
};

const VIEW_ITEMS: Array<{ id: SidebarView; icon: React.ComponentType<{ size?: number }>; label: string }> = [
  { id: 'pages', icon: FileText, label: 'Pages' },
  { id: 'bookmarks', icon: Bookmark, label: 'Bookmarks' },
  { id: 'annotations', icon: MessageSquare, label: 'Annotations' },
  { id: 'layers', icon: Layers, label: 'Layers' },
  { id: 'search', icon: Search, label: 'Search' },
];

export function LeftSidebar({
  showThumbnails, onToggleThumbnails, pdfDoc, documentState,
  activePage = 0, activeView, onViewChange, onPageClick, onDocumentChanged,
}: LeftSidebarProps) {
  const { theme: t } = useTheme();
  const pages = documentState?.children ?? [];
  const [localActivePage, setLocalActivePage] = useState(0);
  const [dragSrc, setDragSrc] = useState<number | null>(null);
  const [insertBefore, setInsertBefore] = useState<number | null>(null);
  const busyRef = useRef(false);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const thumbRefs = useRef<(HTMLDivElement | null)[]>([]);
  const effectivePage = activePage ?? localActivePage;

  useEffect(() => {
    const el = thumbRefs.current[effectivePage];
    const container = scrollContainerRef.current;
    if (!el || !container) return;
    const elTop = el.offsetTop, elBottom = elTop + el.offsetHeight;
    const contTop = container.scrollTop, contBottom = contTop + container.clientHeight;
    if (elTop < contTop || elBottom > contBottom) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [effectivePage]);

  const withBusy = useCallback(async (fn: () => Promise<void>) => {
    if (busyRef.current) return;
    busyRef.current = true;
    try { await fn(); } finally { busyRef.current = false; }
  }, []);

  const drawerView = activeView ?? (showThumbnails ? 'pages' : null);
  const drawerLabel = VIEW_ITEMS.find(x => x.id === drawerView)?.label ?? '';

  return (
    <div style={{ height: '100%', display: 'flex', flexShrink: 0, backgroundColor: t.colors.bgRaised, borderRight: `1px solid ${t.colors.bgBase}` }}>

      {/* Icon rail */}
      <div style={{ width: 48, backgroundColor: t.colors.bgBase, display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '12px 0', gap: 4, flexShrink: 0 }}>
        {VIEW_ITEMS.map(item => {
          const Icon = item.icon;
          const isActive = item.id === drawerView;
          const [hov, setHov] = useState(false);
          return (
            <button key={item.id} title={item.label}
              onClick={() => onViewChange ? onViewChange(isActive ? null : item.id) : onToggleThumbnails()}
              onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
              style={{
                width: 40, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center',
                borderRadius: t.radius.md, border: 'none', cursor: 'pointer', transition: t.t.fast,
                backgroundColor: isActive || hov ? t.colors.bgRaised : 'transparent',
                color: isActive ? t.colors.accent : hov ? t.colors.textPrimary : t.colors.textMuted,
              }}>
              <Icon size={18} />
            </button>
          );
        })}
      </div>

      {/* Drawer */}
      {drawerView && (
        <div style={{ width: 176, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Header */}
          <div style={{ height: 40, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 12px', borderBottom: `1px solid ${t.colors.bgBase}`, flexShrink: 0 }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: t.colors.textSecondary, textTransform: 'uppercase', letterSpacing: '0.06em', display: 'flex', alignItems: 'center', gap: 6 }}>
              {drawerLabel}
              {drawerView === 'pages' && pages.length > 0 && (
                <span style={{ fontSize: '10px', color: t.colors.accent, backgroundColor: `${t.colors.accent}20`, fontWeight: 700, fontFamily: t.fonts.mono, padding: '1px 6px', borderRadius: t.radius.pill }}>
                  {pages.length}
                </span>
              )}
            </span>
            <button onClick={() => onViewChange ? onViewChange(null) : onToggleThumbnails()}
              style={{ color: t.colors.textMuted, background: 'none', border: 'none', cursor: 'pointer', display: 'flex' }}
              onMouseEnter={e => (e.currentTarget.style.color = t.colors.textPrimary)}
              onMouseLeave={e => (e.currentTarget.style.color = t.colors.textMuted)}>
              <ChevronRight size={14} />
            </button>
          </div>

          {/* Scroll area */}
          <div ref={scrollContainerRef} style={{ flex: 1, overflowY: 'auto', padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {drawerView === 'pages' && (<>
              {!pdfDoc && pages.length === 0 && [1,2,3,4].map(n => (
                <div key={n} style={{ position: 'relative', borderRadius: t.radius.md, overflow: 'hidden', border: n === 1 ? `2px solid ${t.colors.accent}` : 'none' }}>
                  <div style={{ aspectRatio: '8.5/11', backgroundColor: t.colors.bgRaised, borderRadius: t.radius.md, padding: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {[0.75, 1, 0.66].map((w, i) => <div key={i} style={{ height: 6, backgroundColor: t.colors.bgHover, borderRadius: 3, width: `${w * 100}%`, animation: 'pulse 2s infinite' }} />)}
                  </div>
                  <div style={{ position: 'absolute', bottom: 4, right: 6, backgroundColor: t.colors.bgBase, color: t.colors.textMuted, fontSize: 9, padding: '1px 6px', borderRadius: t.radius.xs, fontFamily: t.fonts.mono }}>{n}</div>
                </div>
              ))}
              {pdfDoc && pages.map((page, i) => (
                <div key={page.id} ref={el => { thumbRefs.current[i] = el; }} draggable
                  onDragStart={e => { setDragSrc(i); e.dataTransfer.effectAllowed = 'move'; }}
                  onDragOver={e => {
                    e.preventDefault(); if (dragSrc === null || i === dragSrc) return;
                    const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
                    setInsertBefore(e.clientY < rect.top + rect.height / 2 ? i : i + 1);
                  }}
                  onDragEnd={() => { setDragSrc(null); setInsertBefore(null); }}
                  onDrop={async e => {
                    e.preventDefault(); const src = dragSrc;
                    setDragSrc(null); setInsertBefore(null);
                    if (src !== null && src !== i) await withBusy(async () => {
                      const { engineApi } = await import('../../api/client');
                      await engineApi.movePage(pages[src].id, i);
                      await onDocumentChanged?.();
                    });
                  }}
                  onClick={() => { setLocalActivePage(i); onPageClick?.(i); }}
                  style={{ position: 'relative', cursor: 'pointer', borderRadius: t.radius.md, opacity: dragSrc === i ? 0.4 : 1, transition: t.t.fast }}>

                  {insertBefore === i && dragSrc !== i && (
                    <div style={{ position: 'absolute', top: -5, left: 8, right: 8, height: 3, backgroundColor: t.colors.accent, borderRadius: t.radius.pill, zIndex: 20, pointerEvents: 'none' }} />
                  )}
                  {insertBefore === i + 1 && dragSrc !== i && (
                    <div style={{ position: 'absolute', bottom: -5, left: 8, right: 8, height: 3, backgroundColor: t.colors.accent, borderRadius: t.radius.pill, zIndex: 20, pointerEvents: 'none' }} />
                  )}

                  <div style={{ padding: '12px 12px 4px', display: 'flex', justifyContent: 'center' }}>
                    <div style={{ backgroundColor: 'white', borderRadius: 4, overflow: 'hidden', boxShadow: t.shadow.panel, outline: effectivePage === i ? `2px solid ${t.colors.accent}` : 'none' }}>
                      <Thumbnail pdfDoc={pdfDoc} pageNumber={page.page_number ?? i} rotation={page.rotation ?? 0} />
                    </div>
                  </div>

                  <div style={{ paddingBottom: 8, textAlign: 'center' }}>
                    <span style={{ fontSize: '11px', fontFamily: t.fonts.mono, fontWeight: 600, color: effectivePage === i ? t.colors.accent : t.colors.textMuted }}>{i + 1}</span>
                  </div>

                  {(page.rotation ?? 0) !== 0 && (
                    <div style={{ position: 'absolute', top: 8, right: 8, backgroundColor: t.colors.accent, color: '#fff', fontSize: 9, padding: '1px 4px', borderRadius: t.radius.xs, fontFamily: t.fonts.mono, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 2 }}>
                      <RotateCw size={8} />{page.rotation}°
                    </div>
                  )}
                </div>
              ))}
            </>)}

            {drawerView === 'bookmarks' && <PlaceholderView icon={Bookmark} title="No bookmarks yet" hint="Use Insert › Bookmark to add one." t={t} />}
            {drawerView === 'annotations' && <PlaceholderView icon={MessageSquare} title="Annotations" hint="Annotations list coming soon." t={t} />}
            {drawerView === 'layers' && <PlaceholderView icon={Layers} title="Layers" hint="Layers panel coming soon." t={t} />}
            {drawerView === 'search' && <SearchView t={t} />}
          </div>
        </div>
      )}
    </div>
  );
}

const PlaceholderView = ({ icon: Icon, title, hint, t }: { icon: any; title: string; hint: string; t: any }) => (
  <div style={{ padding: 24, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, textAlign: 'center' }}>
    <div style={{ width: 40, height: 40, backgroundColor: t.colors.bgBase, borderRadius: t.radius.md, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <Icon size={18} style={{ color: t.colors.textMuted }} />
    </div>
    <div>
      <div style={{ fontSize: '12px', fontWeight: 500, color: t.colors.textSecondary, marginBottom: 4 }}>{title}</div>
      <div style={{ fontSize: '11px', color: t.colors.textMuted, lineHeight: 1.5 }}>{hint}</div>
    </div>
  </div>
);

const SearchView = ({ t }: { t: any }) => {
  const [q, setQ] = useState('');
  return (
    <div style={{ padding: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, backgroundColor: t.colors.bgBase, border: `1px solid ${t.colors.border}`, borderRadius: t.radius.md, padding: '6px 8px', marginBottom: 8 }}>
        <Search size={13} style={{ color: t.colors.textMuted, flexShrink: 0 }} />
        <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search document…"
          style={{ flex: 1, background: 'transparent', color: t.colors.textPrimary, fontSize: '12px', outline: 'none', border: 'none', fontFamily: t.fonts.ui }} />
      </div>
      <div style={{ fontSize: '11px', color: t.colors.textMuted, textAlign: 'center', marginTop: 12 }}>Full-text search coming soon.</div>
    </div>
  );
};