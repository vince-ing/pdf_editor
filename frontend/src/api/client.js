import axios from 'axios';

const API_BASE = 'http://localhost:8000/api';

export const engineApi = {

    cropPage: async (pageId, x, y, width, height) => {
    const res = await fetch(`http://localhost:8000/api/pages/${pageId}/crop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ x, y, width, height }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
    },

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
    exportDocument: async (outputPath) => {
        const response = await axios.post(`${API_BASE}/document/export`, { output_path: outputPath });
        return response.data;
    },
    undo: async () => await axios.post(`${API_BASE}/undo`),
    redo: async () => await axios.post(`${API_BASE}/redo`),

    // --- Pages ---
    rotatePage: async (pageId, degrees = 90) => {
        const response = await axios.post(`${API_BASE}/pages/${pageId}/rotate`, { degrees });
        return response.data;
    },
    deletePage: async (pageId) => {
        const response = await axios.delete(`${API_BASE}/pages/${pageId}`);
        return response.data;
    },
    movePage: async (pageId, newIndex) => {
        const response = await axios.post(`${API_BASE}/pages/${pageId}/move`, { new_index: newIndex });
        return response.data;
    },
    cropPage: async (pageId, x, y, width, height) => {
        const response = await axios.post(`${API_BASE}/pages/${pageId}/crop`, { x, y, width, height });
        return response.data;
    },
    clearCrop: async (pageId) => {
        const response = await axios.delete(`${API_BASE}/pages/${pageId}/crop`);
        return response.data;
    },
    getPageChars: async (pageId) => {
        const response = await axios.get(`${API_BASE}/pages/${pageId}/chars`);
        return response.data.chars;
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