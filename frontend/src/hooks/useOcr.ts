// frontend/src/hooks/useOcr.ts
import { useState, useCallback } from 'react';
import { engineApi } from '../api/client';

interface UseOcrProps {
  activeTabId: string | null;
  onSuccess?: () => void;
}

export function useOcr({ activeTabId, onSuccess }: UseOcrProps) {
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runOcr = useCallback(async (pageId: string) => {
    if (!activeTabId) return;
    setIsProcessing(true);
    setError(null);
    try {
      const response = await engineApi.runOcr(pageId, activeTabId);
      if (response.status === 'success') {
        onSuccess?.();
      } else {
        setError(response.message || 'OCR failed');
      }
    } catch (err: any) {
      console.error('OCR Error:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to process OCR.');
    } finally {
      setIsProcessing(false);
    }
  }, [activeTabId, onSuccess]);

  return { runOcr, isProcessing, error };
}