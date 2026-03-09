import { BaseTool, InteractionContext } from './BaseTool';
import { toolManager } from './ToolManager';

type PointerEventCallback = (context: InteractionContext) => void;

export class DragTool extends BaseTool {
  id = 'drag-placeholder'; // Set dynamically based on the tool
  private downListeners = new Set<PointerEventCallback>();
  private moveListeners = new Set<PointerEventCallback>();
  private upListeners = new Set<PointerEventCallback>();
  private leaveListeners = new Set<PointerEventCallback>();

  onDown(cb: PointerEventCallback) { this.downListeners.add(cb); return () => this.downListeners.delete(cb); }
  onMove(cb: PointerEventCallback) { this.moveListeners.add(cb); return () => this.moveListeners.delete(cb); }
  onUp(cb: PointerEventCallback) { this.upListeners.add(cb); return () => this.upListeners.delete(cb); }
  onLeave(cb: PointerEventCallback) { this.leaveListeners.add(cb); return () => this.leaveListeners.delete(cb); }

  onPointerDown(ctx: InteractionContext) { this.downListeners.forEach(cb => cb(ctx)); }
  onPointerMove(ctx: InteractionContext) { this.moveListeners.forEach(cb => cb(ctx)); }
  onPointerUp(ctx: InteractionContext) { this.upListeners.forEach(cb => cb(ctx)); }
  onPointerLeave(ctx: InteractionContext) { this.leaveListeners.forEach(cb => cb(ctx)); }
}

// Create an instance for each tool that needs drag selection
export const highlightTool = new DragTool(); highlightTool.id = 'highlight';
export const redactTool = new DragTool(); redactTool.id = 'redact';
export const selectTool = new DragTool(); selectTool.id = 'select';
export const cropTool = new DragTool(); cropTool.id = 'crop';
export const underlineTool = new DragTool(); underlineTool.id = 'underline';

toolManager.registerTool(highlightTool);
toolManager.registerTool(redactTool);
toolManager.registerTool(selectTool);
toolManager.registerTool(cropTool);
toolManager.registerTool(underlineTool);