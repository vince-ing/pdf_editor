import { useState, useEffect } from 'react';
import { toolManager } from '../core/tools/ToolManager';

export function useActiveTool() {
  const [activeTool, setActiveTool] = useState(toolManager.getActiveToolId());

  useEffect(() => {
    const unsubscribe = toolManager.subscribe(setActiveTool);
    return unsubscribe;
  }, []);

  return activeTool;
}