// frontend/src/hooks/usePageChars.js
import { useState, useEffect } from 'react';
import { engineApi } from '../api/client';

export const usePageChars = ({ pageNodeId, localRotation, metadata }) => {
    const [rawChars, setRawChars] = useState([]);
    const [pageChars, setPageChars] = useState([]);

    // 1. Fetch the raw character bounding boxes (in original PDF space)
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

    // 2. Transform the raw characters to match the current visual rotation
    useEffect(() => {
        if (!rawChars.length) { 
            setPageChars([]); 
            return; 
        }

        // Page dimensions in the *original* (unrotated) orientation
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

        // Sort into reading order for the *rotated* orientation
        transformed.sort((a, b) =>
            Math.abs(a.y - b.y) > 5 ? a.y - b.y : a.x - b.x
        );
        
        setPageChars(transformed);
    }, [rawChars, localRotation, metadata]);

    return { pageChars };
};