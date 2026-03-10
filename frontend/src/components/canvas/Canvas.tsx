// components/canvas/Canvas.tsx
import React from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import { DEFAULT_TEXT_PROPS, type TextProps } from '../../types/textProps';
import { PageRenderer } from './PageRenderer';
import type { ToolId } from '../toolbar/Toolbar';
import type { DocumentState } from './types';
import { useTheme } from '../../theme';
import type { PageMatchMap } from '../../hooks/useSearchState';

export interface CanvasProps {
  pdfDoc?: pdfjsLib.PDFDocumentProxy | null; documentState?: DocumentState | null;
  activeTool: ToolId; scale: number; sessionId: string;
  textProps?: TextProps; highlightColor?: string; highlightOpacity?: number;
  onTextPropsChange?: (p: TextProps) => void; onAnnotationAdded?: () => Promise<void>;
  onDocumentChanged?: () => Promise<void>; onTextSelected?: (text: string) => void;
  pageRefs?: React.MutableRefObject<(HTMLDivElement | null)[]>;
  canvasScrollRef?: React.MutableRefObject<HTMLDivElement | null>;
  // Search
  pageMatchMap?: PageMatchMap;
}

export function Canvas({
  pdfDoc, documentState, activeTool = 'select', scale = 1.5, sessionId,
  textProps = DEFAULT_TEXT_PROPS, highlightColor, highlightOpacity, onTextPropsChange,
  onAnnotationAdded, onDocumentChanged, onTextSelected, pageRefs,
  canvasScrollRef,
  pageMatchMap = {},
}: CanvasProps) {
  const { theme: t } = useTheme();

  return (
    <div
      ref={canvasScrollRef}
      style={{ flex: 1, backgroundColor: t.colors.bgHover, overflow: 'auto', display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 32, paddingBottom: 32, paddingLeft: 16, paddingRight: 16 }}
    >
      {!documentState ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 20, userSelect: 'none' }}>
          <div style={{ width: 64, height: 64, backgroundColor: t.colors.bgRaised, borderRadius: t.radius.lg, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28, border: `1px solid ${t.colors.border}`, boxShadow: t.shadow.panel }}>📄</div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '15px', fontWeight: 600, color: t.colors.textPrimary, marginBottom: 4, fontFamily: t.fonts.ui }}>Open a document to begin</div>
            <div style={{ fontSize: '13px', color: t.colors.textSecondary, fontFamily: t.fonts.ui }}>File → Open, or press Ctrl+O</div>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'center', maxWidth: 280 }}>
            {['Highlight · Redact', 'Add Text · Images', 'Reorder · Rotate', 'Read Aloud · Export'].map(f => (
              <span key={f} style={{ fontSize: '11px', color: t.colors.textMuted, backgroundColor: t.colors.bgRaised, border: `1px solid ${t.colors.border}`, borderRadius: t.radius.pill, padding: '3px 12px', fontFamily: t.fonts.ui }}>{f}</span>
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
              textProps={textProps} highlightColor={highlightColor} highlightOpacity={highlightOpacity}
              onTextPropsChange={onTextPropsChange}
              onAnnotationAdded={onAnnotationAdded} onDocumentChanged={onDocumentChanged}
              onTextSelected={onTextSelected}
              searchMatches={pageMatchMap[page.id] ?? []}
            />
          </div>
        ))
      )}
    </div>
  );
}