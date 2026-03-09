import React from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import { DEFAULT_TEXT_PROPS, type TextProps } from '../../types/textProps';
import { PageRenderer } from './PageRenderer';
import type { ToolId } from '../toolbar/Toolbar';
import type { DocumentState } from './types';

export interface CanvasProps {
  pdfDoc?:            pdfjsLib.PDFDocumentProxy | null;
  documentState?:     DocumentState | null;
  activeTool:         ToolId;
  scale:              number;
  sessionId:          string;
  textProps?:         TextProps;
  onTextPropsChange?: (p: TextProps) => void;
  onAnnotationAdded?: () => Promise<void>;
  onDocumentChanged?: () => Promise<void>;
  onTextSelected?:    (text: string) => void;
  pageRefs?:          React.MutableRefObject<(HTMLDivElement | null)[]>;
}

export function Canvas({
  pdfDoc, documentState, activeTool = 'select', scale = 1.5, sessionId,
  textProps = DEFAULT_TEXT_PROPS, onTextPropsChange,
  onAnnotationAdded, onDocumentChanged, onTextSelected, pageRefs,
}: CanvasProps) {
  return (
    <div className="flex-1 bg-[#353a40] overflow-auto flex flex-col items-center pt-8 pb-8 px-4">
      {!documentState ? (
        <div className="flex flex-col items-center justify-center h-full gap-5 select-none">
          <div className="w-16 h-16 bg-[#2d3338] rounded-xl flex items-center justify-center text-3xl border border-white/[0.05] shadow-2xl">📄</div>
          <div className="text-center">
            <div className="text-base font-semibold text-white mb-1">Open a document to begin</div>
            <div className="text-sm text-gray-400">File → Open, or press Ctrl+O</div>
          </div>
          <div className="flex flex-wrap gap-1.5 justify-center max-w-xs">
            {['Highlight · Redact', 'Add Text · Images', 'Reorder · Rotate', 'Read Aloud · Export'].map(f => (
              <span key={f} className="text-[11px] text-gray-500 bg-[#2d3338] border border-white/[0.05] rounded-full px-3 py-1">{f}</span>
            ))}
          </div>
        </div>
      ) : (
        documentState.children?.map((page, i) => (
          <div key={page.id} ref={el => { if (pageRefs) pageRefs.current[i] = el; }}>
            <PageRenderer
              pageNode={page} pdfDoc={pdfDoc!} pageIndex={i}
              totalPages={documentState.children?.length ?? 1}
              scale={scale} activeTool={activeTool} sessionId={sessionId}
              textProps={textProps} onTextPropsChange={onTextPropsChange}
              onAnnotationAdded={onAnnotationAdded} onDocumentChanged={onDocumentChanged}
              onTextSelected={onTextSelected}
            />
          </div>
        ))
      )}
    </div>
  );
}