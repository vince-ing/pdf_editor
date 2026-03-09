// LeftSidebar.tsx — w-12 icon rail + w-44 expandable drawer.
// Rail icons: Menu, Pages, Bookmarks, Comments, Layers, Code
// Drawer: page thumbnails (canvas-rendered), bookmarks, annotations, search.

import {
  Menu, Home, FileText, Star, MessageSquare, Layers, FileCode, ChevronRight, Search,
} from 'lucide-react';
import { useState, useEffect, useRef, useCallback } from 'react';
import * as pdfjsLib from 'pdfjs-dist';

// ── Types ─────────────────────────────────────────────────────────────────────

export type SidebarView = 'pages' | 'bookmarks' | 'annotations' | 'layers' | 'search' | null;

interface PageNode {
  id: string;
  page_number?: number;
  rotation?: number;
  children?: unknown[];
}

interface DocumentState {
  children?: PageNode[];
}

interface LeftSidebarProps {
  showThumbnails: boolean;
  onToggleThumbnails: () => void;
  // PDF functionality (optional — works as visual scaffold without them)
  pdfDoc?: pdfjsLib.PDFDocumentProxy | null;
  documentState?: DocumentState | null;
  activePage?: number;
  activeView?: SidebarView;
  onViewChange?: (v: SidebarView) => void;
  onPageClick?: (index: number) => void;
  onDocumentChanged?: () => Promise<void>;
}

// ── Thumbnail canvas ──────────────────────────────────────────────────────────
const Thumbnail = ({
  pdfDoc,
  pageNumber,
  rotation,
}: {
  pdfDoc: pdfjsLib.PDFDocumentProxy;
  pageNumber: number;
  rotation: number;
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const W = 136;

  useEffect(() => {
    let alive = true;
    let task: pdfjsLib.RenderTask | null = null;
    (async () => {
      try {
        const page = await pdfDoc.getPage(pageNumber + 1);
        if (!alive) return;
        const vp0 = page.getViewport({ scale: 1, rotation });
        const vp = page.getViewport({ scale: W / vp0.width, rotation });
        const cv = canvasRef.current;
        if (!cv) return;
        cv.width = vp.width;
        cv.height = vp.height;
        task = page.render({ canvasContext: cv.getContext('2d')!, viewport: vp });
        await task.promise;
      } catch (e: unknown) {
        if ((e as Error)?.name !== 'RenderingCancelledException') console.error(e);
      }
    })();
    return () => { alive = false; task?.cancel(); };
  }, [pdfDoc, pageNumber, rotation]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: W, display: 'block' }}
      className="rounded"
    />
  );
};

// ── Placeholder views ─────────────────────────────────────────────────────────
const BookmarksView = () => (
  <div className="p-4 text-center">
    <div className="text-2xl mb-2">🔖</div>
    <div className="text-xs text-gray-400 leading-relaxed">No bookmarks yet.<br />Use Insert › Bookmark.</div>
  </div>
);

const AnnotationsView = () => (
  <div className="p-4 text-center">
    <div className="text-2xl mb-2">✏️</div>
    <div className="text-xs text-gray-400">Annotations panel coming soon.</div>
  </div>
);

const LayersView = () => (
  <div className="p-4 text-center">
    <div className="text-2xl mb-2">⊞</div>
    <div className="text-xs text-gray-400">Layers panel coming soon.</div>
  </div>
);

const SearchView = () => {
  const [q, setQ] = useState('');
  return (
    <div className="p-2">
      <div className="flex items-center gap-1.5 bg-[#1e2327] border border-white/[0.06] rounded-md px-2 py-1.5 mb-2">
        <Search size={13} className="text-gray-500 flex-shrink-0" />
        <input
          value={q}
          onChange={e => setQ(e.target.value)}
          placeholder="Search document…"
          className="flex-1 bg-transparent text-white text-xs outline-none placeholder-gray-500"
        />
      </div>
      <div className="text-[11px] text-gray-500 text-center mt-3">Full-text search coming soon.</div>
    </div>
  );
};

