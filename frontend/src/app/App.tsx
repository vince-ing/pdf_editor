// frontend/src/app/App.tsx
import React from 'react';
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
import { ThemeProvider, useTheme } from '../theme';

// Register external strategy tools
import '../core/tools/PanTool';
import '../core/tools/DragTool';
import '../core/tools/SelectTool'; 
import '../core/tools/TextTool';

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

// ── Inner app — has access to ThemeProvider context ──────────────────────────

function AppInner() {
  const editor = useEditorState();
  const { theme: t } = useTheme();

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
      />

      <div className="flex-1 flex overflow-hidden min-h-0">
        <LeftSidebar
          showThumbnails={editor.showThumbnails}
          onToggleThumbnails={() => editor.setShowThumbnails(v => !v)}
          pdfDoc={editor.pdfDoc} documentState={editor.documentState} activePage={editor.activePage}
          activeView={editor.sidebarView}
          onViewChange={v => {
            editor.setSidebarView(v);
            if (v) editor.setShowThumbnails(true);
            if (v === 'search') editor.search.open();
          }}
          onPageClick={i => {
            editor.setActivePage(i);
            editor.pageRefs.current[i]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
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

        <div className="flex-1 flex flex-col overflow-hidden min-w-0">
          <Toolbar
            activeTool={editor.activeTool}
            onToolChange={editor.setActiveTool}
            scale={editor.scale} onZoomIn={editor.zoomIn} onZoomOut={editor.zoomOut} onZoomReset={editor.zoomReset}
            onUndo={editor.handleUndo} onRedo={editor.handleRedo}
            onReadPage={editor.handleReadPage} onReadSelection={editor.handleReadSelection}
            hasSelection={!!editor.lastSelectedText} ttsActive={editor.tts.visible}
            pageInfo={editor.documentState ? { current: editor.activePage + 1, total: editor.pageCount } : null}
          />

          <div className="flex-1 flex overflow-hidden min-h-0">
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
            {editor.rightPanelOpen && (
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
              />
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

// ── Root export ───────────────────────────────────────────────────────────────

export default function App() {
  return (
    <ThemeProvider>
      <AppInner />
    </ThemeProvider>
  );
}