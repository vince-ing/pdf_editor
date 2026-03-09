import { BaseTool, InteractionContext } from './BaseTool';
import { toolManager } from './ToolManager';

export type TransientPos = { x: number; y: number; pageId: string } | null;

export class TextTool extends BaseTool {
  id = 'addtext';
  private posListeners = new Set<(pos: TransientPos) => void>();
  private commitListeners = new Set<() => void>();

  private isBoxActive = false;
  private justCommitted = false;

  onPositionStateChange(cb: (pos: TransientPos) => void) {
    this.posListeners.add(cb);
    return () => this.posListeners.delete(cb);
  }

  onCommitRequest(cb: () => void) {
    this.commitListeners.add(cb);
    return () => this.commitListeners.delete(cb);
  }

  // React calls this when a box is successfully committed or cancelled
  notifyCommitted() {
    this.isBoxActive = false;
  }

  onPointerDown(context: InteractionContext) {
    // If a box is already open, this click is meant to close it. 
    // Flag it so onPointerUp doesn't immediately open a new box.
    if (this.isBoxActive) {
        this.justCommitted = true;
    }
  }

  onPointerUp(context: InteractionContext) {
    // Left click only
    if (context.originalEvent.button !== 0) return;

    // If this click just closed an existing box, reset the flag and do nothing
    if (this.justCommitted) {
        this.justCommitted = false;
        return;
    }

    if (this.isBoxActive) return;

    // Broadcast the new coordinates and page ID
    this.posListeners.forEach(cb => cb({
      x: context.x,
      y: context.y,
      pageId: context.pageId
    }));

    this.isBoxActive = true;
  }

  onDeactivate() {
    this.commitListeners.forEach(cb => cb());
    this.posListeners.forEach(cb => cb(null));
    this.isBoxActive = false;
    this.justCommitted = false;
  }
}

// Initialize and register
export const textTool = new TextTool();
toolManager.registerTool(textTool);