import React, { useState } from 'react';

export const NodeOverlay = ({ node, scale = 1.0 }) => {
    const [hovered, setHovered] = useState(false);
    
    if (!node.bbox) return null;

    const style = {
        position: 'absolute',
        left:   `${node.bbox.x * scale}px`,
        top:    `${node.bbox.y * scale}px`,
        width:  `${node.bbox.width * scale}px`,
        height: `${node.bbox.height * scale}px`,
        pointerEvents: 'none',
    };

    switch (node.node_type) {
        case 'text':
            return (
                <div 
                    style={{ 
                        ...style, 
                        border: hovered ? '1px solid #3498db' : '1px solid transparent', 
                        cursor: 'pointer', 
                        borderRadius: '2px', 
                        pointerEvents: 'auto' 
                    }}
                    onMouseEnter={() => setHovered(true)} 
                    onMouseLeave={() => setHovered(false)}
                >
                    <span style={{ 
                        fontSize: `${node.font_size * scale}px`, 
                        fontFamily: node.font_family, 
                        color: node.color || '#000' 
                    }}>
                        {node.text_content}
                    </span>
                </div>
            );
        case 'highlight':
            const borderWidth = node.border_width || 0;
            if (node.color === '#000000') {
                return <div style={{ ...style, backgroundColor: '#000000', opacity: 1.0, borderRadius: '2px', pointerEvents: 'none', border: `${borderWidth}px solid transparent` }} />;
            }
            return <div style={{ ...style, backgroundColor: node.color || '#FFFF00', opacity: node.opacity ?? 0.5, borderRadius: '2px', pointerEvents: 'none', border: `${borderWidth}px solid transparent` }} />;
        default:
            return null;
    }
};