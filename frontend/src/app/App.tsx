// frontend/src/app/App.tsx
import React, { useState, useEffect, useRef } from 'react';
import * as pdfjsLib from 'pdfjs-dist';

// ── pdf.js 5.x asset configuration ────────────────────────────────────────────
// In pdf.js 5.x the worker no longer bundles WASM codecs (OpenJPEG for
// JPEG2000, Jbig2, etc.) inline. Instead it fetches them at runtime via
// fetch() from a path relative to the worker script.
//
// vite.config.ts copies all pdfjs assets to /pdfjs/ in the build output.
// We must tell pdf.js exactly where to find:
//   1. The worker script itself
//   2. The cMaps directory (for CJK / special-encoding text)
//   3. The standard fonts directory (fallback fonts)
//
// The WASM files are loaded automatically by the worker from the same
// directory as the worker script — which is why vite.config.ts copies
// both the worker AND the .wasm files into /pdfjs/.

pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdfjs/pdf.worker.mjs';

// ──────────────────────────────────────────────────────────────────────────────

import { TopBar }      from '../components/layout/TopBar';
import { LeftSidebar } from '../components/layout/LeftSidebar';
import { RightPanel }  from '../components/layout/RightPanel';
import { TtsBar }      from '../components/layout/TtsBar';
import { StatusBar }   from '../components/layout/StatusBar';
import { Toolbar }     from '../components/toolbar/Toolbar';
import { Canvas, type CanvasHandle } from '../components/canvas/Canvas';

import { useEditorState } from '../hooks/useEditorState';
import { useOcr } from '../hooks/useOcr';
import { ThemeProvider, useTheme } from '../theme';
import { ToastProvider } from '../components/canvas/CopyToast';
import { toolManager } from '../core/tools/ToolManager';
import { DrawTool } from '../core/tools/DrawTool';

import '../core/tools/PanTool';
import '../core/tools/DragTool';
import '../core/tools/SelectTool';
import '../core/tools/TextTool';
import { getPanelSection } from '../constants/tools';

// cMap and standard font URLs — passed to getDocument() so pdf.js can
// correctly render non-Latin text and PDFs without embedded fonts.
export const PDFJS_CMAP_URL           = '/pdfjs/cmaps/';
export const PDFJS_STANDARD_FONT_URL  = '/pdfjs/standard_fonts/';

