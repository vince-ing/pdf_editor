// frontend/src/components/canvas/PageRenderer/AnnotationLayer.tsx
// Renders persisted annotation overlays and the in-progress transient text box.

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { NodeOverlay } from '../NodeOverlay';
import { TransientTextBox } from '../TransientTextBox';
import { textTool } from '../../../core/tools/TextTool';
import type { TextProps } from '../../../types/textProps';
import type { ToolId } from '../../toolbar/Toolbar';
import type { AnnotationNode, PageNode } from '../types';

interface AnnotationLayerProps {
  pageNode:          PageNode;
  annotations:       AnnotationNode[];
  scale:             number;
  activeTool:        ToolId;
  textProps:         TextProps;
  onTextPropsChange?: (p: TextProps) => void;
  onNodeUpdate:      (id: string, updates: Partial<AnnotationNode & { runs: any[] }>) => void;
  onNodeDelete:      (id: string) => void;
  onRegisterActiveBlur:     (fn: (() => void) | null) => void;
  onRegisterClearTransient: (fn: () => void) => void;
  onTextCommit:      (runs: any[], plain: string) => void;
}

export function AnnotationLayer({
  pageNode, annotations, scale, activeTool, textProps,
  onTextPropsChange, onNodeUpdate, onNodeDelete,
  onRegisterActiveBlur, onRegisterClearTransient, onTextCommit,
}: AnnotationLayerProps) {
  const transientBlurRef = useRef<(() => void) | null>(null);

  const [transientPos, setTransientPos] = useState<{
    x: number; y: number; w?: number; h?: number; isDrawing?: boolean;
  } | null>(null);

  // Stable callback ref so the parent's ref assignment never triggers
  // a re-render loop regardless of how often onRegisterClearTransient changes.
  const clearTransient = useCallback(() => setTransientPos(null), []);
  const onRegisterClearTransientRef = useRef(onRegisterClearTransient);
  useEffect(() => { onRegisterClearTransientRef.current = onRegisterClearTransient; }, [onRegisterClearTransient]);

  // Register clear function exactly once (or when the stable callback
  // identity changes — which should be never in practice).
  useEffect(() => {
    onRegisterClearTransientRef.current(clearTransient);
  }, [clearTransient]);

  // Subscribe to TextTool position events for this page only
  useEffect(() => {
    const unsubPos = textTool.onPositionStateChange((pos) => {
      if (!pos) {
        setTransientPos(null);
      } else if (pos.pageId === pageNode.id) {
        setTransientPos({ x: pos.x, y: pos.y, w: pos.w, h: pos.h, isDrawing: pos.isDrawing });
      }
    });
    const unsubCommit = textTool.onCommitRequest(() => transientBlurRef.current?.());
    return () => { unsubPos(); unsubCommit(); };
  }, [pageNode.id]);

  return (
    <>
      {annotations.map(node => (
        <NodeOverlay
          key={node.id}
          node={node}
          scale={scale}
          activeTool={activeTool}
          textProps={textProps}
          onPropsChange={onTextPropsChange}
          onUpdate={onNodeUpdate}
          onDelete={onNodeDelete}
          onRegisterBlur={fn => onRegisterActiveBlur(fn)}
        />
      ))}

      {transientPos && (
        <TransientTextBox
          initialX={transientPos.x}
          initialY={transientPos.y}
          initialW={transientPos.w}
          initialH={transientPos.h}
          isDrawing={transientPos.isDrawing}
          scale={scale}
          textProps={textProps}
          onPropsChange={onTextPropsChange}
          blurRef={transientBlurRef}
          onCommit={onTextCommit}
          onCancel={() => {
            setTransientPos(null);
            textTool.notifyCommitted();
          }}
        />
      )}
    </>
  );
}