// ── LeftSidebar ───────────────────────────────────────────────────────────────
export function LeftSidebar({
  showThumbnails,
  onToggleThumbnails,
  pdfDoc,
  documentState,
  activePage = 0,
  activeView,
  onViewChange,
  onPageClick,
  onDocumentChanged,
}: LeftSidebarProps) {
  const pages = documentState?.children ?? [];
  const [localActivePage, setLocalActivePage] = useState(0);
  const [dragSrc, setDragSrc] = useState<number | null>(null);
  const [dragOver, setDragOver] = useState<number | null>(null);
  const busyRef = useRef(false);

  const effectivePage = activePage ?? localActivePage;

  const handlePageClick = (i: number) => {
    setLocalActivePage(i);
    onPageClick?.(i);
  };

  const withBusy = useCallback(async (fn: () => Promise<void>) => {
    if (busyRef.current) return;
    busyRef.current = true;
    try { await fn(); }
    finally { busyRef.current = false; }
  }, []);

  // Rail icon definitions — add new panel views here
  const RAIL = [
    { id: null as SidebarView,           icon: Menu,         label: 'Menu',        onClick: onToggleThumbnails },
    { id: null as SidebarView,           icon: Home,         label: 'Home',        onClick: undefined },
    { id: 'pages' as SidebarView,        icon: FileText,     label: 'Pages',       onClick: undefined },
    { id: 'bookmarks' as SidebarView,    icon: Star,         label: 'Bookmarks',   onClick: undefined },
    { id: 'annotations' as SidebarView,  icon: MessageSquare,label: 'Annotations', onClick: undefined },
    { id: 'layers' as SidebarView,       icon: Layers,       label: 'Layers',      onClick: undefined },
    { id: 'search' as SidebarView,       icon: FileCode,     label: 'Search',      onClick: undefined },
  ];

  const handleRail = (id: SidebarView, onClick?: () => void) => {
    if (onClick) { onClick(); return; }
    if (!id) return;
    if (onViewChange) {
      onViewChange(activeView === id ? null : id);
    } else {
      // fallback: if no view controller, toggle thumbnails panel
      onToggleThumbnails();
    }
  };

  // Determine if drawer should show
  const drawerView = activeView ?? (showThumbnails ? 'pages' : null);

  return (
    <div className="h-full bg-[#25292d] border-r border-[#1e2327] flex flex-shrink-0">

      {/* ── Icon rail ── */}
      <div className="w-12 bg-[#1e2327] flex flex-col items-center py-4 gap-1 flex-shrink-0">
        {RAIL.map((item, i) => {
          const Icon = item.icon;
          const isActive = item.id !== null && item.id === drawerView;
          return (
            <button
              key={i}
              title={item.label}
              onClick={() => handleRail(item.id, item.onClick)}
              className={`w-10 h-10 flex items-center justify-center rounded transition-colors
                ${isActive
                  ? 'text-[#4a90e2] bg-[#2d3338]'
                  : 'text-gray-400 hover:text-white hover:bg-[#2d3338]'
                }`}
            >
              <Icon size={19} />
            </button>
          );
        })}
      </div>

      {/* ── Drawer ── */}
      {drawerView && (
        <div className="w-44 flex flex-col animate-slide-right overflow-hidden">
          {/* Drawer header */}
          <div className="h-14 flex items-center justify-between px-3 border-b border-[#1e2327] flex-shrink-0">
            <span className="text-sm text-white font-medium capitalize">
              {drawerView}
              {drawerView === 'pages' && pages.length > 0 && (
                <span className="ml-2 text-[11px] text-[#4a90e2] bg-[#4a90e2]/15 font-semibold font-mono px-1.5 py-0.5 rounded-full">
                  {pages.length}
                </span>
              )}
            </span>
            <button
              onClick={() => onViewChange ? onViewChange(null) : onToggleThumbnails()}
              className="text-gray-400 hover:text-white transition-colors"
            >
              <ChevronRight size={15} />
            </button>
          </div>

          {/* Drawer body */}
          <div className="flex-1 overflow-y-auto p-2.5 space-y-2">
            {drawerView === 'pages' && (
              <>
                {!pdfDoc && pages.length === 0 && (
                  // Fallback static thumbnails (reference style)
                  [1, 2, 3, 4].map(n => (
                    <div
                      key={n}
                      className={`relative cursor-pointer rounded-lg overflow-hidden ${n === 1 ? 'ring-2 ring-[#4a90e2]' : ''}`}
                    >
                      <div className="aspect-[8.5/11] bg-[#3d4449] rounded-lg flex items-center justify-center overflow-hidden">
                        {n <= 3 ? (
                          <div className="w-full h-full bg-white p-2">
                            <div className="space-y-1">
                              <div className="h-1 bg-gray-300 rounded w-3/4" />
                              <div className="h-1 bg-gray-300 rounded w-full" />
                              <div className="h-1 bg-gray-300 rounded w-2/3" />
                              <div className="h-0.5 bg-gray-200 rounded w-full mt-1" />
                              <div className="h-0.5 bg-gray-200 rounded w-5/6" />
                              <div className="h-0.5 bg-gray-200 rounded w-full" />
                            </div>
                          </div>
                        ) : (
                          <span className="text-gray-500 text-xs">Page {n}</span>
                        )}
                      </div>
                      <div className="absolute bottom-1 right-1 bg-[#1e2327] text-white text-xs px-1.5 py-0.5 rounded font-mono">
                        {n}
                      </div>
                    </div>
                  ))
                )}

                {pdfDoc && pages.map((page, i) => (
                  <div
                    key={page.id}
                    draggable
                    onDragStart={e => { setDragSrc(i); e.dataTransfer.effectAllowed = 'move'; }}
                    onDragOver={e => { e.preventDefault(); if (i !== dragSrc) setDragOver(i); }}
                    onDragEnd={() => { setDragSrc(null); setDragOver(null); }}
                    onDrop={async e => {
                      e.preventDefault();
                      const src = dragSrc;
                      setDragSrc(null); setDragOver(null);
                      if (src !== null && src !== i) {
                        await withBusy(async () => {
                          const { engineApi } = await import('../api/client');
                          await engineApi.movePage(pages[src].id, i);
                          await onDocumentChanged?.();
                        });
                      }
                    }}
                    onClick={() => handlePageClick(i)}
                    className={`relative cursor-pointer rounded-lg overflow-hidden transition-all
                      ${effectivePage === i ? 'ring-2 ring-[#4a90e2]' : 'hover:ring-1 hover:ring-white/20'}
                      ${dragOver === i && dragSrc !== i ? 'border-2 border-amber-400' : ''}
                      ${dragSrc === i ? 'opacity-40' : ''}`}
                  >
                    <div className="bg-white rounded overflow-hidden">
                      <Thumbnail
                        pdfDoc={pdfDoc}
                        pageNumber={page.page_number ?? i}
                        rotation={page.rotation ?? 0}
                      />
                    </div>
                    <div className="absolute bottom-1 right-1 bg-[#1e2327] text-white text-[10px] px-1.5 py-0.5 rounded font-mono font-semibold">
                      {i + 1}
                    </div>
                    {(page.rotation ?? 0) !== 0 && (
                      <div className="absolute bottom-1 left-1 bg-[#4a90e2] text-white text-[9px] px-1 py-0.5 rounded font-mono font-bold">
                        {page.rotation}°
                      </div>
                    )}
                  </div>
                ))}
              </>
            )}

            {drawerView === 'bookmarks'   && <BookmarksView />}
            {drawerView === 'annotations' && <AnnotationsView />}
            {drawerView === 'layers'      && <LayersView />}
            {drawerView === 'search'      && <SearchView />}
          </div>
        </div>
      )}
    </div>
  );
}