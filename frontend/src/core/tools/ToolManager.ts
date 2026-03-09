import { BaseTool } from './BaseTool';

type Listener = (activeToolId: string) => void;

class ToolManager {
  private tools: Map<string, BaseTool> = new Map();
  private activeToolId: string = 'select';
  private listeners: Set<Listener> = new Set();

  registerTool(tool: BaseTool) {
    this.tools.set(tool.id, tool);
  }

  setActiveTool(id: string) {
    if (this.activeToolId === id) return;
    
    const currentTool = this.getActiveTool();
    if (currentTool) currentTool.onDeactivate();
    
    this.activeToolId = id;
    
    const newTool = this.getActiveTool();
    if (newTool) newTool.onActivate();

    this.notifyListeners();
  }

  getActiveTool(): BaseTool | undefined {
    return this.tools.get(this.activeToolId);
  }

  getActiveToolId(): string {
    return this.activeToolId;
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notifyListeners() {
    this.listeners.forEach(listener => listener(this.activeToolId));
  }
}

export const toolManager = new ToolManager();