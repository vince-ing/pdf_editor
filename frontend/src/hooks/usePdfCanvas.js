// frontend/src/hooks/usePdfCanvas.js
import { useEffect, useRef, useState } from 'react';

export const usePdfCanvas = ({ pdfDoc, pageNode, pageIndex, scale, localRotation }) => {
    const canvasRef = useRef(null);
    
    // Explicitly track full page dimensions, distinct from cropped visible bounds
    const [fullDimensions, setFullDimensions] = useState({
        width:  (pageNode?.metadata?.width  || 612) * scale,
        height: (pageNode?.metadata?.height || 792) * scale,
    });

    useEffect(() => {
        if (!pdfDoc) return;
        
        let alive = true;
        let renderTask = null;
        
        const renderPage = async () => {
            try {
                // PDF.js uses 1-based indexing
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
                
                renderTask = page.render({ 
                    canvasContext: canvas.getContext('2d'), 
                    viewport: vp 
                });
                
                await renderTask.promise;
            } catch (err) { 
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