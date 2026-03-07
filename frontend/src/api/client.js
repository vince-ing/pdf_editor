import axios from 'axios';

const API_BASE = 'http://localhost:8000/api'; // Update if your port changes

export const engineApi = {
    // --- Document & State ---
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
    loadDocument: async (filePath) => {
        const response = await axios.post(`${API_BASE}/document/load`, { file_path: filePath });
        return response.data;
    },
    undo: async () => await axios.post(`${API_BASE}/undo`),
    redo: async () => await axios.post(`${API_BASE}/redo`),

    // --- Page Operations ---
    rotatePage: async (pageId, degrees = 90) => {
        const response = await axios.post(`${API_BASE}/pages/${pageId}/rotate`, { degrees });
        return response.data;
    },

    // --- Plugins ---
    runOcr: async (pageId, language = 'eng') => {
        const response = await axios.post(`${API_BASE}/plugins/ocr/process`, { page_id: pageId, language });
        return response.data;
    }
};