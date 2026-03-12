// frontend/src/hooks/useEditorState.ts
//
// Thin composer: calls focused sub-hooks and assembles the return object.
// Owns only state that doesn't belong to any single sub-hook:
//   activeTool, sidebar/panel UI prefs, textProps, highlight color/opacity.

import { useState, useCallback, useRef, useMemo } from 'react';
import { buildMenuDefs } from '../constants/menuDefs';
import { DEFAULT_TEXT_PROPS, type TextProps } from '../types/textProps';
import { toolManager } from '../core/tools/ToolManager';
import { useTheme } from '../theme';
import { useSearchState } from './useSearchState';
import { useTabManager } from './useTabManager';
import { useSessionState } from './useSessionState';
import { useZoom } from './useZoom';
import { useDocumentActions } from './useDocumentActions';
import { useKeyboardShortcuts } from './useKeyboardShortcuts';

import type { ToolId } from '../constants/tools';
import type { SidebarView } from '../components/layout/LeftSidebar';

export function useEditorState() {
  // ── Refs shared across hooks ───────────────────────────────────────────────
  const fileInputRef    = useRef<HTMLInputElement>(null);
  const pageRefs        = useRef<(HTMLDivElement | null)[]>([]);
  const canvasScrollRef = useRef<HTMLDivElement | null>(null);

  // ── Sub-hooks (order matters — each may depend on the previous) ────────────
  const tabManager = useTabManager(fileInputRef, pageRefs);

  const session = useSessionState({
    activeTabId:   tabManager.activeTabId,
    activeSession: tabManager.activeSession,
    patchSession:  tabManager.patchSession,
    pageRefs,
  });

  const { zoomIn, zoomOut, zoomReset } = useZoom(session.setScale);

  const actions = useDocumentActions({
    activeTabId:          tabManager.activeTabId,
    documentState:        session.documentState,
    pdfDoc:               session.pdfDoc,
    activePage:           session.activePage,
    refreshDocumentState: session.refreshDocumentState,
  });

  // ── Local UI state ─────────────────────────────────────────────────────────
  const [activeTool,       setActiveToolState]  = useState<ToolId>('hand');
  const [sidebarView,      setSidebarView]      = useState<SidebarView>('pages');
  const [showThumbnails,   setShowThumbnails]   = useState(true);
  const [rightPanelOpen,   setRightPanelOpen]   = useState(true);
  const [textProps,        setTextProps]        = useState<TextProps>(DEFAULT_TEXT_PROPS);
  const [highlightColor,   setHighlightColor]   = useState('#f59e0b');
  const [highlightOpacity, setHighlightOpacity] = useState(0.45);

  // ── Theme ──────────────────────────────────────────────────────────────────
  const { themeId, setTheme } = useTheme();

  // ── Search ─────────────────────────────────────────────────────────────────
  const search = useSearchState({
    documentState:   session.documentState,
    sessionId:       tabManager.activeTabId,
    pageRefs,
    canvasScrollRef,
    scale:           session.scale,
  });

  // ── Tool sync ──────────────────────────────────────────────────────────────
  const setActiveTool = useCallback((id: ToolId) => {
    setActiveToolState(id);
    toolManager.setActiveTool(id);
  }, []);

  // ── Keyboard shortcuts ─────────────────────────────────────────────────────
  useKeyboardShortcuts({
    handleUndo:        actions.handleUndo,
    handleRedo:        actions.handleRedo,
    handleExportPdf:   actions.handleExportPdf,
    openFileDialog:    tabManager.openFileDialog,
    zoomIn,
    zoomOut,
    setSidebarView,
    setShowThumbnails,
    openSearch:        search.open,
  });

  // ── Menus ──────────────────────────────────────────────────────────────────
  // buildMenuDefs creates new arrays every call, so memoize against its
  // inputs to avoid unnecessary re-renders of TopBar on every keystroke.
  const menus = useMemo(() => buildMenuDefs({
    openFileDialog:      tabManager.openFileDialog,
    handleExportPdf:     actions.handleExportPdf,
    handleUndo:          actions.handleUndo,
    handleRedo:          actions.handleRedo,
    handleReadPage:      actions.handleReadPage,
    handleReadSelection: actions.handleReadSelection,
    ttsStop:             actions.ttsStop,
    setShowThumbnails,
    setRightPanelOpen,
    zoomIn, zoomOut, zoomReset,
    documentState:       session.documentState,
    themeId, setTheme,
    openSearch:          search.open,
  }), [
    tabManager.openFileDialog,
    actions.handleExportPdf,
    actions.handleUndo,
    actions.handleRedo,
    actions.handleReadPage,
    actions.handleReadSelection,
    actions.ttsStop,
    zoomIn, zoomOut, zoomReset,
    session.documentState,
    themeId, setTheme,
    search.open,
  ]);

  const pageCount = session.documentState?.children?.length ?? 0;

  // ── Assembled return ───────────────────────────────────────────────────────
  return {
    // Tab management
    tabs:           tabManager.tabs,
    activeTabId:    tabManager.activeTabId,
    setActiveTabId: tabManager.setActiveTabId,
    handleTabClose: tabManager.handleTabClose,
    loading:        tabManager.loading,

    // Session state
    documentState:        session.documentState,
    pdfDoc:               session.pdfDoc,
    activePage:           session.activePage,
    setActivePage:        session.setActivePage,
    scale:                session.scale,
    refreshDocumentState: session.refreshDocumentState,

    // Zoom
    zoomIn, zoomOut, zoomReset,

    // Document actions + selected text (co-located in useDocumentActions)
    handleUndo:          actions.handleUndo,
    handleRedo:          actions.handleRedo,
    handleExportPdf:     actions.handleExportPdf,
    handleReadPage:      actions.handleReadPage,
    handleReadSelection: actions.handleReadSelection,
    lastSelectedText:    actions.lastSelectedText,
    setLastSelectedText: actions.setLastSelectedText,
    tts:                 actions.tts,
    ttsStop:             actions.ttsStop,
    pauseResume:         actions.pauseResume,
    setSpeed:            actions.setSpeed,

    // File I/O
    openFileDialog:   tabManager.openFileDialog,
    handleFileUpload: tabManager.handleFileUpload,

    // Local UI state
    activeTool,       setActiveTool,
    sidebarView,      setSidebarView,
    showThumbnails,   setShowThumbnails,
    rightPanelOpen,   setRightPanelOpen,
    textProps,        setTextProps,
    highlightColor,   setHighlightColor,
    highlightOpacity, setHighlightOpacity,

    // Theme
    themeId, setTheme,

    // Refs
    fileInputRef, pageRefs, canvasScrollRef,

    // Search
    search,

    // Menus
    menus, pageCount,
  };
}