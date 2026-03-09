// frontend/src/hooks/usePageChars.ts
import { useState, useEffect } from 'react';
import { engineApi } from '../api/client';

export interface PageChar {
    x: number;
    y: number;
    width: number;
    height: number;
    text: string;
}

interface UsePageCharsArgs {
    pageNodeId: string;
    localRotation: number;
    metadata?: { width: number; height: number };
}

export const usePageChars = ({ pageNodeId, localRotation, metadata }: UsePageCharsArgs) => {
    const [rawChars, setRawChars] = useState<PageChar[]>([]);
    const [pageChars, setPageChars] = useState<PageChar[]>([]);

    useEffect(() => {
        let alive = true;
        if (!pageNodeId) return;

        engineApi.getPageChars(pageNodeId)
            .then(chars => {
                if (!alive) return;
                setRawChars(chars || []);
            })
            .catch(err => console.error('[usePageChars] fetch error:', err));
            
        return () => { alive = false; };
    }, [pageNodeId]);

    useEffect(() => {
        if (!rawChars.length) { 
            setPageChars([]); 
            return; 
        }

        const W = metadata?.width  || 612;
        const H = metadata?.height || 792;

        const transformed = rawChars.map(c => {
            let { x, y, width, height } = c;
            switch (((localRotation % 360) + 360) % 360) {
                case 90: {
                    const nx = H - y - height;
                    const ny = x;
                    return { ...c, x: nx, y: ny, width: height, height: width };
                }
                case 180: {
                    return { ...c, x: W - x - width, y: H - y - height };
                }
                case 270: {
                    const nx = y;
                    const ny = W - x - width;
                    return { ...c, x: nx, y: ny, width: height, height: width };
                }
                default:
                    return c;
            }
        });

        transformed.sort((a, b) =>
            Math.abs(a.y - b.y) > 5 ? a.y - b.y : a.x - b.x
        );
        
        setPageChars(transformed);
    }, [rawChars, localRotation, metadata]);

    return { pageChars };
};