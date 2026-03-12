// frontend/src/components/canvas/PageRenderer/PageChrome.tsx
// UI chrome: PageControls and busy overlay.
// CopyToast is now app-level (see ToastProvider in CopyToast.tsx) so it
// can't stack across pages.

import React, { useState } from 'react';
import { PageControls } from '../PageControls';

interface PageChromeProps {
  pageId:      string;
  pageIndex:   number;
  totalPages:  number;
  sessionId:   string;
  busy:        boolean;
  cropActive:  boolean; // hide controls while crop rect is active
  setLocalRotation: (r: number | ((prev: number) => number)) => void;
  onDocumentChanged?: () => Promise<void>;
  withBusy:    (fn: () => Promise<void>) => Promise<void>;
  children:    React.ReactNode;
}

export function PageChrome({
  pageId, pageIndex, totalPages, sessionId,
  busy, cropActive,
  setLocalRotation, onDocumentChanged, withBusy,
  children,
}: PageChromeProps) {
  const [showCtrl, setShowCtrl] = useState(false);

  return (
    <div
      className="relative bg-white flex-shrink-0 mx-auto mb-6 transition-shadow rounded-sm shadow-xl hover:shadow-2xl"
      style={{ opacity: busy ? 0.75 : 1 }}
      onMouseEnter={() => setShowCtrl(true)}
      onMouseLeave={() => setShowCtrl(false)}
    >
      {showCtrl && !cropActive && (
        <PageControls
          pageId={pageId}
          pageIndex={pageIndex}
          totalPages={totalPages}
          sessionId={sessionId}
          withBusy={withBusy}
          onDocumentChanged={onDocumentChanged}
          setLocalRotation={setLocalRotation}
        />
      )}

      {children}

      {busy && (
        <div className="absolute inset-0 bg-black/10 flex items-center justify-center z-50">
          <div className="bg-[#2d3338] text-white text-xs font-semibold px-4 py-2 rounded-lg border border-white/10 shadow-xl">
            Working…
          </div>
        </div>
      )}
    </div>
  );
}