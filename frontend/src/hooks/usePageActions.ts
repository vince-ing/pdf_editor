import { useCallback } from 'react';
import { engineApi } from '../api/client';
import type { TextRun, TextProps } from '../types/textProps';
import type { AnnotationNode, PageNode } from '../components/canvas/types';
import type { ToolId } from '../components/toolbar/Toolbar';

interface UsePageActionsProps {
  pageNode: PageNode;
  pageChars: any[];
  activeTool: ToolId;
  textProps: TextProps;
  sessionId: string;
  setAnnotations: React.Dispatch<React.SetStateAction<AnnotationNode[]>>;
  setTransientPos: (pos: { x: number; y: number } | null) => void;
  onAnnotationAdded?: () => Promise<void>;
  onTextSelected?: (text: string) => void;
  clearSelRef: React.MutableRefObject<(() => void) | null>;
  toast: () => void;
  textToolNotifyCommitted: () => void;
}

export function usePageActions({
  pageNode,
  pageChars,
  activeTool,
  textProps,
  sessionId,
  setAnnotations,
  setTransientPos,
  onAnnotationAdded,
  onTextSelected,
  clearSelRef,
  toast,
  textToolNotifyCommitted,
}: UsePageActionsProps) {

  const handleNodeUpdate = useCallback(async (nodeId: string, updatedNode: Partial<AnnotationNode & { runs: TextRun[] }>) => {
    setAnnotations(prev => prev.map(n => n.id === nodeId ? { ...n, ...updatedNode } as AnnotationNode : n));
    try {
      await engineApi.updateAnnotation(nodeId, {
        page_id:      pageNode.id,
        x:            updatedNode.bbox?.x,
        y:            updatedNode.bbox?.y,
        width:        updatedNode.bbox?.width,
        height:       updatedNode.bbox?.height,
        text_content: updatedNode.text_content,
        runs:         updatedNode.runs,
      }, sessionId);
    } catch (err) { console.error('Failed to update node:', err); }
  }, [pageNode.id, sessionId, setAnnotations]);

  const handleAction = useCallback(async (rects: { x: number; y: number; width: number; height: number }[]) => {
    if (activeTool === 'crop') return;
    if (activeTool === 'select') {
      const tol = 4;
      const sel = pageChars
        .filter(c => { const cx = c.x + c.width / 2, cy = c.y + c.height / 2; return rects.some(r => cx >= r.x - tol && cx <= r.x + r.width + tol && cy >= r.y - tol && cy <= r.y + r.height + tol); })
        .sort((a, b) => Math.abs(a.y - b.y) > 5 ? a.y - b.y : a.x - b.x);
      if (!sel.length) return;
      let text = sel[0].text;
      for (let i = 1; i < sel.length; i++) {
        const p = sel[i - 1], c = sel[i];
        const avgH = (p.height + c.height) / 2;
        text += Math.abs((p.y + p.height / 2) - (c.y + c.height / 2)) > avgH * 0.75 ? '\n' + c.text : (c.x - (p.x + p.width) > p.width * 0.4 ? ' ' : '') + c.text;
      }
      try { await navigator.clipboard.writeText(text); toast(); onTextSelected?.(text); }
      catch { window.prompt('Copy (Ctrl+C):', text); onTextSelected?.(text); }
      return;
    }
    try {
      if (activeTool === 'highlight') {
        const res = await engineApi.addHighlight(
          pageNode.id, rects[0].x, rects[0].y, rects[0].width, rects[0].height, sessionId,
        );
        if (res?.node) { setAnnotations(p => [...p, res.node]); onAnnotationAdded?.(); }
      } else if (activeTool === 'redact') {
        const res = await engineApi.applyRedaction(pageNode.id, rects, sessionId);
        const nodes = res?.node ? [res.node] : (res?.nodes ?? []);
        if (nodes.length) { setAnnotations(p => [...p, ...nodes]); onAnnotationAdded?.(); }
      }
      clearSelRef.current?.();
    } catch (e) { console.error(e); }
  }, [activeTool, pageNode.id, sessionId, pageChars, toast, onAnnotationAdded, onTextSelected, setAnnotations, clearSelRef]);

  const handleTextCommit = useCallback(async (runs: TextRun[], plain: string, x: number, y: number, w: number, h: number) => {
    setTransientPos(null);
    textToolNotifyCommitted();
    try {
      const res = await engineApi.addTextAnnotation(
        pageNode.id, plain, x, y, sessionId, w, h,
        textProps.fontFamily, textProps.fontSize, textProps.color,
        textProps.isBold, textProps.isItalic, runs,
      );
      if (res?.node) { setAnnotations(p => [...p, res.node]); onAnnotationAdded?.(); }
    } catch (err) { console.error(err); }
  }, [pageNode.id, sessionId, textProps, onAnnotationAdded, setAnnotations, setTransientPos, textToolNotifyCommitted]);

  return { handleNodeUpdate, handleAction, handleTextCommit };
}