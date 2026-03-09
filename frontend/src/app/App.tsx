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

// Register external strategy tools (so they load into the ToolManager registry)
import '../core/tools/PanTool';
import '../core/tools/DragTool';

// Setup PDF.js worker
pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

export default function App() {
  const editor = useEditorState();

  if (editor.loading) {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-[#1e2327] gap-3">
        <div className="w-9 h-9 border-2 border-[#2d3338] border-t-[#4a90e2] rounded-full animate-spin-slow" />
        <span className="text-sm text-gray-400">Loading document…</span>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-[#1e2327] text-white overflow-hidden">
      <TopBar
        tabs={editor.tabs} activeTabId={editor.activeTabId} onTabClick={editor.setActiveTabId}
        onTabClose={id => {
          editor.setTabs(prev => prev.filter(x => x.id !== id));
          if (editor.activeTabId === id) { 
            editor.setActiveTabId(null); 
            editor.setDocumentState(null); 
            editor.setPdfDoc(null); 
          }
        }}
        onNewTab={editor.openFileDialog} onUndo={editor.handleUndo} onRedo={editor.handleRedo} menus={editor.menus}
      />

      <div className="flex-1 flex overflow-hidden min-h-0">
        <LeftSidebar
          showThumbnails={editor.showThumbnails}
          onToggleThumbnails={() => editor.setShowThumbnails(v => !v)}
          pdfDoc={editor.pdfDoc} documentState={editor.documentState} activePage={editor.activePage}
          activeView={editor.sidebarView}
          onViewChange={v => { editor.setSidebarView(v); if (v) editor.setShowThumbnails(true); }}
          onPageClick={i => { 
            editor.setActivePage(i); 
            editor.pageRefs.current[i]?.scrollIntoView({ behavior: 'smooth', block: 'start' }); 
          }}
          onDocumentChanged={editor.refreshDocumentState}
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
              textProps={editor.textProps}
              onTextPropsChange={editor.setTextProps}
              onAnnotationAdded={editor.refreshDocumentState}
              onDocumentChanged={editor.refreshDocumentState}
              onTextSelected={editor.setLastSelectedText}
              pageRefs={editor.pageRefs}
            />
            {editor.rightPanelOpen && (
              <RightPanel
                documentState={editor.documentState} activePage={editor.activePage} activeTool={editor.activeTool}
                textProps={editor.textProps}
                onTextPropsChange={editor.setTextProps}
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