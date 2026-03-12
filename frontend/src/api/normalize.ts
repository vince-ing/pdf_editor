// frontend/src/api/normalize.ts
//
// Normalizes raw API responses into the frontend's canonical types.
// All snake_case → camelCase conversion happens HERE and nowhere else.
// Downstream code (components, hooks) can assume clean camelCase types.

import type { AnnotationNode, PageNode, DocumentState } from '../components/canvas/types';
import type { TextRun } from '../types/textProps';

// ── Raw API shapes (what the server actually sends) ───────────────────────────
// Using `unknown`-safe intermediates means TypeScript will flag any accidental
// field access that isn't explicitly guarded, unlike `any`.

interface RawRun {
  text?:        unknown;
  bold?:        unknown;
  italic?:      unknown;
  fontFamily?:  unknown;
  font_family?: unknown;
  fontSize?:    unknown;
  font_size?:   unknown;
  color?:       unknown;
}

interface RawAnnotation {
  id?:           unknown;
  node_type?:    unknown;
  bbox?:         unknown;
  color?:        unknown;
  opacity?:      unknown;
  text_content?: unknown;
  font_size?:    unknown;
  fontSize?:     unknown;
  font_family?:  unknown;
  fontFamily?:   unknown;
  bold?:         unknown;
  italic?:       unknown;
  runs?:         unknown;
  points?:       unknown;
  thickness?:    unknown;
}

interface RawPage {
  id?:          unknown;
  page_number?: unknown;
  rotation?:    unknown;
  metadata?:    unknown;
  crop_box?:    unknown;
  children?:    unknown;
}

interface RawDocument {
  node_type?: unknown;
  file_name?: unknown;
  file_size?: unknown;
  children?:  unknown;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function asString(v: unknown, fallback: string): string {
  return typeof v === 'string' ? v : fallback;
}

function asNumber(v: unknown, fallback: number): number {
  return typeof v === 'number' ? v : fallback;
}

function asBool(v: unknown, fallback: boolean): boolean {
  return typeof v === 'boolean' ? v : fallback;
}

// ── Normalizers ───────────────────────────────────────────────────────────────

function normalizeRun(r: RawRun): TextRun {
  return {
    text:       asString(r.text,       ''),
    bold:       asBool  (r.bold,       false),
    italic:     asBool  (r.italic,     false),
    fontFamily: asString(r.fontFamily ?? r.font_family, 'Helvetica'),
    fontSize:   asNumber(r.fontSize   ?? r.font_size,   12),
    color:      asString(r.color,      '#000000'),
  };
}

function normalizeAnnotation(raw: RawAnnotation): AnnotationNode {
  const rawRuns = Array.isArray(raw.runs) ? (raw.runs as RawRun[]) : [];
  const runs: TextRun[] = rawRuns.length > 0 ? rawRuns.map(normalizeRun) : [];

  return {
    id:           asString(raw.id,        ''),
    node_type:    asString(raw.node_type, ''),
    bbox:         raw.bbox as AnnotationNode['bbox'],
    color:        typeof raw.color   === 'string' ? raw.color   : undefined,
    opacity:      typeof raw.opacity === 'number' ? raw.opacity : undefined,
    text_content: typeof raw.text_content === 'string' ? raw.text_content : undefined,
    font_size:    typeof (raw.font_size ?? raw.fontSize) === 'number'
                    ? (raw.font_size ?? raw.fontSize) as number
                    : undefined,
    font_family:  typeof (raw.font_family ?? raw.fontFamily) === 'string'
                    ? (raw.font_family ?? raw.fontFamily) as string
                    : undefined,
    bold:         typeof raw.bold   === 'boolean' ? raw.bold   : undefined,
    italic:       typeof raw.italic === 'boolean' ? raw.italic : undefined,
    runs,
    points:       Array.isArray(raw.points)
                    ? (raw.points as { x: number; y: number }[])
                    : undefined,
    thickness:    typeof raw.thickness === 'number' ? raw.thickness : undefined,
  };
}

function normalizePage(raw: RawPage): PageNode {
  return {
    id:          asString(raw.id,          ''),
    page_number: typeof raw.page_number === 'number' ? raw.page_number : undefined,
    rotation:    typeof raw.rotation    === 'number' ? raw.rotation    : undefined,
    metadata:    raw.metadata as PageNode['metadata'],
    crop_box:    raw.crop_box as PageNode['crop_box'],
    children:    Array.isArray(raw.children)
      ? (raw.children as RawAnnotation[]).map(normalizeAnnotation)
      : [],
  };
}

export function normalizeDocumentState(raw: RawDocument): DocumentState {
  return {
    node_type: typeof raw.node_type === 'string' ? raw.node_type : undefined,
    file_name: typeof raw.file_name === 'string' ? raw.file_name : undefined,
    file_size: typeof raw.file_size === 'number' ? raw.file_size : undefined,
    children:  Array.isArray(raw.children)
      ? (raw.children as RawPage[]).map(normalizePage)
      : [],
  };
}