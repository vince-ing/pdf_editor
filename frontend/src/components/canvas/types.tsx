// frontend/src/components/canvas/types.tsx
import type { TextRun } from '../../types/textProps';

export interface AnnotationNode {
  id:           string;
  node_type:    string;
  bbox?:        { x: number; y: number; width: number; height: number };
  color?:       string;
  opacity?:     number;
  text_content?: string;
  font_size?:   number;
  font_family?: string;
  bold?:        boolean;
  italic?:      boolean;
  // runs are always normalized to camelCase by normalize.ts
  runs?:        TextRun[];
  // path-specific
  points?:      { x: number; y: number }[];
  thickness?:   number;
}

export interface PageNode {
  id: string; page_number?: number; rotation?: number;
  metadata?: { width: number; height: number };
  crop_box?: { x: number; y: number; width: number; height: number };
  children?: AnnotationNode[];
}

export interface DocumentState { 
  node_type?: string;
  children?: PageNode[]; 
  file_name?: string;
  file_size?: number;
}