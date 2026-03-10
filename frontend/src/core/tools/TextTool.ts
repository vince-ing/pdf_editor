import { BaseTool, InteractionContext } from './BaseTool';
import { toolManager } from './ToolManager';

export type TransientPos = { x: number; y: number; w?: number; h?: number; pageId: string; isDrawing?: boolean } | null;

export class TextTool extends BaseTool {
  id = 'addtext';
  private posListeners = new Set<(pos: TransientPos) => void>();
  private commitListeners = new Set<() => void>();

  private isBoxActive = false;
  private justCommitted = false;
  private isDragging = false;
  private startX = 0;
  private startY = 0;

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
        return;
    }
    if (context.originalEvent.button !== 0) return;

    this.isDragging = true;
    this.startX = context.x;
    this.startY = context.y;

    this.posListeners.forEach(cb => cb({
      x: this.startX, y: this.startY, w: 0, h: 0,
      pageId: context.pageId, isDrawing: true
    }));
  }

  onPointerMove(context: InteractionContext) {
    if (!this.isDragging) return;
    const currentX = context.x;
    const currentY = context.y;
    const x = Math.min(this.startX, currentX);
    const y = Math.min(this.startY, currentY);
    const w = Math.abs(currentX - this.startX);
    const h = Math.abs(currentY - this.startY);

    this.posListeners.forEach(cb => cb({
        x, y, w, h, pageId: context.pageId, isDrawing: true
    }));
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
    if (!this.isDragging) return;

    this.isDragging = false;
    const currentX = context.x;
    const currentY = context.y;
    const x = Math.min(this.startX, currentX);
    const y = Math.min(this.startY, currentY);
    const w = Math.abs(currentX - this.startX);
    const h = Math.abs(currentY - this.startY);

    // If it was just a click, emit without w/h so it uses defaults
    const isClick = w < 5 && h < 5;

    // Broadcast the final coordinates
    this.posListeners.forEach(cb => cb({
      x: isClick ? this.startX : x,
      y: isClick ? this.startY : y,
      w: isClick ? undefined : w,
      h: isClick ? undefined : h,
      pageId: context.pageId,
      isDrawing: false
    }));

    this.isBoxActive = true;
  }

  onDeactivate() {
    this.commitListeners.forEach(cb => cb());
    this.posListeners.forEach(cb => cb(null));
    this.isBoxActive = false;
    this.justCommitted = false;
    this.isDragging = false;
  }
}

// Initialize and register
export const textTool = new TextTool();
toolManager.registerTool(textTool);