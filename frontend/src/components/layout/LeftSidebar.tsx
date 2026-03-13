// components/layout/LeftSidebar.tsx
import {
  FileText, Bookmark, MessageSquare, Layers, Search, ChevronRight, RotateCw,
  ChevronDown, ChevronUp, Loader2,
} from 'lucide-react';
import { useState, useEffect, useRef, useCallback } from 'react';import * as pdfjsLib from 'pdfjs-dist';
import { useTheme } from '../../theme';
import type { SearchMatch, PageMatchMap } from '../../hooks/useSearchState';

export type SidebarView = 'pages' | 'bookmarks' | 'annotations' | 'layers' | 'search' | null;

interface PageNode { id: string; page_number?: number; rotation?: number; children?: unknown[]; }
interface DocumentState { children?: PageNode[]; }

export interface SearchProps {
  query:          string;
  onQueryChange:  (q: string) => void;
  matchCount:     number;
  currentIndex:   number;
  isSearching:    boolean;
  pageMatchMap:   PageMatchMap;
  matches:        SearchMatch[];
  onNext:         () => void;
  onPrev:         () => void;
  goToMatch:      (index: number) => void;
  inputRef?:      React.RefObject<HTMLInputElement>;
}

interface LeftSidebarProps {
  showThumbnails: boolean; onToggleThumbnails: () => void;
  pdfDoc?: pdfjsLib.PDFDocumentProxy | null; documentState?: DocumentState | null;
  activePage?: number; activeView?: SidebarView; onViewChange?: (v: SidebarView) => void;
  onPageClick?: (index: number) => void; onDocumentChanged?: () => Promise<void>;
  search?: SearchProps;
  sessionId?: string;
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
  { id: 'pages',       icon: FileText,      label: 'Pages'       },
  { id: 'bookmarks',   icon: Bookmark,      label: 'Bookmarks'   },
  { id: 'annotations', icon: MessageSquare, label: 'Annotations' },
  { id: 'layers',      icon: Layers,        label: 'Layers'      },
  { id: 'search',      icon: Search,        label: 'Search'      },
];

