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
  runs?:        TextRun[];
}

export interface PageNode {
  id: string; page_number?: number; rotation?: number;
  metadata?: { width: number; height: number };
  crop_box?: { x: number; y: number; width: number; height: number };
  children?: AnnotationNode[];
}

export interface DocumentState { 
  children?: PageNode[]; 
  file_name?: string; 
}