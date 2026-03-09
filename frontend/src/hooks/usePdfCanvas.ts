// frontend/src/hooks/usePdfCanvas.ts
import { useEffect, useRef, useState } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import type { PageNode } from '../components/canvas/types';

interface UsePdfCanvasArgs {
    pdfDoc: pdfjsLib.PDFDocumentProxy | null;
    pageNode: PageNode;
    pageIndex: number;
    scale: number;
    localRotation: number;
}

export const usePdfCanvas = ({ pdfDoc, pageNode, pageIndex, scale, localRotation }: UsePdfCanvasArgs) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    
    const [fullDimensions, setFullDimensions] = useState({
        width:  (pageNode?.metadata?.width  || 612) * scale,
        height: (pageNode?.metadata?.height || 792) * scale,
    });

    useEffect(() => {
        if (!pdfDoc) return;
        
        let alive = true;
        let renderTask: pdfjsLib.RenderTask | null = null;
        
        const renderPage = async () => {
            try {
                const pageNum = (pageNode?.page_number ?? pageIndex) + 1;
                if (pageNum < 1 || pageNum > pdfDoc.numPages) return;
                
                const page = await pdfDoc.getPage(pageNum);
                if (!alive) return;
                
                const dpr = window.devicePixelRatio || 1;
                const vp  = page.getViewport({ scale: scale * dpr, rotation: localRotation });
                
                const canvas = canvasRef.current;
                if (!canvas) return;
                
                canvas.width  = vp.width;
                canvas.height = vp.height;
                
                const cssW = vp.width / dpr;
                const cssH = vp.height / dpr;
                canvas.style.width = `${cssW}px`; 
                canvas.style.height = `${cssH}px`;
                
                setFullDimensions({ width: cssW, height: cssH });
                
                const canvasContext = canvas.getContext('2d');
                if (!canvasContext) return;

                renderTask = page.render({ 
                    canvasContext, 
                    viewport: vp 
                });
                
                await renderTask.promise;
            } catch (err: any) { 
                if (err?.name !== 'RenderingCancelledException') {
                    console.error('[usePdfCanvas] Rendering error:', err);
                }
            }
        };
        
        renderPage();
        
        return () => { 
            alive = false; 
            if (renderTask) {
                renderTask.cancel(); 
            }
        };
    }, [pdfDoc, pageNode, pageIndex, localRotation, scale]);

    return { canvasRef, fullDimensions };
};