function AppInner() {
  const editor = useEditorState();
  const { theme: t } = useTheme();

  const ocr = useOcr({
    activeTabId: editor.activeTabId,
    onSuccess: editor.refreshDocumentState,
  });

  // Ref to Canvas imperative handle — used by thumbnail clicks to force-render
  // and scroll to pages that haven't been lazily loaded yet.
  const canvasRef = useRef<CanvasHandle>(null);

  const activePageId = (editor.documentState?.children?.[editor.activePage] as { id?: string } | undefined)?.id ?? null;

  const [ocrSectionOpen, setOcrSectionOpen] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [mobileRightPanelOpen, setMobileRightPanelOpen] = useState(false);

  useEffect(() => {
    if (!editor.activeTabId) return;
    const tool = new DrawTool(
      editor.activeTabId,
      editor.highlightColor,
      2.0,
      editor.refreshDocumentState,
    );
    toolManager.registerTool(tool);
  }, [editor.activeTabId]);

  useEffect(() => {
    const tool = toolManager.getTool('draw') as DrawTool | undefined;
    tool?.setColor(editor.highlightColor);
  }, [editor.highlightColor]);

  useEffect(() => {
    if (!editor.activeTabId) return;
    const tool = toolManager.getTool('draw') as DrawTool | undefined;
    tool?.setSessionId(editor.activeTabId);
  }, [editor.activeTabId]);

  useEffect(() => {
    const tool = toolManager.getTool('draw') as DrawTool | undefined;
    tool?.setOnSuccess(editor.refreshDocumentState);
  }, [editor.refreshDocumentState]);

  const toolSection = getPanelSection(editor.activeTool);
  const prevToolSection = React.useRef(toolSection);
  if (prevToolSection.current !== toolSection) {
    prevToolSection.current = toolSection;
    if (ocrSectionOpen) setOcrSectionOpen(false);
  }
  const rightPanelSection = ocrSectionOpen ? 'page' : toolSection;

  React.useEffect(() => {
    if (toolSection && editor.rightPanelOpen) {
      setMobileRightPanelOpen(true);
    }
  }, [toolSection, editor.rightPanelOpen]);

  const handleRunOcr = () => {
    if (!activePageId) return;
    setOcrSectionOpen(true);
    ocr.runOcr(activePageId);
  };

  if (editor.loading) {
    return (
      <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', backgroundColor: t.colors.bgBase, gap: '12px' }}>
        <div className="w-9 h-9 border-2 border-[#2d3338] border-t-[#4a90e2] rounded-full animate-spin-slow" />
        <span style={{ fontSize: '14px', color: t.colors.textSecondary }}>Loading document…</span>
      </div>
    );
  }

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: t.colors.bgBase, color: t.colors.textPrimary, overflow: 'hidden' }}>
      <TopBar
        tabs={editor.tabs} activeTabId={editor.activeTabId} onTabClick={editor.setActiveTabId}
        onTabClose={editor.handleTabClose}
        onNewTab={editor.openFileDialog} onUndo={editor.handleUndo} onRedo={editor.handleRedo} onSave={editor.handleExportPdf} menus={editor.menus}
        onToggleMobileSidebar={() => setMobileSidebarOpen(v => !v)}
        onToggleMobileRightPanel={() => setMobileRightPanelOpen(v => !v)}
      />

      <div className="flex-1 flex overflow-hidden min-h-0 relative">

        {mobileSidebarOpen && (
          <div
            className="md:hidden absolute inset-0 z-[8999] bg-black/40 transition-opacity"
            onClick={() => setMobileSidebarOpen(false)}
          />
        )}

        <div
          className={`
            absolute inset-y-0 left-0 z-[9000] flex flex-col transform transition-transform duration-200 ease-in-out md:relative md:translate-x-0 md:z-0
            ${mobileSidebarOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full md:shadow-none'}
          `}
          style={{ backgroundColor: t.colors.bgBase }}
        >
          <LeftSidebar
            showThumbnails={editor.showThumbnails}
            onToggleThumbnails={() => editor.setShowThumbnails(v => !v)}
            pdfDoc={editor.pdfDoc} documentState={editor.documentState} activePage={editor.activePage}
            activeView={editor.sidebarView}
            sessionId={editor.activeTabId ?? ''}
            onViewChange={v => {
              editor.setSidebarView(v);
              if (v) editor.setShowThumbnails(true);
              if (v === 'search') editor.search.open();
            }}
            onPageClick={i => {
              editor.setActivePage(i);
              // jumpToPage force-renders the target page if not yet loaded,
              // then scrolls to it. Raw scrollIntoView breaks for unrendered
              // pages because they have no real height yet (lazy placeholder).
              if (canvasRef.current) {
                canvasRef.current.jumpToPage(i);
              } else {
                editor.pageRefs.current[i]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
              }
              setMobileSidebarOpen(false);
            }}
            onDocumentChanged={editor.refreshDocumentState}
            search={{
              query:          editor.search.query,
              onQueryChange:  editor.search.handleQueryChange,
              matchCount:     editor.search.matches.length,
              currentIndex:   editor.search.currentIndex,
              isSearching:    editor.search.isSearching,
              pageMatchMap:   editor.search.pageMatchMap,
              matches:        editor.search.matches,
              onNext:         editor.search.goNext,
              onPrev:         editor.search.goPrev,
              goToMatch:      editor.search.goToMatch,
              inputRef:       editor.search.inputRef,
            }}
          />
        </div>

        <div className="flex-1 flex flex-col overflow-hidden min-w-0">
          <Toolbar
            activeTool={editor.activeTool}
            onToolChange={editor.setActiveTool}
            scale={editor.scale} onZoomIn={editor.zoomIn} onZoomOut={editor.zoomOut} onZoomReset={editor.zoomReset}
            onUndo={editor.handleUndo} onRedo={editor.handleRedo}
            onReadPage={editor.handleReadPage} onReadSelection={editor.handleReadSelection}
            hasSelection={!!editor.lastSelectedText} ttsActive={editor.tts.visible}
            pageInfo={editor.documentState ? { current: editor.activePage + 1, total: editor.pageCount } : null}
            onRunOcr={activePageId ? handleRunOcr : undefined} isOcrProcessing={ocr.isProcessing}
          />

          <div className="flex-1 flex overflow-hidden min-h-0 relative">
            <Canvas
              ref={canvasRef}
              pdfDoc={editor.pdfDoc} documentState={editor.documentState}
              activeTool={editor.activeTool} scale={editor.scale}
              sessionId={editor.activeTabId ?? ''}
              textProps={editor.textProps}
              highlightColor={editor.highlightColor}
              highlightOpacity={editor.highlightOpacity}
              onTextPropsChange={editor.setTextProps}
              onAnnotationAdded={editor.refreshDocumentState}
              onDocumentChanged={editor.refreshDocumentState}
              onTextSelected={editor.setLastSelectedText}
              pageRefs={editor.pageRefs}
              canvasScrollRef={editor.canvasScrollRef}
              pageMatchMap={editor.search.pageMatchMap}
              onActivePageChange={editor.setActivePage} 
            />

            {mobileRightPanelOpen && (
              <div
                className="md:hidden absolute inset-0 z-[8499] bg-black/40 transition-opacity"
                onClick={() => setMobileRightPanelOpen(false)}
              />
            )}

            {editor.rightPanelOpen && (
              <div
                className={`
                   absolute inset-y-0 right-0 z-[8500] md:relative md:z-0 shadow-2xl md:shadow-none transform transition-transform duration-200 ease-in-out md:translate-x-0
                   ${mobileRightPanelOpen ? 'translate-x-0' : 'translate-x-full'}
                `}
                style={{ backgroundColor: t.colors.bgBase }}
              >
                <RightPanel
                  documentState={editor.documentState}
                  activePage={editor.activePage}
                  activeTool={editor.activeTool}
                  textProps={editor.textProps}
                  onTextPropsChange={editor.setTextProps}
                  highlightColor={editor.highlightColor}
                  highlightOpacity={editor.highlightOpacity}
                  onHighlightColorChange={editor.setHighlightColor}
                  onHighlightOpacityChange={editor.setHighlightOpacity}
                  sessionId={editor.activeTabId}
                  onDocumentChanged={editor.refreshDocumentState}
                  onRunOcr={activePageId ? handleRunOcr : undefined}
                  isOcrProcessing={ocr.isProcessing}
                  ocrError={ocr.error}
                  openSection={rightPanelSection}
                  onSectionChange={s => { if (s !== 'page') setOcrSectionOpen(false); }}
                  onCloseMobile={() => setMobileRightPanelOpen(false)}
                />
              </div>
            )}
          </div>
        </div>
      </div>

      <TtsBar
        visible={editor.tts.visible} status={editor.tts.status} phase={editor.tts.phase}
        progress={editor.tts.progress} isPaused={editor.tts.isPaused} speed={editor.tts.speed}
        onStop={editor.ttsStop} onPauseResume={editor.pauseResume} onSpeedChange={editor.setSpeed}
      />

      <StatusBar
        activeTool={editor.activeTool} scale={editor.scale} activePage={editor.activePage}
        pageCount={editor.pageCount} lastSelectedText={editor.lastSelectedText} documentState={editor.documentState}
      />

      <input ref={editor.fileInputRef} type="file" accept="application/pdf" className="hidden" onChange={editor.handleFileUpload} />
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <AppInner />
      </ToastProvider>
    </ThemeProvider>
  );
}