import React, { useEffect, useRef, useState } from 'react';

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

export const PageRenderer = ({ pageNode, pdfDoc, pageIndex }) => {
    const canvasRef = useRef(null);
    const [dimensions, setDimensions] = useState({
        width: pageNode.metadata?.width || 612,
        height: pageNode.metadata?.height || 792
    });

    const scale = 1.5;

    useEffect(() => {
        if (!pdfDoc) return;
        let isMounted = true;
        let renderTask = null;

        const renderPage = async () => {
            try {
                // pageIndex is 0-based from the array; PDF.js getPage is 1-based
                const pageNum = pageIndex + 1;

                if (pageNum < 1 || pageNum > pdfDoc.numPages) {
                    console.error(`Page ${pageNum} out of range (doc has ${pdfDoc.numPages} pages)`);
                    return;
                }

                const page = await pdfDoc.getPage(pageNum);
                if (!isMounted) return;

                const rotation = pageNode.rotation ?? 0;
                const viewport = page.getViewport({ scale, rotation });
                setDimensions({ width: viewport.width, height: viewport.height });

                const canvas = canvasRef.current;
                if (!canvas) return;

                const context = canvas.getContext('2d');
                canvas.height = viewport.height;
                canvas.width = viewport.width;

                renderTask = page.render({ canvasContext: context, viewport });
                await renderTask.promise;
                console.log(`Page ${pageNum} rendered successfully.`);

            } catch (error) {
                if (error?.name !== 'RenderingCancelledException') {
                    console.error('PDF Render Error:', error);
                }
            }
        };

        renderPage();

        return () => {
            isMounted = false;
            renderTask?.cancel();
        };
    }, [pdfDoc, pageIndex, pageNode.rotation, scale]);

    return (
        <div style={{
            position: 'relative',
            width: `${dimensions.width}px`,
            height: `${dimensions.height}px`,
            flexShrink: 0,
            backgroundColor: 'white',
            boxShadow: '0 4px 8px rgba(0,0,0,0.1)',
            margin: '20px auto',
            overflow: 'hidden'
        }}>
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