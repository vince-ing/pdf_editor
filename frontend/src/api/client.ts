// frontend/src/api/client.ts

import axios from 'axios';
import type { TextRun } from '../types/textProps';

const isProduction = window.location.hostname.includes('vercel.app');

const API_BASE = isProduction 
  ? 'https://vince-ing-pdf-editor-backend.hf.space/api' 
  : 'http://localhost:8000/api';

const s = (sessionId: string) => ({ headers: { 'X-Session-Id': sessionId } });

export const engineApi = {
  // --- Session ---
  closeSession: async (sessionId: string) =>
    (await axios.delete(`${API_BASE}/session`, s(sessionId))).data,

  // --- Document ---
  uploadDocument: async (file: File, sessionId: string) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await axios.post(`${API_BASE}/document/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data', 'X-Session-Id': sessionId },
    });
    return response.data;
  },
  getDocumentState: async (sessionId: string) =>
    (await axios.get(`${API_BASE}/document`, s(sessionId))).data,
  exportDocument: async (outputPath: string, sessionId: string) =>
    (await axios.post(`${API_BASE}/document/export`, { output_path: outputPath }, s(sessionId))).data,
  undo: async (sessionId: string) => axios.post(`${API_BASE}/undo`, {}, s(sessionId)),
  redo: async (sessionId: string) => axios.post(`${API_BASE}/redo`, {}, s(sessionId)),

  // --- Pages ---
  rotatePage: async (pageId: string, sessionId: string, degrees = 90) =>
    (await axios.post(`${API_BASE}/pages/${pageId}/rotate`, { degrees }, s(sessionId))).data,
  deletePage: async (pageId: string, sessionId: string) =>
    (await axios.delete(`${API_BASE}/pages/${pageId}`, s(sessionId))).data,
  movePage: async (pageId: string, newIndex: number, sessionId: string) =>
    (await axios.post(`${API_BASE}/pages/${pageId}/move`, { new_index: newIndex }, s(sessionId))).data,
  cropPage: async (pageId: string, x: number, y: number, width: number, height: number, sessionId: string) =>
    (await axios.post(`${API_BASE}/pages/${pageId}/crop`, { x, y, width, height }, s(sessionId))).data,
  clearCrop: async (pageId: string, sessionId: string) =>
    (await axios.delete(`${API_BASE}/pages/${pageId}/crop`, s(sessionId))).data,
  getPageChars: async (pageId: string, sessionId: string) =>
    (await axios.get(`${API_BASE}/pages/${pageId}/chars`, s(sessionId))).data.chars,

  // --- Annotations ---
  addTextAnnotation: async (
    pageId:     string,
    text:       string,
    x:          number,
    y:          number,
    sessionId:  string,
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
    }, s(sessionId));
    return response.data;
  },

  updateAnnotation: async (
    nodeId:     string,
    updates:    Record<string, unknown> & { runs?: TextRun[] },
    sessionId:  string,
  ) => {
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
    return (await axios.patch(`${API_BASE}/annotations/${nodeId}`, payload, s(sessionId))).data;
  },

  deleteAnnotation: async (nodeId: string, pageId: string, sessionId: string) =>
    (await axios.delete(`${API_BASE}/annotations/${nodeId}`, {
      params: { page_id: pageId },
      ...s(sessionId),
    })).data,

  addHighlight: async (
    pageId: string,
    rects: { x: number; y: number; width: number; height: number }[],
    color: string,
    opacity: number,
    sessionId: string,
  ) =>
    (await axios.post(`${API_BASE}/annotations/highlight`, {
      page_id: pageId,
      rects,
      color,
      opacity,
    }, s(sessionId))).data,

  addPathAnnotation: async (
    pageId: string,
    points: { x: number; y: number }[],
    color: string,
    thickness: number,
    opacity: number,
    sessionId: string,
  ) => {
    const response = await axios.post(`${API_BASE}/annotations/path`, {
      page_id: pageId,
      points,
      color,
      thickness,
      opacity,
    }, s(sessionId));
    return response.data;
  },

  // --- Plugins ---
  applyRedaction: async (pageId: string, rects: { x: number; y: number; width: number; height: number }[], sessionId: string) =>
    (await axios.post(`${API_BASE}/plugins/redact/apply`, {
      page_id: pageId,
      rects: rects.map(r => ({ x: r.x, y: r.y, width: r.width, height: r.height })),
    }, s(sessionId))).data,
  runOcr: async (pageId: string, sessionId: string, language = 'eng') =>
    (await axios.post(`${API_BASE}/plugins/ocr/process`, { page_id: pageId, language }, s(sessionId))).data,

  // --- TTS (global, not session-scoped) ---
  ttsPlay: async (text: string, speed = 1.0) =>
    (await axios.post(`${API_BASE}/plugins/tts/play`, { text, speed })).data,
  ttsStop: async () =>
    (await axios.post(`${API_BASE}/plugins/tts/stop`)).data,
};