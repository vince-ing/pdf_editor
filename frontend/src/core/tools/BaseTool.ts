import React from 'react';

export interface InteractionContext {
  x: number;
  y: number;
  originalEvent: React.PointerEvent<HTMLDivElement>;
  scale: number;
  pageId: string;
}

export abstract class BaseTool {
  abstract id: string;
  
  onPointerDown(context: InteractionContext): void {}
  onPointerMove(context: InteractionContext): void {}
  onPointerUp(context: InteractionContext): void {}
  onPointerLeave(context: InteractionContext): void {}
  
  onActivate(): void {}
  onDeactivate(): void {}
}