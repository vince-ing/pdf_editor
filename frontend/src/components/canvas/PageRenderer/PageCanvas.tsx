// frontend/src/components/canvas/PageRenderer/PageCanvas.tsx
// Renders the pdf.js canvas element. Pure display, no logic.

import React from 'react';

interface PageCanvasProps {
  canvasRef: React.RefObject<HTMLCanvasElement>;
  width:     number;
  height:    number;
}

export function PageCanvas({ canvasRef, width, height }: PageCanvasProps) {
  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 pointer-events-none"
      style={{ width, height }}
    />
  );
}