// frontend/src/hooks/useZoom.ts
import { useCallback } from 'react';

const MIN_SCALE = 0.25;
const MAX_SCALE = 4.0;
const STEP      = 0.25;

export function useZoom(setScale: (updater: (prev: number) => number) => void) {
  const zoomIn    = useCallback(() => setScale(s => Math.min(+(s + STEP).toFixed(2), MAX_SCALE)), [setScale]);
  const zoomOut   = useCallback(() => setScale(s => Math.max(+(s - STEP).toFixed(2), MIN_SCALE)), [setScale]);
  const zoomReset = useCallback(() => setScale(() => 1.0), [setScale]);

  return { zoomIn, zoomOut, zoomReset };
}