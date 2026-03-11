// frontend/src/app/App.tsx
// Make sure to add the new onToggleMobileRightPanel prop
import React, { useState, useEffect } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.mjs?url';

import { TopBar }      from '../components/layout/TopBar';
import { LeftSidebar } from '../components/layout/LeftSidebar';
import { RightPanel }  from '../components/layout/RightPanel';
import { TtsBar }      from '../components/layout/TtsBar';
import { StatusBar }   from '../components/layout/StatusBar';
import { Toolbar }     from '../components/toolbar/Toolbar';
import { Canvas }      from '../components/canvas/Canvas';

import { useEditorState } from '../hooks/useEditorState';
import { useOcr } from '../hooks/useOcr';
import { ThemeProvider, useTheme } from '../theme';
import { toolManager } from '../core/tools/ToolManager';
import { DrawTool } from '../core/tools/DrawTool';

// Register external strategy tools
import '../core/tools/PanTool';
import '../core/tools/DragTool';
import '../core/tools/SelectTool'; 
import '../core/tools/TextTool';

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

const TOOL_SECTION_MAP: Partial<Record<string, 'text' | 'page' | 'appearance'>> = {
  addtext: 'text', edittext: 'text',
  highlight: 'appearance', underline: 'appearance', stickynote: 'appearance',
  stamp: 'appearance', redact: 'appearance', draw: 'appearance',
  insert: 'page', delete: 'page', rotate: 'page', extract: 'page', crop: 'page',
};

function AppInner() {
  const editor = useEditorState();
  const { theme: t } = useTheme();

  const ocr = useOcr({
    activeTabId: editor.activeTabId,
    onSuccess: editor.refreshDocumentState,
  });

  const activePageId = (editor.documentState?.children?.[editor.activePage] as { id?: string } | undefined)?.id ?? null;

  const [ocrSectionOpen, setOcrSectionOpen] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [mobileRightPanelOpen, setMobileRightPanelOpen] = useState(false);

  // Initialize and register the draw tool when the session becomes active
  useEffect(() => {
    if (editor.activeTabId) {
       // Only register if it hasn't been added yet, to avoid duplicate registrations on re-renders
       if (!toolManager.getActiveTool() || toolManager.getActiveToolId() !== 'draw' || !toolManager['tools']?.has('draw')) {
           toolManager.registerTool(
             new DrawTool(editor.activeTabId, editor.highlightColor, 2.0, editor.refreshDocumentState)
           );
       }
    }
  }, [editor.activeTabId, editor.highlightColor, editor.refreshDocumentState]);

  // Hook into annotation additions so drawn paths refresh the canvas
  useEffect(() => {
     // Re-register if color changes and draw tool is active
     if (editor.activeTabId && toolManager.getActiveToolId() === 'draw') {
        toolManager.registerTool(
          new DrawTool(editor.activeTabId, editor.highlightColor, 2.0, editor.refreshDocumentState)
        );
     }
  }, [editor.highlightColor, editor.activeTabId, editor.refreshDocumentState]);


  const toolSection = TOOL_SECTION_MAP[editor.activeTool] ?? null;
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
              editor.pageRefs.current[i]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
      <AppInner />
    </ThemeProvider>
  );
}