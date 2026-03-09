// frontend/src/api/client.ts

import axios from 'axios';
import type { TextRun } from '../types/textProps';

const API_BASE = 'http://localhost:8000/api';

export const engineApi = {
  // --- Document ---
  uploadDocument: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await axios.post(`${API_BASE}/document/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },
  getDocumentState: async () => (await axios.get(`${API_BASE}/document`)).data,
  exportDocument:   async (outputPath: string) => (await axios.post(`${API_BASE}/document/export`, { output_path: outputPath })).data,
  undo: async () => axios.post(`${API_BASE}/undo`),
  redo: async () => axios.post(`${API_BASE}/redo`),

  // --- Pages ---
  rotatePage: async (pageId: string, degrees = 90) =>
    (await axios.post(`${API_BASE}/pages/${pageId}/rotate`, { degrees })).data,
  deletePage: async (pageId: string) =>
    (await axios.delete(`${API_BASE}/pages/${pageId}`)).data,
  movePage: async (pageId: string, newIndex: number) =>
    (await axios.post(`${API_BASE}/pages/${pageId}/move`, { new_index: newIndex })).data,
  cropPage: async (pageId: string, x: number, y: number, width: number, height: number) =>
    (await axios.post(`${API_BASE}/pages/${pageId}/crop`, { x, y, width, height })).data,
  clearCrop: async (pageId: string) =>
    (await axios.delete(`${API_BASE}/pages/${pageId}/crop`)).data,
  getPageChars: async (pageId: string) =>
    (await axios.get(`${API_BASE}/pages/${pageId}/chars`)).data.chars,

  // --- Annotations ---
  addTextAnnotation: async (
    pageId:     string,
    text:       string,
    x:          number,
    y:          number,
    width  =    200,
    height =    30,
    fontFamily= 'Helvetica',
    fontSize=   12,
    color=      '#000000',
    bold=       false,
    italic=     false,
    runs:       TextRun[] = [],
  ) => {
    const response = await axios.post(`${API_BASE}/annotations/text`, {
      page_id:     pageId,
      text,
      x, y, width, height,
      font_family: fontFamily,
      font_size:   fontSize,
      color,
      bold,
      italic,
      runs: runs.map(r => ({
        text:        r.text,
        bold:        r.bold        ?? false,
        italic:      r.italic      ?? false,
        font_family: r.fontFamily  ?? fontFamily,
        font_size:   r.fontSize    ?? fontSize,
        color:       r.color       ?? color,
      })),
    });
    return response.data;
  },

  updateAnnotation: async (
    nodeId:     string,
    updates:    Record<string, unknown> & { runs?: TextRun[] },
  ) => {
    // Remap camelCase runs fields to snake_case for the backend
    const payload = { ...updates };
    if (payload.runs) {
      payload.runs = (payload.runs as TextRun[]).map(r => ({
        text:        r.text,
        bold:        r.bold        ?? false,
        italic:      r.italic      ?? false,
        font_family: r.fontFamily  ?? 'Helvetica',
        font_size:   r.fontSize    ?? 12,
        color:       r.color       ?? '#000000',
      })) as unknown as TextRun[];
    }
    return (await axios.patch(`${API_BASE}/annotations/${nodeId}`, payload)).data;
  },

  addHighlight: async (pageId: string, x: number, y: number, width: number, height: number, color = '#FFFF00') =>
    (await axios.post(`${API_BASE}/annotations/highlight`, { page_id: pageId, x, y, width, height, color })).data,

  // --- Plugins ---
  applyRedaction: async (pageId: string, rects: { x: number; y: number; width: number; height: number }[]) =>
    (await axios.post(`${API_BASE}/plugins/redact/apply`, {
      page_id: pageId,
      rects: rects.map(r => ({ x: r.x, y: r.y, width: r.width, height: r.height })),
    })).data,
  runOcr: async (pageId: string, language = 'eng') =>
    (await axios.post(`${API_BASE}/plugins/ocr/process`, { page_id: pageId, language })).data,

  // --- TTS ---
  ttsPlay: async (text: string, speed = 1.0) =>
    (await axios.post(`${API_BASE}/plugins/tts/play`, { text, speed })).data,
  ttsStop: async () =>
    (await axios.post(`${API_BASE}/plugins/tts/stop`)).data,
};