// frontend/src/components/canvas/Canvas.tsx
// Canvas.tsx — PDF document area. bg-[#353a40], pages centered, annotations overlaid.

import { useRef, useEffect, useState, useCallback } from 'react';
import { engineApi } from "../../api/client";
import { usePdfCanvas } from '../../hooks/usePdfCanvas';
import { usePageChars } from '../../hooks/usePageChars';
import { useDragSelection } from '../../hooks/useDragSelection';
import * as pdfjsLib from 'pdfjs-dist';

type ToolId = import('./Toolbar').ToolId;

interface AnnotationNode {
  id: string;
  node_type: string;
  bbox?: { x: number; y: number; width: number; height: number };
  color?: string;
  opacity?: number;
  text_content?: string;
  font_size?: number;
  font_family?: string;
}

interface PageNode {
  id: string;
  page_number?: number;
  rotation?: number;
  metadata?: { width: number; height: number };
  crop_box?: { x: number; y: number; width: number; height: number };
  children?: AnnotationNode[];
}

interface DocumentState {
  children?: PageNode[];
  file_name?: string;
}

interface CanvasProps {
  pdfDoc?: pdfjsLib.PDFDocumentProxy | null;
  documentState?: DocumentState | null;
  activeTool: ToolId;
  scale: number;
  onAnnotationAdded?: () => Promise<void>;
  onDocumentChanged?: () => Promise<void>;
  onTextSelected?: (text: string) => void;
  pageRefs?: React.MutableRefObject<(HTMLDivElement | null)[]>;
}

// ── Tool cursor map ───────────────────────────────────────────────────────────
const CURSORS: Partial<Record<ToolId, string>> = {
  hand: 'grab', select: 'default', zoom: 'zoom-in',
  addtext: 'text', edittext: 'text',
  highlight: 'crosshair', redact: 'crosshair', crop: 'crosshair', underline: 'crosshair',
};

// ── Selection overlay color per tool ─────────────────────────────────────────
const SEL_COLOR: Partial<Record<ToolId, string>> = {
  highlight: 'rgba(245,158,11,0.25)',
  redact:    'rgba(239,68,68,0.25)',
  select:    'rgba(74,144,226,0.2)',
  crop:      'rgba(0,0,0,0)',
  underline: 'rgba(255,255,255,0.1)',
};

