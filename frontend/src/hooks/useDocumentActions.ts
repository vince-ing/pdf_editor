// frontend/src/hooks/useDocumentActions.ts
import { useState, useCallback } from 'react';
import { engineApi } from '../api/client';
import { useTts } from './useTts';
import type { DocumentState } from '../components/canvas/types';
import type * as pdfjsLib from 'pdfjs-dist';

interface UseDocumentActionsArgs {
  activeTabId:          string | null;
  documentState:        DocumentState | null;
  pdfDoc:               pdfjsLib.PDFDocumentProxy | null;
  activePage:           number;
  refreshDocumentState: () => Promise<void>;
}

export function useDocumentActions({
  activeTabId,
  documentState,
  pdfDoc,
  activePage,
  refreshDocumentState,
}: UseDocumentActionsArgs) {
  const { tts, speak, stop: ttsStop, pauseResume, setSpeed } = useTts();

  // Owned here because only handleReadSelection reads it; exposed so
  // Canvas can call setLastSelectedText when the user selects text.
  const [lastSelectedText, setLastSelectedText] = useState('');

  const handleUndo = useCallback(async () => {
    if (!activeTabId) return;
    try {
      await engineApi.undo(activeTabId);
      await refreshDocumentState();
    } catch {
      alert('Nothing to undo!');
    }
  }, [activeTabId, refreshDocumentState]);

  const handleRedo = useCallback(async () => {
    if (!activeTabId) return;
    try {
      await engineApi.redo(activeTabId);
      await refreshDocumentState();
    } catch {
      alert('Nothing to redo!');
    }
  }, [activeTabId, refreshDocumentState]);

  const handleExportPdf = useCallback(async () => {
    if (!documentState || !activeTabId) return;
    try {
      const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';
      const res = await fetch(`${apiBase}/document/download`, {
        headers: { 'X-Session-Id': activeTabId },
      });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = Object.assign(document.createElement('a'), {
        href:     url,
        download: `edited_${documentState.file_name}`,
      });
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      alert('Export failed: ' + err.message);
    }
  }, [documentState, activeTabId]);

  const handleReadPage = useCallback(async () => {
    if (!documentState || !pdfDoc) return alert('Open a document first.');
    const pageNode = documentState.children?.[activePage];
    if (!pageNode || !activeTabId) return;
    try {
      const chars = await engineApi.getPageChars(pageNode.id, activeTabId);
      const text  = chars.map((c: { text: string }) => c.text).join('');
      if (!text.trim()) return alert('No readable text found. Try OCR first.');
      await speak(text, `Reading page ${activePage + 1}`);
    } catch (err: any) {
      alert('TTS failed: ' + err.message);
    }
  }, [documentState, pdfDoc, activePage, activeTabId, speak]);

  const handleReadSelection = useCallback(async () => {
    if (!lastSelectedText?.trim()) return alert('Select text first using the Select tool.');
    await speak(lastSelectedText.trim(), 'Reading selection');
  }, [lastSelectedText, speak]);

  return {
    handleUndo, handleRedo, handleExportPdf,
    handleReadPage, handleReadSelection,
    lastSelectedText, setLastSelectedText,
    tts, ttsStop, pauseResume, setSpeed,
  };
}