export function LeftSidebar({
  showThumbnails, onToggleThumbnails, pdfDoc, documentState,
  activePage = 0, activeView, onViewChange, onPageClick, onDocumentChanged,
  search, sessionId,
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
        <div style={{ width: 216, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Header */}
          <div style={{ height: 40, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 12px', borderBottom: `1px solid ${t.colors.bgBase}`, flexShrink: 0 }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: t.colors.textSecondary, textTransform: 'uppercase', letterSpacing: '0.06em', display: 'flex', alignItems: 'center', gap: 6 }}>
              {drawerLabel}
              {drawerView === 'pages' && pages.length > 0 && (
                <span style={{ fontSize: '10px', color: t.colors.accent, backgroundColor: `${t.colors.accent}20`, fontWeight: 700, fontFamily: t.fonts.mono, padding: '1px 6px', borderRadius: t.radius.pill }}>
                  {pages.length}
                </span>
              )}
              {drawerView === 'search' && search && search.matchCount > 0 && (
                <span style={{ fontSize: '10px', color: t.colors.accent, backgroundColor: `${t.colors.accent}20`, fontWeight: 700, fontFamily: t.fonts.mono, padding: '1px 6px', borderRadius: t.radius.pill }}>
                  {search.matchCount}
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
          <div ref={scrollContainerRef} className="scrollbar-thumb-only" style={{ flex: 1, overflowY: 'auto', padding: drawerView === 'search' ? '0' : '8px 12px', display: 'flex', flexDirection: 'column', gap: drawerView === 'search' ? 0 : 8 }}>
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
                      await engineApi.movePage(pages[src].id, i, sessionId ?? '');
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

            {drawerView === 'bookmarks'   && <PlaceholderView icon={Bookmark}      title="No bookmarks yet"   hint="Use Insert › Bookmark to add one." t={t} />}
            {drawerView === 'annotations' && <PlaceholderView icon={MessageSquare} title="Annotations"        hint="Annotations list coming soon." t={t} />}
            {drawerView === 'layers'      && <PlaceholderView icon={Layers}        title="Layers"             hint="Layers panel coming soon." t={t} />}
            {drawerView === 'search'      && <SearchPanel search={search} pages={documentState?.children ?? []} t={t} />}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Placeholder ───────────────────────────────────────────────────────────────

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

// ── Real search panel ─────────────────────────────────────────────────────────

function ContextSnippet({ before, term, after, t, isCurrent }: {
  before: string; term: string; after: string; t: any; isCurrent: boolean;
}) {
  // Normalize whitespace
  const b = before.replace(/\s+/g, ' ').trimStart();
  const a = after.replace(/\s+/g, ' ').trimEnd();

  // Keep a balanced window: last N chars of before, first N of after
  const MAX_SIDE = 22;
  const trimB = b.length > MAX_SIDE ? '…' + b.slice(b.length - MAX_SIDE) : (b.length ? b : '');
  const trimA = a.length > MAX_SIDE ? a.slice(0, MAX_SIDE) + '…' : (a.length ? a : '');

  return (
    <span style={{
      fontSize: '10.5px',
      fontFamily: t.fonts.ui,
      color: isCurrent ? t.colors.textSecondary : t.colors.textMuted,
      lineHeight: 1.55,
      display: 'block',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap',
      letterSpacing: '0.01em',
    }}>
      {trimB && <span>{trimB}</span>}
      <span style={{
        fontWeight: 700,
        color: isCurrent ? t.colors.textPrimary : t.colors.textSecondary,
      }}>{term}</span>
      {trimA && <span>{trimA}</span>}
    </span>
  );
}

function SearchPanel({
  search, pages, t,
}: {
  search:    SearchProps | undefined;
  pages:     PageNode[];
  t:         any;
}) {
  // Group matches by page for display — preserving per-match global index
  const byPage: { pageIndex: number; pageLabel: number; entries: { match: SearchMatch; globalIndex: number }[] }[] = [];
  if (search?.matches) {
    search.matches.forEach((match, gi) => {
      let group = byPage.find(g => g.pageIndex === match.pageIndex);
      if (!group) {
        group = { pageIndex: match.pageIndex, pageLabel: match.pageIndex + 1, entries: [] };
        byPage.push(group);
      }
      group.entries.push({ match, globalIndex: gi });
    });
  }

  const hasQuery   = (search?.query ?? '').trim().length > 0;
  const noResults  = hasQuery && !search?.isSearching && search?.matchCount === 0;
  const hasResults = hasQuery && (search?.matchCount ?? 0) > 0;

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!search) return;
    if (e.key === 'Enter') { e.preventDefault(); e.shiftKey ? search.onPrev() : search.onNext(); }
  };

  // Scroll the active match row into view inside the results list
  const activeRowRef = useRef<HTMLButtonElement | null>(null);
  const resultsRef   = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const row = activeRowRef.current;
    const container = resultsRef.current;
    if (!row || !container) return;
    const rowTop    = row.offsetTop;
    const rowBottom = rowTop + row.offsetHeight;
    const contTop   = container.scrollTop;
    const contBottom = contTop + container.clientHeight;
    if (rowTop < contTop || rowBottom > contBottom) {
      row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [search?.currentIndex]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* ── Input row ── */}
      <div style={{ padding: '10px 10px 8px', borderBottom: `1px solid ${t.colors.bgBase}`, flexShrink: 0 }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          backgroundColor: t.colors.bgBase,
          border: `1px solid ${noResults ? t.colors.danger + '80' : t.colors.border}`,
          borderRadius: t.radius.md, padding: '5px 8px',
          transition: 'border-color 0.15s',
        }}>
          {search?.isSearching
            ? <Loader2 size={13} style={{ color: t.colors.accent, flexShrink: 0, animation: 'spin 1s linear infinite' }} />
            : <Search size={13} style={{ color: noResults ? t.colors.danger : t.colors.textMuted, flexShrink: 0 }} />
          }
          <input
            ref={search?.inputRef}
            value={search?.query ?? ''}
            onChange={e => search?.onQueryChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search document…"
            spellCheck={false}
            style={{
              flex: 1, background: 'transparent', border: 'none', outline: 'none',
              fontSize: '12px', fontFamily: t.fonts.ui,
              color: noResults ? t.colors.danger : t.colors.textPrimary,
              caretColor: t.colors.accent, minWidth: 0,
            }}
          />
          {hasResults && (
            <>
              <button onClick={search?.onPrev} title="Previous (Shift+Enter)"
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 20, height: 20, border: 'none', borderRadius: t.radius.sm, cursor: 'pointer', backgroundColor: 'transparent', color: t.colors.textMuted, flexShrink: 0 }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.backgroundColor = t.colors.bgHover; (e.currentTarget as HTMLElement).style.color = t.colors.textPrimary; }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'; (e.currentTarget as HTMLElement).style.color = t.colors.textMuted; }}>
                <ChevronUp size={12} />
              </button>
              <button onClick={search?.onNext} title="Next (Enter)"
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 20, height: 20, border: 'none', borderRadius: t.radius.sm, cursor: 'pointer', backgroundColor: 'transparent', color: t.colors.textMuted, flexShrink: 0 }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.backgroundColor = t.colors.bgHover; (e.currentTarget as HTMLElement).style.color = t.colors.textPrimary; }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'; (e.currentTarget as HTMLElement).style.color = t.colors.textMuted; }}>
                <ChevronDown size={12} />
              </button>
            </>
          )}
        </div>

        {/* Status line */}
        <div style={{ marginTop: 6, fontSize: '11px', fontFamily: t.fonts.mono, color: noResults ? t.colors.danger : t.colors.textMuted, minHeight: 16 }}>
          {search?.isSearching && 'Searching…'}
          {!search?.isSearching && noResults && 'No results found'}
          {!search?.isSearching && hasResults && `${(search?.currentIndex ?? 0) + 1} of ${search?.matchCount} match${search?.matchCount !== 1 ? 'es' : ''}`}
        </div>
      </div>

      {/* ── Results list ── */}
      <div ref={resultsRef} style={{ flex: 1, overflowY: 'auto' }}>
        {!hasQuery && (
          <div style={{ padding: '24px 12px', textAlign: 'center' }}>
            <div style={{ width: 36, height: 36, backgroundColor: t.colors.bgBase, borderRadius: t.radius.md, display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 10px' }}>
              <Search size={16} style={{ color: t.colors.textMuted }} />
            </div>
            <div style={{ fontSize: '11px', color: t.colors.textMuted, lineHeight: 1.6 }}>
              Type to search all pages.<br />
              <span style={{ color: t.colors.textDisabled }}>Enter / Shift+Enter to step</span>
            </div>
          </div>
        )}

        {hasResults && byPage.map(group => (
          <div key={group.pageIndex}>
            {/* Page group header */}
            <div style={{
              padding: '4px 10px', fontSize: '10px', fontWeight: 700, letterSpacing: '0.06em',
              textTransform: 'uppercase', color: t.colors.textMuted,
              backgroundColor: t.colors.bgBase,
              borderTop: `1px solid ${t.colors.border}`,
              borderBottom: `1px solid ${t.colors.border}`,
              fontFamily: t.fonts.mono,
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <span>Page {group.pageLabel}</span>
              <span style={{ color: t.colors.accent }}>{group.entries.length}</span>
            </div>

            {/* Match rows */}
            {group.entries.map(({ match, globalIndex }, localIdx) => {
              const isCurrent = globalIndex === (search?.currentIndex ?? -1);
              return (
                <button
                  key={globalIndex}
                  ref={isCurrent ? (el => { (activeRowRef as any).current = el; }) : undefined}
                  onClick={() => search?.goToMatch(globalIndex)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 7,
                    width: '100%', textAlign: 'left', border: 'none',
                    cursor: 'pointer', padding: '5px 10px 5px 10px',
                    backgroundColor: isCurrent ? `${t.colors.accent}18` : 'transparent',
                    borderLeft: isCurrent ? `2px solid ${t.colors.accent}` : '2px solid transparent',
                    transition: 'background 0.1s',
                  }}
                  onMouseEnter={e => { if (!isCurrent) (e.currentTarget as HTMLElement).style.backgroundColor = t.colors.bgHover; }}
                  onMouseLeave={e => { if (!isCurrent) (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'; }}
                >
                  {/* Plain index number */}
                  <span style={{
                    flexShrink: 0,
                    fontSize: '9px', fontFamily: t.fonts.mono,
                    color: isCurrent ? t.colors.accent : t.colors.textDisabled,
                    minWidth: 14, textAlign: 'right',
                    lineHeight: 1,
                  }}>
                    {globalIndex + 1}
                  </span>
                  {/* Context */}
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <ContextSnippet
                      before={match.contextBefore}
                      term={match.text}
                      after={match.contextAfter}
                      t={t}
                      isCurrent={isCurrent}
                    />
                  </div>
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}