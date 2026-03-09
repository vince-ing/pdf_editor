// components/layout/LeftSidebar.tsx — Icon rail + expandable drawer.
// Consolidates LeftPanel.jsx, Sidebar.jsx, LeftSidebar.tsx into one file.
// All icons: Lucide React. No emoji.

import {
  Menu, Home, FileText, Bookmark, MessageSquare,
  Layers, Search, ChevronRight, RotateCw, X, GripVertical,
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

  return <canvas ref={canvasRef} style={{ width: W, display: 'block' }} className="rounded" />;
};

// ── Placeholder panel views ───────────────────────────────────────────────────

const PlaceholderView = ({
  icon: Icon,
  title,
  hint,
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  title: string;
  hint: string;
}) => (
  <div className="p-6 flex flex-col items-center gap-3 text-center">
    <div className="w-10 h-10 bg-[#1e2327] rounded-lg flex items-center justify-center">
      <Icon size={18} className="text-gray-500" />
    </div>
    <div>
      <div className="text-xs font-medium text-gray-400 mb-1">{title}</div>
      <div className="text-[11px] text-gray-600 leading-relaxed">{hint}</div>
    </div>
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
      <div className="text-[11px] text-gray-600 text-center mt-3">Full-text search coming soon.</div>
    </div>
  );
};

// ── Rail icon definitions ─────────────────────────────────────────────────────

