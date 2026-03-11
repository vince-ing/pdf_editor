// frontend/src/core/tools/DrawTool.ts

import { BaseTool, InteractionContext } from './BaseTool';
import { engineApi } from '../../api/client';

export class DrawTool extends BaseTool {
  id = 'draw';
  private isDrawing = false;
  private currentPath: {x: number, y: number}[] = [];
  
  constructor(
    private sessionId: string, 
    private color: string = '#000000', 
    private thickness: number = 2.0,
    private onSuccess?: () => void // Add callback to trigger canvas refresh
  ) {
    super();
  }

  private notify(pageId: string) {
    window.dispatchEvent(new CustomEvent('draw-update', {
      detail: { pageId, path: this.currentPath, color: this.color, thickness: this.thickness }
    }));
  }

  onPointerDown(context: InteractionContext) {
    this.isDrawing = true;
    this.currentPath = [{ x: context.x, y: context.y }];
    this.notify(context.pageId);
  }

  onPointerMove(context: InteractionContext) {
    if (!this.isDrawing) return;
    this.currentPath.push({ x: context.x, y: context.y });
    this.notify(context.pageId);
  }

  async onPointerUp(context: InteractionContext) {
    if (!this.isDrawing) return;
    this.isDrawing = false;
    
    if (this.currentPath.length > 1) {
      // Keep a copy to save, then immediately clear the transient state
      const pathToSave = [...this.currentPath];
      this.currentPath = [];
      this.notify(context.pageId);

      try {
        await engineApi.addPathAnnotation(
          context.pageId, 
          pathToSave, 
          this.color, 
          this.thickness, 
          1.0, 
          this.sessionId
        );
        // Inform the application to re-fetch the document state so the path renders
        if (this.onSuccess) {
          this.onSuccess();
        }
      } catch (err) {
        console.error("Failed to add path annotation:", err);
      }
    } else {
      this.currentPath = [];
      this.notify(context.pageId);
    }
  }
  
  onPointerLeave(context: InteractionContext) {
    if (this.isDrawing) {
      this.onPointerUp(context);
    }
  }
}