// frontend/src/hooks/useKeyboardShortcuts.ts
import { useEffect } from 'react';
import type { SidebarView } from '../components/layout/LeftSidebar';
import type { ToolId } from '../constants/tools';

const SCROLL_STEP = 120; // px per arrow key press

// Smooth scroll implementation — accumulates velocity on repeated keydown
// and decelerates with requestAnimationFrame for a fluid feel.
const scrollState = new WeakMap<HTMLElement, { velocity: number; raf: number }>();

function smoothScroll(container: HTMLElement, delta: number) {
  let state = scrollState.get(container);
  if (!state) {
    state = { velocity: 0, raf: 0 };
    scrollState.set(container, state);
  }

  // Add to velocity (capped so holding the key doesn't accelerate forever)
  state.velocity = Math.max(-600, Math.min(600, state.velocity + delta));

  // Cancel any existing animation frame before starting a new one
  if (state.raf) cancelAnimationFrame(state.raf);

  const animate = () => {
    if (!state || Math.abs(state.velocity) < 0.5) {
      if (state) state.velocity = 0;
      return;
    }
    container.scrollTop += state.velocity * 0.016; // ~60fps frame step
    state.velocity *= 0.88;                         // friction / deceleration
    state.raf = requestAnimationFrame(animate);
  };

  state.raf = requestAnimationFrame(animate);
}

interface UseKeyboardShortcutsArgs {
  handleUndo:        () => void;
  handleRedo:        () => void;
  handleExportPdf:   () => void;
  openFileDialog:    () => void;
  zoomIn:            () => void;
  zoomOut:           () => void;
  setSidebarView:    (v: SidebarView) => void;
  setShowThumbnails: (fn: (v: boolean) => boolean) => void;
  openSearch:        () => void;
  activeTool:        ToolId;
  canvasScrollRef:   React.RefObject<HTMLDivElement | null>;
}

export function useKeyboardShortcuts({
  handleUndo,
  handleRedo,
  handleExportPdf,
  openFileDialog,
  zoomIn,
  zoomOut,
  setSidebarView,
  setShowThumbnails,
  openSearch,
  activeTool,
  canvasScrollRef,
}: UseKeyboardShortcutsArgs) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // ── Arrow key scrolling (hand tool only) ──────────────────────────────
      // Only fire when no modifier is held and focus is not in an input/textarea
      // so typing is never interrupted.
      if (!e.ctrlKey && !e.metaKey && !e.altKey) {
        if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
          const tag = (document.activeElement as HTMLElement)?.tagName;
          const isTyping = tag === 'INPUT' || tag === 'TEXTAREA' || (document.activeElement as HTMLElement)?.isContentEditable;
          if (!isTyping && activeTool === 'hand') {
            e.preventDefault();
            const container = canvasScrollRef.current;
            if (container) {
              smoothScroll(container, e.key === 'ArrowDown' ? SCROLL_STEP : -SCROLL_STEP);
            }
          }
        }
      }

      // ── Ctrl/Cmd shortcuts ────────────────────────────────────────────────
      if (!e.ctrlKey && !e.metaKey) return;
      switch (e.key) {
        case 'z': e.preventDefault(); handleUndo();       break;
        case 'y': e.preventDefault(); handleRedo();       break;
        case 's': e.preventDefault(); handleExportPdf();  break;
        case 'o': e.preventDefault(); openFileDialog();   break;
        case '=': e.preventDefault(); zoomIn();           break;
        case '-': e.preventDefault(); zoomOut();          break;
        case 'f':
          e.preventDefault();
          setSidebarView('search');
          setShowThumbnails(v => (v, true));
          openSearch();
          break;
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handleUndo, handleRedo, handleExportPdf, openFileDialog, zoomIn, zoomOut,
      setSidebarView, setShowThumbnails, openSearch, activeTool, canvasScrollRef]);
}