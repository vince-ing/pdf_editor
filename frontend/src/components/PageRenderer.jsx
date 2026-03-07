import React, { useEffect, useRef, useState } from 'react';
import * as pdfjsLib from 'pdfjs-dist';

// THE FIX: Build the worker natively using Vite and hand the active port to the engine
import PdfWorker from 'pdfjs-dist/build/pdf.worker.mjs?worker';
pdfjsLib.GlobalWorkerOptions.workerPort = new PdfWorker();

const NodeOverlay = ({ node, scale = 1.0 }) => {
    if (!node.bbox) return null;

    const style = {
        position: 'absolute',
        left: `${node.bbox.x * scale}px`,
        top: `${node.bbox.y * scale}px`,
        width: `${node.bbox.width * scale}px`,
        height: `${node.bbox.height * scale}px`,
        pointerEvents: 'auto', 
    };

    switch (node.node_type) {
        case 'text':
            return (
                <div style={{ 
                    ...style, 
                    color: node.color || 'transparent', 
                    fontSize: `${node.font_size * scale}px`, 
                    fontFamily: node.font_family,
                    border: '1px solid rgba(0,0,0,0.1)', 
                    cursor: 'text'
                }}>
                    <span style={{ color: 'transparent' }}>{node.text_content}</span>
                </div>
            );
        case 'highlight':
            return (
                <div style={{ 
                    ...style, 
                    backgroundColor: node.color, 
                    opacity: node.opacity || 0.4, 
                    mixBlendMode: 'multiply' 
                }} />
            );
        default:
            return null;
    }
};

export const PageRenderer = ({ pageNode, documentUrl }) => {
    const canvasRef = useRef(null);
    const [dimensions, setDimensions] = useState({ 
        width: pageNode.metadata?.width || 612, 
        height: pageNode.metadata?.height || 792 
    });
    
    const scale = 1.5; 

    useEffect(() => {
        if (!documentUrl) return;
        let isMounted = true;

        const renderPage = async () => {
            try {
                const loadingTask = pdfjsLib.getDocument(documentUrl);
                const pdf = await loadingTask.promise;
                if (!isMounted) return;
                
                const page = await pdf.getPage(pageNode.page_number + 1); 
                if (!isMounted) return;
                
                const viewport = page.getViewport({ scale: scale, rotation: pageNode.rotation }); 
                setDimensions({ width: viewport.width, height: viewport.height });

                const canvas = canvasRef.current;
                if (!canvas) return;
                
                const context = canvas.getContext('2d');
                canvas.height = viewport.height;
                canvas.width = viewport.width;

                const renderContext = {
                    canvasContext: context,
                    viewport: viewport
                };

                await page.render(renderContext).promise;
                console.log(`Page ${pageNode.page_number + 1} rendered successfully!`);
                
            } catch (error) {
                console.error("PDF Render Error:", error);
            }
        };

        renderPage();

        return () => {
            isMounted = false;
        };
    }, [documentUrl, pageNode.page_number, pageNode.rotation, scale]);

    return (
        <div 
            className="page-container" 
            style={{ 
                position: 'relative', 
                width: `${dimensions.width}px`, 
                height: `${dimensions.height}px`, 
                minWidth: `${dimensions.width}px`,
                minHeight: `${dimensions.height}px`,
                flexShrink: 0,
                backgroundColor: 'white',
                boxShadow: '0 4px 8px rgba(0,0,0,0.1)',
                margin: '20px auto',
                overflow: 'hidden' 
            }}
        >
            <canvas 
                ref={canvasRef} 
                style={{ 
                    position: 'absolute', 
                    top: 0, 
                    left: 0,
                    width: `${dimensions.width}px`,
                    height: `${dimensions.height}px`,
                    pointerEvents: 'none' 
                }} 
            />
            
            {pageNode.children && pageNode.children.map(child => (
                <NodeOverlay key={child.id} node={child} scale={scale} />
            ))}
        </div>
    );
};