// ── Copy toast ────────────────────────────────────────────────────────────────
const CopyToast = ({ visible }: { visible: boolean }) => (
  <div
    className={`fixed bottom-10 left-1/2 -translate-x-1/2 bg-[#2d3338] text-white border border-white/[0.07] px-4 py-2 rounded-lg text-sm font-medium shadow-xl flex items-center gap-2 pointer-events-none z-50 transition-all duration-200
      ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}
  >
    <span className="text-green-400">✓</span> Copied to clipboard
  </div>
);

// ── Single page renderer ──────────────────────────────────────────────────────
function PageRenderer({
  pageNode, pdfDoc, pageIndex, totalPages, scale, activeTool,
  onAnnotationAdded, onDocumentChanged, onTextSelected, containerRef,
}: {
  pageNode: PageNode;
  pdfDoc: pdfjsLib.PDFDocumentProxy;
  pageIndex: number;
  totalPages: number;
  scale: number;
  activeTool: ToolId;
  onAnnotationAdded?: () => Promise<void>;
  onDocumentChanged?: () => Promise<void>;
  onTextSelected?: (text: string) => void;
  containerRef?: React.Ref<HTMLDivElement>;
}) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const clearSelRef = useRef<(() => void) | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout>>();
  const busyRef = useRef(false);

  const [annotations, setAnnotations] = useState<AnnotationNode[]>(pageNode.children ?? []);
  const [hovered, setHovered] = useState(false);
  const [busy, setBusy] = useState(false);
  const [localRotation, setLocalRotation] = useState(pageNode.rotation ?? 0);
  const [showToast, setShowToast] = useState(false);
  const [showCtrl, setShowCtrl] = useState(false);
  
  // State to hold the temporary coordinates for the inline text box
  const [transientText, setTransientText] = useState<{ x: number; y: number } | null>(null);

  useEffect(() => { setAnnotations(pageNode.children ?? []); }, [pageNode.children]);
  useEffect(() => { if (typeof pageNode.rotation === 'number') setLocalRotation(pageNode.rotation); }, [pageNode.rotation, pageNode.id]);

  const { canvasRef, fullDimensions } = usePdfCanvas({ pdfDoc, pageNode, pageIndex, scale, localRotation });
  const { pageChars } = usePageChars({ pageNodeId: pageNode.id, localRotation, metadata: pageNode.metadata });

  const withBusy = useCallback(async (fn: () => Promise<void>) => {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true);
    try { await fn(); } finally { busyRef.current = false; setBusy(false); }
  }, []);

  const toast = useCallback(() => {
    setShowToast(true);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setShowToast(false), 2000);
  }, []);

  const handleNodeUpdate = useCallback(async (nodeId: string, updatedNode: Partial<AnnotationNode>) => {
    setAnnotations(prev => prev.map(n => n.id === nodeId ? { ...n, ...updatedNode } as AnnotationNode : n));
    try {
      await engineApi.updateAnnotation(nodeId, {
        page_id: pageNode.id,
        x: updatedNode.bbox?.x,
        y: updatedNode.bbox?.y,
        width: updatedNode.bbox?.width,
        height: updatedNode.bbox?.height,
      });
    } catch (err) {
      console.error("Failed to update node:", err);
    }
  }, [pageNode.id]);

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
        const res = await fetch('http://localhost:8000/api/annotations/highlight', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ page_id: pageNode.id, rects }),
        }).then(r => r.json());
        if (res?.node) { setAnnotations(p => [...p, res.node]); onAnnotationAdded?.(); }
      } else if (activeTool === 'redact') {
        const res = await engineApi.applyRedaction(pageNode.id, rects);
        const nodes = res?.node ? [res.node] : (res?.nodes ?? []);
        if (nodes.length) { setAnnotations(p => [...p, ...nodes]); onAnnotationAdded?.(); }
      }
      clearSelRef.current?.();
    } catch (e) { console.error(e); }
  }, [activeTool, pageNode.id, pageChars, toast, onAnnotationAdded]);

  const isDragTool = ['highlight', 'redact', 'select', 'crop', 'underline'].includes(activeTool);
  const { liveRects, committedRects, clearSelection, handlers } = useDragSelection({ overlayRef, pageChars, scale, activeTool, metadata: pageNode.metadata, onAction: handleAction });
  useEffect(() => { clearSelRef.current = clearSelection; }, [clearSelection]);

  const displayRects = liveRects.length > 0 ? liveRects : committedRects;
  const cropRect = activeTool === 'crop' && committedRects[0];

  const cropBox = pageNode.crop_box;
  const isCropped = cropBox && typeof cropBox.width === 'number';
  const outerW = isCropped ? cropBox!.width * scale : fullDimensions.width;
  const outerH = isCropped ? cropBox!.height * scale : fullDimensions.height;
  const innerX = isCropped ? -(cropBox!.x * scale) : 0;
  const innerY = isCropped ? -(cropBox!.y * scale) : 0;

  return (
    <div
      ref={containerRef as React.Ref<HTMLDivElement>}
      style={{ width: outerW, height: outerH, opacity: busy ? 0.75 : 1 }}
      className={`relative bg-white flex-shrink-0 mx-auto mb-6 transition-shadow rounded-sm ${hovered ? 'shadow-2xl' : 'shadow-xl'} ${isCropped ? 'overflow-hidden' : ''}`}
      onMouseEnter={() => { setHovered(true); setShowCtrl(true); }}
      onMouseLeave={() => { setHovered(false); setShowCtrl(false); }}
    >
      {/* Page controls */}
      {showCtrl && !cropRect && (
        <div className="absolute -top-9 left-1/2 -translate-x-1/2 z-30 flex items-center gap-1 bg-[#2d3338] border border-white/[0.07] rounded-lg px-2 py-1.5 shadow-xl animate-ctrl-in">
          {[
            { icon: '↑', title: 'Move up', disabled: pageIndex === 0, onClick: () => withBusy(async () => { await engineApi.movePage(pageNode.id, pageIndex - 1); await onDocumentChanged?.(); }) },
            { icon: '↓', title: 'Move down', disabled: pageIndex >= totalPages - 1, onClick: () => withBusy(async () => { await engineApi.movePage(pageNode.id, pageIndex + 1); await onDocumentChanged?.(); }) },
            null,
            { icon: '↻', title: 'Rotate CW', onClick: () => withBusy(async () => { const r = await engineApi.rotatePage(pageNode.id, 90); setLocalRotation(r?.page?.rotation ?? (v => (v + 90) % 360)); await onDocumentChanged?.(); }) },
            { icon: '↺', title: 'Rotate CCW', onClick: () => withBusy(async () => { const r = await engineApi.rotatePage(pageNode.id, -90); setLocalRotation(r?.page?.rotation ?? (v => (v - 90 + 360) % 360)); await onDocumentChanged?.(); }) },
            null,
            { icon: '✕', title: 'Delete page', danger: true, disabled: totalPages <= 1, onClick: () => { if (!window.confirm(`Delete page ${pageIndex + 1}?`)) return; withBusy(async () => { await engineApi.deletePage(pageNode.id); await onDocumentChanged?.(); }); } },
          ].map((btn, i) =>
            btn === null
              ? <div key={i} className="w-px h-4 bg-white/10 mx-0.5" />
              : (
                <button
                  key={i}
                  title={btn.title}
                  disabled={btn.disabled}
                  onClick={btn.onClick}
                  className={`w-7 h-7 rounded flex items-center justify-center text-sm transition-colors
                    ${btn.danger ? 'text-red-400 hover:bg-red-500/20 disabled:opacity-30' : 'text-gray-400 hover:bg-[#3d4449] hover:text-white disabled:opacity-30'}
                    disabled:cursor-not-allowed`}
                >
                  {btn.icon}
                </button>
              )
          )}
        </div>
      )}

      <div style={{ position: 'absolute', top: innerY, left: innerX, width: fullDimensions.width, height: fullDimensions.height }}>
        
        {/* Layer 1: PDF canvas */}
        <canvas ref={canvasRef} className="absolute inset-0 pointer-events-none" style={{ width: fullDimensions.width, height: fullDimensions.height }} />

        {/* Layer 2: Crop mask */}
        {cropRect && (
          <div className="absolute inset-0 pointer-events-none z-[8]">
            {[
              { top: 0, left: 0, right: 0, height: cropRect.y * scale },
              { bottom: 0, left: 0, right: 0, top: (cropRect.y + cropRect.height) * scale },
              { top: cropRect.y * scale, left: 0, width: cropRect.x * scale, height: cropRect.height * scale },
              { top: cropRect.y * scale, left: (cropRect.x + cropRect.width) * scale, right: 0, height: cropRect.height * scale },
            ].map((s, i) => (
              <div key={i} className="absolute bg-black/50" style={s} />
            ))}
          </div>
        )}

        {/* Layer 3: Interaction overlay (Listens for tool clicks and drags on the background) */}
        <div
          ref={overlayRef}
          className="absolute inset-0 z-10"
          style={{ cursor: CURSORS[activeTool] ?? 'default', userSelect: 'none' }}
          onClick={activeTool === 'addtext' ? (e) => {
            if (!overlayRef.current || transientText) return;
            const r = overlayRef.current.getBoundingClientRect();
            setTransientText({ x: (e.clientX - r.left) / scale, y: (e.clientY - r.top) / scale });
          } : handlers.onClick}
          onMouseDown={isDragTool ? handlers.onMouseDown : undefined}
          onMouseMove={isDragTool ? handlers.onMouseMove : undefined}
          onMouseUp={isDragTool ? handlers.onMouseUp : undefined}
          onMouseLeave={isDragTool ? handlers.onMouseLeave : undefined}
        >
          {displayRects.map((rect, i) => (
            <div
              key={i}
              className="absolute pointer-events-none"
              style={{
                left: rect.x * scale, top: rect.y * scale,
                width: rect.width * scale, height: rect.height * scale,
                background: SEL_COLOR[activeTool] ?? 'rgba(74,144,226,0.2)',
                border: activeTool === 'crop' ? '2px dashed #f97316' : 'none',
                borderRadius: 1,
              }}
            />
          ))}
        </div>

        {/* Layer 4: Annotations (z-20 sits ABOVE the interaction layer, so it receives clicks first) */}
        {annotations.map(node => (
          <NodeOverlay 
            key={node.id} 
            node={node} 
            scale={scale} 
            activeTool={activeTool}
            onUpdate={handleNodeUpdate}
          />
        ))}

        {/* Layer 5: Transient inline text box (Top-most) */}
        {transientText && (
          <textarea
            autoFocus
            placeholder="Type here..."
            className="absolute z-50 bg-white/90 border-2 border-[#4a90e2] outline-none text-black p-1 shadow-md resize"
            style={{
              left: transientText.x * scale,
              top: transientText.y * scale,
              minWidth: 150,
              minHeight: 30,
              fontSize: 12 * scale,
              lineHeight: 1.2
            }}
            onMouseDown={e => e.stopPropagation()} 
            onKeyDown={(e) => {
              if (e.key === 'Escape') setTransientText(null);
            }}
            onBlur={async (e) => {
              const text = e.target.value;
              setTransientText(null);
              if (!text.trim()) return;
              try {
                const width = e.target.offsetWidth / scale;
                const height = e.target.offsetHeight / scale;
                const res = await engineApi.addTextAnnotation(
                  pageNode.id, text, transientText.x, transientText.y, width, height
                );
                if (res?.node) {
                  setAnnotations(p => [...p, res.node]);
                  onAnnotationAdded?.();
                }
              } catch (err) { console.error(err); }
            }}
          />
        )}
      </div>

      {/* Crop confirm bar */}
      {cropRect && (
        <div className="absolute z-30 flex gap-2" style={{ bottom: fullDimensions.height - (cropRect.y + cropRect.height) * scale + 10, left: '50%', transform: 'translateX(-50%)' }}>
          <button onClick={() => withBusy(async () => { await engineApi.cropPage(pageNode.id, cropRect.x, cropRect.y, cropRect.width, cropRect.height); clearSelection(); await onDocumentChanged?.(); })}
            className="h-7 px-4 bg-green-500 text-[#0a1f17] text-xs font-semibold rounded-md hover:bg-green-400 transition-colors">
            ✓ Apply
          </button>
          <button onClick={clearSelection}
            className="h-7 px-3 bg-[#2d3338] text-gray-300 text-xs border border-white/10 rounded-md hover:bg-[#3d4449] transition-colors">
            Cancel
          </button>
        </div>
      )}

      {/* Page number badge */}
      <div className="absolute bottom-2 right-2.5 bg-[#1e2327]/70 backdrop-blur-sm text-white text-[10px] font-semibold font-mono px-1.5 py-0.5 rounded-full pointer-events-none z-20">
        {pageIndex + 1}
      </div>

      {/* Busy overlay */}
      {busy && (
        <div className="absolute inset-0 bg-black/10 flex items-center justify-center z-50">
          <div className="bg-[#2d3338] text-white text-xs font-semibold px-4 py-2 rounded-lg border border-white/10 shadow-xl">
            Working…
          </div>
        </div>
      )}

      <CopyToast visible={showToast} />
    </div>
  );
}

// ── Annotation overlay ────────────────────────────────────────────────────────
function NodeOverlay({ 
  node, scale, activeTool, onUpdate 
}: { 
  node: AnnotationNode; scale: number; activeTool?: ToolId; onUpdate?: (id: string, updates: Partial<AnnotationNode>) => void 
}) {
  const [isDragging, setIsDragging] = useState(false);
  const [localPos, setLocalPos] = useState({ x: node.bbox?.x || 0, y: node.bbox?.y || 0 });

  const dragRef = useRef({ isDragging: false, startX: 0, startY: 0, initialNodeX: 0, initialNodeY: 0 });

  useEffect(() => {
    if (!dragRef.current.isDragging && node.bbox) {
      setLocalPos({ x: node.bbox.x, y: node.bbox.y });
    }
  }, [node.bbox]);

  if (!node.bbox) return null;

  const isEditable = node.node_type === 'text' && (activeTool === 'select' || activeTool === 'addtext' || activeTool === 'edittext');

  const handlePointerDown = (e: React.PointerEvent) => {
    if (!isEditable) return;
    e.stopPropagation(); 
    e.preventDefault(); 

    setIsDragging(true);
    dragRef.current = {
      isDragging: true,
      startX: e.clientX,
      startY: e.clientY,
      initialNodeX: localPos.x,
      initialNodeY: localPos.y
    };

    const handlePointerMove = (moveEv: PointerEvent) => {
      if (!dragRef.current.isDragging) return;
      const dx = (moveEv.clientX - dragRef.current.startX) / scale;
      const dy = (moveEv.clientY - dragRef.current.startY) / scale;
      setLocalPos({
        x: dragRef.current.initialNodeX + dx,
        y: dragRef.current.initialNodeY + dy
      });
    };

    const handlePointerUp = (upEv: PointerEvent) => {
      if (!dragRef.current.isDragging) return;
      dragRef.current.isDragging = false;
      setIsDragging(false);

      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);

      const dx = (upEv.clientX - dragRef.current.startX) / scale;
      const dy = (upEv.clientY - dragRef.current.startY) / scale;

      if (onUpdate && node.bbox) {
        onUpdate(node.id, {
          ...node,
          bbox: { ...node.bbox, x: dragRef.current.initialNodeX + dx, y: dragRef.current.initialNodeY + dy }
        });
      }
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
  };

  const style: React.CSSProperties = {
    position: 'absolute',
    zIndex: 20,
    left: localPos.x * scale, 
    top: localPos.y * scale,
    // Fail-safes to ensure the box is never 0 width/height
    width: Math.max((node.bbox.width || 100) * scale, 10), 
    height: Math.max((node.bbox.height || 30) * scale, 10), 
    pointerEvents: isEditable ? 'auto' : 'none',
    cursor: isEditable ? (isDragging ? 'grabbing' : 'grab') : 'default',
    outline: isEditable ? '1px dashed rgba(74,144,226,0.6)' : 'none',
    background: isEditable ? 'rgba(0,0,0,0.01)' : 'transparent', 
  };

  if (node.node_type === 'text') {
    return (
      <div style={style} onPointerDown={handlePointerDown}>
        <span style={{ fontSize: (node.font_size ?? 12) * scale, fontFamily: node.font_family, color: node.color ?? '#000', pointerEvents: 'none', userSelect: 'none' }}>
          {node.text_content}
        </span>
      </div>
    );
  }
  
  if (node.node_type === 'highlight') {
    style.pointerEvents = 'none';
    if (node.color === '#000000') return <div style={{ ...style, background: '#000', borderRadius: 1 }} />;
    return <div style={{ ...style, background: node.color ?? '#f59e0b', opacity: node.opacity ?? 0.42, borderRadius: 1, mixBlendMode: 'multiply' }} />;
  }
  
  return null;
}

// ── Canvas (document area) ────────────────────────────────────────────────────
export function Canvas({
  pdfDoc, documentState, activeTool = 'select', scale = 1.5,
  onAnnotationAdded, onDocumentChanged, onTextSelected, pageRefs,
}: CanvasProps) {
  return (
    <div className="flex-1 bg-[#353a40] overflow-auto flex flex-col items-center pt-8 pb-8 px-4">
      {!documentState ? (
        <div className="flex flex-col items-center justify-center h-full gap-5 select-none">
          <div className="w-16 h-16 bg-[#2d3338] rounded-xl flex items-center justify-center text-3xl border border-white/[0.05] shadow-2xl">📄</div>
          <div className="text-center">
            <div className="text-base font-semibold text-white mb-1">Open a document to begin</div>
            <div className="text-sm text-gray-400">File → Open,  or press Ctrl+O</div>
          </div>
          <div className="flex flex-wrap gap-1.5 justify-center max-w-xs">
            {['Highlight · Redact', 'Add Text · Images', 'Reorder · Rotate', 'Read Aloud · Export'].map(f => (
              <span key={f} className="text-[11px] text-gray-500 bg-[#2d3338] border border-white/[0.05] rounded-full px-3 py-1">{f}</span>
            ))}
          </div>
        </div>
      ) : (
        documentState.children?.map((page, i) => (
          <div
            key={page.id}
            ref={el => { if (pageRefs) pageRefs.current[i] = el; }}
          >
            <PageRenderer
              pageNode={page}
              pdfDoc={pdfDoc!}
              pageIndex={i}
              totalPages={documentState.children?.length ?? 1}
              scale={scale}
              activeTool={activeTool}
              onAnnotationAdded={onAnnotationAdded}
              onDocumentChanged={onDocumentChanged}
              onTextSelected={onTextSelected}
            />
          </div>
        ))
      )}
    </div>
  );
}