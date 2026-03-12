// frontend/src/hooks/useDrawToolRegistration.ts
//
// Encapsulates the full DrawTool lifecycle so AppInner stays focused on layout.
//
// Responsibilities:
//   - Create and register a DrawTool instance the first time a tab becomes active.
//   - Keep sessionId, color, and refreshDocumentState in sync on the existing
//     instance without triggering a re-registration.
//
// Why three separate effects instead of one?
//   - Registration must run only when activeTabId changes (not on color changes).
//   - sessionId must update whenever the tab changes (fixes the staleness bug).
//   - color and refreshDocumentState updates are independent and cheap.
//   Merging them would either over-register or miss updates.

import { useEffect } from 'react';
import { toolManager } from '../core/tools/ToolManager';
import { DrawTool } from '../core/tools/DrawTool';

interface UseDrawToolRegistrationArgs {
  activeTabId:          string | null;
  highlightColor:       string;
  refreshDocumentState: () => Promise<void>;
}

export function useDrawToolRegistration({
  activeTabId,
  highlightColor,
  refreshDocumentState,
}: UseDrawToolRegistrationArgs) {

  // 1. Register a fresh DrawTool instance when a new tab becomes active.
  //    Intentionally excludes highlightColor and refreshDocumentState — those
  //    are kept current by the effects below so registration stays stable.
  useEffect(() => {
    if (!activeTabId) return;
    const tool = new DrawTool(
      activeTabId,
      highlightColor,
      2.0,
      refreshDocumentState,
    );
    toolManager.registerTool(tool);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTabId]);

  // 2. Sync sessionId immediately on tab switch.
  //    Previously this was never called; the DrawTool kept writing annotations
  //    to the previous tab's session after switching.
  useEffect(() => {
    if (!activeTabId) return;
    (toolManager.getTool('draw') as DrawTool | undefined)?.setSessionId(activeTabId);
  }, [activeTabId]);

  // 3. Sync highlight color without re-registering the tool.
  useEffect(() => {
    (toolManager.getTool('draw') as DrawTool | undefined)?.setColor(highlightColor);
  }, [highlightColor]);

  // 4. Sync the success callback without re-registering the tool.
  //    refreshDocumentState is recreated by useCallback when its own deps
  //    change, so this keeps the tool pointing at the current closure.
  useEffect(() => {
    (toolManager.getTool('draw') as DrawTool | undefined)?.setOnSuccess(refreshDocumentState);
  }, [refreshDocumentState]);
}