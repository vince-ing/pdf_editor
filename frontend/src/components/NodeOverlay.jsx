// components/NodeOverlay.jsx
import React from 'react';
import theme from '../theme';
const t = theme;

export const NodeOverlay = ({ node, scale = 1.0 }) => {
    if (!node.bbox) return null;
    const s = {
        position: 'absolute',
        left: `${node.bbox.x * scale}px`, top: `${node.bbox.y * scale}px`,
        width: `${node.bbox.width * scale}px`, height: `${node.bbox.height * scale}px`,
        pointerEvents: 'none',
    };

    if (node.node_type === 'text') return (
        <div style={{ ...s, border: '1px solid transparent', borderRadius: t.radius.xs, pointerEvents: 'auto' }}>
            <span style={{ fontSize: `${node.font_size * scale}px`, fontFamily: node.font_family, color: node.color ?? '#000' }}>
                {node.text_content}
            </span>
        </div>
    );

    if (node.node_type === 'highlight') {
        if (node.color === '#000000') return <div style={{ ...s, background: '#000', borderRadius: 1 }} />;
        return <div style={{ ...s, background: node.color ?? t.colors.highlight, opacity: node.opacity ?? 0.42, borderRadius: 1, mixBlendMode: 'multiply' }} />;
    }

    return null;
};