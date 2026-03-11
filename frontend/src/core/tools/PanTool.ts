// frontend/src/core/tools/PanTool.ts
import { BaseTool, InteractionContext } from './BaseTool';
import { toolManager } from './ToolManager';

export class PanTool extends BaseTool {
  id = 'hand';
  private isDragging = false;
  private lastX = 0;
  private lastY = 0;

  onPointerDown(context: InteractionContext) {
    // Respond to Left click (0), Middle click (1), AND touch (usually mapped to 0)
    // We remove the strict button check or expand it to ensure touch is accepted
    
    this.isDragging = true;
    this.lastX = context.originalEvent.clientX;
    this.lastY = context.originalEvent.clientY;
    
    // Force the grabbing cursor globally so it doesn't flicker when moving fast
    document.body.style.cursor = 'grabbing';
  }

  onPointerMove(context: InteractionContext) {
    if (!this.isDragging) return;
    
    const dx = context.originalEvent.clientX - this.lastX;
    const dy = context.originalEvent.clientY - this.lastY;
    this.lastX = context.originalEvent.clientX;
    this.lastY = context.originalEvent.clientY;

    // Find the main scrollable canvas container (it has the overflow-auto class in Canvas.tsx)
    const container = (context.originalEvent.target as HTMLElement).closest('.overflow-auto');
    if (container) {
      container.scrollLeft -= dx;
      container.scrollTop -= dy;
    }
  }

  onPointerUp() {
    this.isDragging = false;
    document.body.style.cursor = '';
  }

  onPointerLeave() {
    this.isDragging = false;
    document.body.style.cursor = '';
  }
  
  onDeactivate() {
    this.isDragging = false;
    document.body.style.cursor = '';
  }
}

// Initialize and register
export const panTool = new PanTool();
toolManager.registerTool(panTool);