const RAIL_ITEMS: Array<{
  id: SidebarView | '__menu' | '__home';
  icon: React.ComponentType<{ size?: number }>;
  label: string;
}> = [
  { id: '__menu',      icon: Menu,         label: 'Toggle Sidebar' },
  { id: '__home',      icon: Home,         label: 'Home'           },
  { id: 'pages',       icon: FileText,     label: 'Pages'          },
  { id: 'bookmarks',   icon: Bookmark,     label: 'Bookmarks'      },
  { id: 'annotations', icon: MessageSquare,label: 'Annotations'    },
  { id: 'layers',      icon: Layers,       label: 'Layers'         },
  { id: 'search',      icon: Search,       label: 'Search'         },
];

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

  const handleRail = (id: string) => {
    if (id === '__menu') { onToggleThumbnails(); return; }
    if (id === '__home') return;
    const viewId = id as SidebarView;
    onViewChange ? onViewChange(activeView === viewId ? null : viewId) : onToggleThumbnails();
  };

  const drawerView = activeView ?? (showThumbnails ? 'pages' : null);

  const drawerLabel = RAIL_ITEMS.find(x => x.id === drawerView)?.label ?? '';

  return (
    <div className="h-full bg-[#25292d] border-r border-[#1e2327] flex flex-shrink-0">

      {/* ── Icon rail ── */}
      <div className="w-12 bg-[#1e2327] flex flex-col items-center py-4 gap-1 flex-shrink-0">
        {RAIL_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = item.id !== '__menu' && item.id !== '__home' && item.id === drawerView;
          return (
            <button
              key={item.id}
              title={item.label}
              onClick={() => handleRail(item.id)}
              className={`w-10 h-10 flex items-center justify-center rounded transition-colors
                ${isActive
                  ? 'text-[#4a90e2] bg-[#2d3338]'
                  : 'text-gray-500 hover:text-white hover:bg-[#2d3338]'
                }`}
            >
              <Icon size={18} />
            </button>
          );
        })}
      </div>

      {/* ── Drawer ── */}
      {drawerView && (
        <div className="w-44 flex flex-col animate-slide-right overflow-hidden">

          {/* Drawer header */}
          <div className="h-10 flex items-center justify-between px-3 border-b border-[#1e2327] flex-shrink-0">
            <span className="text-xs font-semibold text-gray-300 uppercase tracking-wider">
              {drawerLabel}
              {drawerView === 'pages' && pages.length > 0 && (
                <span className="ml-2 text-[10px] text-[#4a90e2] bg-[#4a90e2]/15 font-bold font-mono px-1.5 py-0.5 rounded-full">
                  {pages.length}
                </span>
              )}
            </span>
            <button
              onClick={() => onViewChange ? onViewChange(null) : onToggleThumbnails()}
              className="text-gray-500 hover:text-white transition-colors"
            >
              <ChevronRight size={14} />
            </button>
          </div>

          {/* Drawer body */}
          <div className="flex-1 overflow-y-auto p-2 space-y-2">

            {/* Pages view */}
            {drawerView === 'pages' && (
              <>
                {!pdfDoc && pages.length === 0 && (
                  // Skeleton placeholders before any document is loaded
                  [1, 2, 3, 4].map(n => (
                    <div key={n} className={`relative cursor-default rounded-lg overflow-hidden ${n === 1 ? 'ring-2 ring-[#4a90e2]' : ''}`}>
                      <div className="aspect-[8.5/11] bg-[#2d3338] rounded-lg flex items-center justify-center">
                        <div className="w-full h-full p-3 space-y-1.5">
                          <div className="h-1.5 bg-[#3d4449] rounded w-3/4 animate-pulse" />
                          <div className="h-1.5 bg-[#3d4449] rounded w-full animate-pulse" />
                          <div className="h-1.5 bg-[#3d4449] rounded w-2/3 animate-pulse" />
                          <div className="h-px bg-[#3d4449]/50 rounded w-full mt-2" />
                          <div className="h-1 bg-[#3d4449] rounded w-5/6 animate-pulse" />
                          <div className="h-1 bg-[#3d4449] rounded w-full animate-pulse" />
                        </div>
                      </div>
                      <div className="absolute bottom-1 right-1.5 bg-[#1e2327] text-gray-500 text-[9px] px-1.5 py-0.5 rounded font-mono">
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
                          const { engineApi } = await import('../../api/client');
                          await engineApi.movePage(pages[src].id, i);
                          await onDocumentChanged?.();
                        });
                      }
                    }}
                    onClick={() => handlePageClick(i)}
                    className={`group relative cursor-pointer rounded-lg overflow-hidden transition-all
                      ${effectivePage === i ? 'ring-2 ring-[#4a90e2]' : 'hover:ring-1 hover:ring-white/20'}
                      ${dragOver === i && dragSrc !== i ? 'ring-2 ring-amber-400' : ''}
                      ${dragSrc === i ? 'opacity-40' : ''}`}
                  >
                    {/* Drag handle indicator */}
                    <div className="absolute top-1 left-1 opacity-0 group-hover:opacity-100 transition-opacity z-10 text-white/40">
                      <GripVertical size={12} />
                    </div>

                    <div className="bg-white rounded overflow-hidden">
                      <Thumbnail
                        pdfDoc={pdfDoc}
                        pageNumber={page.page_number ?? i}
                        rotation={page.rotation ?? 0}
                      />
                    </div>

                    {/* Page number badge */}
                    <div className="absolute bottom-1 right-1 bg-[#1e2327] text-white text-[9px] px-1.5 py-0.5 rounded font-mono font-semibold">
                      {i + 1}
                    </div>

                    {/* Rotation badge */}
                    {(page.rotation ?? 0) !== 0 && (
                      <div className="absolute bottom-1 left-1 bg-[#4a90e2] text-white text-[9px] px-1 py-0.5 rounded font-mono font-bold flex items-center gap-0.5">
                        <RotateCw size={8} />
                        {page.rotation}°
                      </div>
                    )}
                  </div>
                ))}
              </>
            )}

            {drawerView === 'bookmarks' && (
              <PlaceholderView
                icon={Bookmark}
                title="No bookmarks yet"
                hint="Use Insert › Bookmark to add one."
              />
            )}
            {drawerView === 'annotations' && (
              <PlaceholderView
                icon={MessageSquare}
                title="Annotations"
                hint="Annotations list coming soon."
              />
            )}
            {drawerView === 'layers' && (
              <PlaceholderView
                icon={Layers}
                title="Layers"
                hint="Layers panel coming soon."
              />
            )}
            {drawerView === 'search' && <SearchView />}
          </div>
        </div>
      )}
    </div>
  );
}