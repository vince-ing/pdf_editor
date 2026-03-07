import axios from 'axios';

const API_BASE = 'http://localhost:8000/api';

export const engineApi = {
    // --- Document ---
    uploadDocument: async (file) => {
        const formData = new FormData();
        formData.append('file', file);
        const response = await axios.post(`${API_BASE}/document/upload`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
        return response.data;
    },
    getDocumentState: async () => {
        const response = await axios.get(`${API_BASE}/document`);
        return response.data;
    },
    undo: async () => await axios.post(`${API_BASE}/undo`),
    redo: async () => await axios.post(`${API_BASE}/redo`),

    // --- Pages ---
    rotatePage: async (pageId, degrees = 90) => {
        const response = await axios.post(`${API_BASE}/pages/${pageId}/rotate`, { degrees });
        return response.data;
    },

    // --- Annotations ---
    addTextAnnotation: async (pageId, text, x, y, width = 200, height = 30) => {
        const response = await axios.post(`${API_BASE}/annotations/text`, {
            page_id: pageId, text, x, y, width, height
        });
        return response.data;
    },
    addHighlight: async (pageId, x, y, width, height, color = '#FFFF00') => {
        const response = await axios.post(`${API_BASE}/annotations/highlight`, {
            page_id: pageId, x, y, width, height, color
        });
        return response.data;
    },

    // --- Plugins ---
    applyRedaction: async (pageId, x, y, width, height) => {
        const response = await axios.post(`${API_BASE}/plugins/redact/apply`, {
            page_id: pageId,
            rects: [{ x, y, width, height }]
        });
        return response.data;
    },
    runOcr: async (pageId, language = 'eng') => {
        const response = await axios.post(`${API_BASE}/plugins/ocr/process`, { page_id: pageId, language });
        return response.data;
    },
};