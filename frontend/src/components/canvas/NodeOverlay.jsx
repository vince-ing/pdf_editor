// components/canvas/NodeOverlay.tsx — Renders annotation overlays on a page.
// Supports: text annotations, highlight/redact boxes.

interface AnnotationNode {
  id: string;
  node_type: string;
  bbox?: { x: number; y: number; width: number; height: number };
  color?: string;
  opacity?: number;
  text_content?: string;
  font_size?: number;
  font_family?: string;
}

interface NodeOverlayProps {
  node: AnnotationNode;
  scale: number;
}

export function NodeOverlay({ node, scale }: NodeOverlayProps) {
  if (!node.bbox) return null;

  const style: React.CSSProperties = {
    position: 'absolute',
    left:   node.bbox.x      * scale,
    top:    node.bbox.y      * scale,
    width:  node.bbox.width  * scale,
    height: node.bbox.height * scale,
    pointerEvents: 'none',
  };

  if (node.node_type === 'text') {
    return (
      <div style={style}>
        <span
          style={{
            fontSize:   (node.font_size ?? 12) * scale,
            fontFamily: node.font_family,
            color:      node.color ?? '#000',
          }}
        >
          {node.text_content}
        </span>
      </div>
    );
  }

  if (node.node_type === 'highlight') {
    // Black highlight = redaction box
    if (node.color === '#000000') {
      return <div style={{ ...style, background: '#000', borderRadius: 1 }} />;
    }
    return (
      <div
        style={{
          ...style,
          background:    node.color ?? '#f59e0b',
          opacity:       node.opacity ?? 0.42,
          borderRadius:  1,
          mixBlendMode:  'multiply',
        }}
      />
    );
  }

  return null;
}