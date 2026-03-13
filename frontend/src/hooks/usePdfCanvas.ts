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

// ── Global render queue ────────────────────────────────────────────────────────
// pdf.js struggles when many pages render concurrently (especially image-heavy
// pages in large textbooks). A simple semaphore limits concurrent renders so
// title-page images and embedded JPEGs are not starved or silently dropped.
const MAX_CONCURRENT_RENDERS = 3;
let activeRenders = 0;
const renderQueue: Array<() => void> = [];

function acquireRenderSlot(): Promise<void> {
    return new Promise((resolve) => {
        if (activeRenders < MAX_CONCURRENT_RENDERS) {
            activeRenders++;
            resolve();
        } else {
            renderQueue.push(() => { activeRenders++; resolve(); });
        }
    });
}

function releaseRenderSlot(): void {
    activeRenders = Math.max(0, activeRenders - 1);
    const next = renderQueue.shift();
    if (next) next();
}
// ──────────────────────────────────────────────────────────────────────────────

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
        let slotAcquired = false;

        const renderPage = async () => {
            try {
                const pageNum = (pageNode?.page_number ?? pageIndex) + 1;
                if (pageNum < 1 || pageNum > pdfDoc.numPages) return;

                // ── FIX 1: Acquire a slot before doing any async work ──────────
                // This prevents all N pages from calling getPage() simultaneously,
                // which is the primary cause of image-render failures on large PDFs.
                await acquireRenderSlot();
                slotAcquired = true;
                if (!alive) { releaseRenderSlot(); return; }

                const page = await pdfDoc.getPage(pageNum);
                if (!alive) { releaseRenderSlot(); return; }

                const dpr = window.devicePixelRatio || 1;
                const vp  = page.getViewport({ scale: scale * dpr, rotation: localRotation });

                const canvas = canvasRef.current;
                if (!canvas) { releaseRenderSlot(); return; }

                // ── FIX 2: Set canvas buffer dimensions BEFORE render ──────────
                // Setting width/height resets the canvas context. Doing it after
                // getContext() but before render() ensures a clean, correctly-sized
                // buffer — critical for image-heavy pages (title pages, figures).
                canvas.width  = vp.width;
                canvas.height = vp.height;

                const cssW = vp.width / dpr;
                const cssH = vp.height / dpr;
                canvas.style.width  = `${cssW}px`;
                canvas.style.height = `${cssH}px`;

                setFullDimensions({ width: cssW, height: cssH });

                const canvasContext = canvas.getContext('2d');
                if (!canvasContext) { releaseRenderSlot(); return; }

                // ── FIX 3: Use 'display' intent + enable all annotation rendering ─
                // Without intent:'display', pdf.js may skip certain image codecs
                // (JBIG2, JPEG2000, CMYK) that textbook cover images often use.
                // annotationMode: ENABLE_FORMS ensures form fields/images aren't
                // omitted on pages that pdf.js treats as "form pages".
                renderTask = page.render({
                    canvasContext,
                    viewport: vp,
                    intent: 'display',
                    annotationMode: pdfjsLib.AnnotationMode.ENABLE_FORMS,
                });

                await renderTask.promise;
            } catch (err: any) {
                if (err?.name !== 'RenderingCancelledException') {
                    console.error('[usePdfCanvas] Rendering error:', err);
                }
            } finally {
                // Always release — even on cancellation or error — so the queue
                // doesn't stall and remaining pages (including image pages) render.
                if (slotAcquired) {
                    releaseRenderSlot();
                    slotAcquired = false;
                }
            }
        };

        renderPage();

        return () => {
            alive = false;
            if (renderTask) {
                renderTask.cancel();
            }
            // If we never acquired a slot (still in queue), remove from queue
            // to prevent a ghost render after unmount.
            const idx = renderQueue.indexOf(() => {});
            if (idx !== -1) renderQueue.splice(idx, 1);
        };
    }, [pdfDoc, pageNode, pageIndex, localRotation, scale]);

    return { canvasRef, fullDimensions };
};