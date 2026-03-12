// frontend/src/components/canvas/PageRenderer/SearchLayer.tsx
// Renders search match highlight rectangles over the page.

import React from 'react';

export interface SearchMatch {
  rects:      { x: number; y: number; width: number; height: number }[];
  matchIndex: number;
  isCurrent:  boolean;
}

interface SearchLayerProps {
  matches: SearchMatch[];
  scale:   number;
}

export function SearchLayer({ matches, scale }: SearchLayerProps) {
  if (matches.length === 0) return null;
  return (
    <>
      {matches.map((match, mi) =>
        match.rects.map((rect, ri) => (
          <div
            key={`search-${mi}-${ri}`}
            className="absolute pointer-events-none"
            style={{
              left:            rect.x      * scale,
              top:             rect.y      * scale,
              width:           rect.width  * scale,
              height:          rect.height * scale,
              backgroundColor: match.isCurrent
                ? 'rgba(250, 204, 21, 0.75)'  // yellow — current match
                : 'rgba(147, 51, 234, 0.45)', // purple — other matches
              mixBlendMode: 'multiply',
              borderRadius: 2,
              zIndex:       match.isCurrent ? 16 : 15,
              transition:   'background-color 0.15s',
            }}
          />
        ))
      )}
    </>
  );
}