// frontend/src/api/normalize.ts
//
// Normalizes raw API responses into the frontend's canonical types.
// All snake_case → camelCase conversion happens HERE and nowhere else.
// Downstream code (components, hooks) can assume clean camelCase types.

import type { AnnotationNode, PageNode, DocumentState } from '../components/canvas/types';

function normalizeRun(r: any) {
  return {
    text:       r.text       ?? '',
    bold:       r.bold       ?? false,
    italic:     r.italic     ?? false,
    fontFamily: r.fontFamily ?? r.font_family ?? 'Helvetica',
    fontSize:   r.fontSize   ?? r.font_size   ?? 12,
    color:      r.color      ?? '#000000',
  };
}

function normalizeAnnotation(raw: any): AnnotationNode {
  const runs = Array.isArray(raw.runs) && raw.runs.length > 0
    ? raw.runs.map(normalizeRun)
    : [];

  return {
    id:           raw.id,
    node_type:    raw.node_type,
    bbox:         raw.bbox,
    color:        raw.color,
    opacity:      raw.opacity,
    text_content: raw.text_content,
    // Normalize top-level font fields
    font_size:    raw.font_size   ?? raw.fontSize,
    font_family:  raw.font_family ?? raw.fontFamily,
    bold:         raw.bold,
    italic:       raw.italic,
    runs,
    // Path-specific
    points:       raw.points,
    thickness:    raw.thickness,
  };
}

function normalizePage(raw: any): PageNode {
  return {
    id:          raw.id,
    page_number: raw.page_number,
    rotation:    raw.rotation,
    metadata:    raw.metadata,
    crop_box:    raw.crop_box,
    children:    Array.isArray(raw.children)
      ? raw.children.map(normalizeAnnotation)
      : [],
  };
}

export function normalizeDocumentState(raw: any): DocumentState {
  return {
    node_type: raw.node_type,   // preserve so callers can still guard on it
    file_name: raw.file_name,
    file_size: raw.file_size,
    children:  Array.isArray(raw.children)
      ? raw.children.map(normalizePage)
      : [],
  };
}