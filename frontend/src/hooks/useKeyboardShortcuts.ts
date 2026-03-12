// frontend/src/hooks/useKeyboardShortcuts.ts
import { useEffect } from 'react';
import type { SidebarView } from '../components/layout/LeftSidebar';

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
}: UseKeyboardShortcutsArgs) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
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
          setShowThumbnails(v => (v, true)); // ensure sidebar is visible
          openSearch();
          break;
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handleUndo, handleRedo, handleExportPdf, openFileDialog, zoomIn, zoomOut, setSidebarView, setShowThumbnails, openSearch]);
}