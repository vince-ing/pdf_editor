import React, { useEffect, useRef, useState } from 'react';

// Renders a single low-res thumbnail by drawing one page onto a small canvas
const Thumbnail = ({ pdfDoc, pageIndex, isActive, onClick }) => {
    const canvasRef = useRef(null);
    const THUMB_WIDTH = 148; // px — the canvas will scale height to match aspect ratio

    useEffect(() => {
        if (!pdfDoc) return;
        let isMounted = true;
        let renderTask = null;

        const render = async () => {
            try {
                const page = await pdfDoc.getPage(pageIndex + 1);
                if (!isMounted) return;

                const naturalViewport = page.getViewport({ scale: 1 });
                const scale = THUMB_WIDTH / naturalViewport.width;
                const viewport = page.getViewport({ scale });

                const canvas = canvasRef.current;
                if (!canvas) return;

                canvas.width  = viewport.width;
                canvas.height = viewport.height;

                renderTask = page.render({
                    canvasContext: canvas.getContext('2d'),
                    viewport,
                });
                await renderTask.promise;
            } catch (err) {
                if (err?.name !== 'RenderingCancelledException') {
                    console.error('Thumbnail render error:', err);
                }
            }
        };

        render();
        return () => { isMounted = false; renderTask?.cancel(); };
    }, [pdfDoc, pageIndex]);

    return (
        <div
            onClick={onClick}
            style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                gap: '6px', padding: '8px', cursor: 'pointer', borderRadius: '6px',
                backgroundColor: isActive ? 'rgba(52, 152, 219, 0.2)' : 'transparent',
                border: isActive ? '2px solid #3498db' : '2px solid transparent',
                transition: 'all 0.15s',
            }}
            title={`Page ${pageIndex + 1}`}
        >
            <canvas
                ref={canvasRef}
                style={{
                    width: `${THUMB_WIDTH}px`,
                    boxShadow: isActive
                        ? '0 0 0 2px #3498db, 0 4px 12px rgba(0,0,0,0.4)'
                        : '0 2px 8px rgba(0,0,0,0.4)',
                    borderRadius: '2px',
                    backgroundColor: 'white',
                    display: 'block',
                }}
            />
            <span style={{
                fontSize: '11px', fontWeight: isActive ? '700' : '400',
                color: isActive ? '#3498db' : '#7f8c8d',
            }}>
                {pageIndex + 1}
            </span>
        </div>
    );
};

export const Sidebar = ({ pdfDoc, documentState, activePage, onPageClick }) => {
    const pages = documentState?.children ?? [];

    return (
        <div style={{
            width: '180px', flexShrink: 0,
            backgroundColor: '#1e2d3d',
            borderRight: '1px solid #0d1520',
            display: 'flex', flexDirection: 'column',
            overflow: 'hidden',
        }}>
            {/* Header */}
            <div style={{
                padding: '10px 12px', fontSize: '11px', fontWeight: '700',
                color: '#7f8c8d', textTransform: 'uppercase', letterSpacing: '0.08em',
                borderBottom: '1px solid #0d1520', flexShrink: 0,
            }}>
                Pages ({pages.length})
            </div>

            {/* Thumbnail list */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {!pdfDoc && (
                    <div style={{ color: '#546e7a', fontSize: '12px', textAlign: 'center', marginTop: '24px' }}>
                        No document loaded
                    </div>
                )}
                {pdfDoc && pages.map((page, index) => (
                    <Thumbnail
                        key={page.id}
                        pdfDoc={pdfDoc}
                        pageIndex={index}
                        isActive={activePage === index}
                        onClick={() => onPageClick(index)}
                    />
                ))}
            </div>
        </div>
    );
};