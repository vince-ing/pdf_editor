import React from 'react';
import { engineApi } from '../../api/client';

interface PageControlsProps {
  pageId: string;
  pageIndex: number;
  totalPages: number;
  sessionId: string;
  withBusy: (fn: () => Promise<void>) => void;
  onDocumentChanged?: () => Promise<void>;
  setLocalRotation: React.Dispatch<React.SetStateAction<number>>;
}

export function PageControls({ pageId, pageIndex, totalPages, sessionId, withBusy, onDocumentChanged, setLocalRotation }: PageControlsProps) {
  return (
    <div className="absolute -top-9 left-1/2 -translate-x-1/2 z-30 flex items-center gap-1 bg-[#2d3338] border border-white/[0.07] rounded-lg px-2 py-1.5 shadow-xl animate-ctrl-in">
      {[
        { icon: '↑', title: 'Move up',    disabled: pageIndex === 0,             onClick: () => withBusy(async () => { await engineApi.movePage(pageId, pageIndex - 1, sessionId);  await onDocumentChanged?.(); }) },
        { icon: '↓', title: 'Move down',  disabled: pageIndex >= totalPages - 1, onClick: () => withBusy(async () => { await engineApi.movePage(pageId, pageIndex + 1, sessionId);  await onDocumentChanged?.(); }) },
        null,
        { icon: '↻', title: 'Rotate CW',  onClick: () => withBusy(async () => { const r = await engineApi.rotatePage(pageId, sessionId, 90); setLocalRotation(r?.page?.rotation ?? (v => (v + 90) % 360));        await onDocumentChanged?.(); }) },
        { icon: '↺', title: 'Rotate CCW', onClick: () => withBusy(async () => { const r = await engineApi.rotatePage(pageId, sessionId, -90); setLocalRotation(r?.page?.rotation ?? (v => (v - 90 + 360) % 360)); await onDocumentChanged?.(); }) },
        null,
        { icon: '✕', title: 'Delete page', danger: true, disabled: totalPages <= 1, onClick: () => { if (!window.confirm(`Delete page ${pageIndex + 1}?`)) return; withBusy(async () => { await engineApi.deletePage(pageId, sessionId); await onDocumentChanged?.(); }); } },
      ].map((btn, i) =>
        btn === null
          ? <div key={i} className="w-px h-4 bg-white/10 mx-0.5" />
          : <button key={i} title={btn.title} disabled={btn.disabled} onClick={btn.onClick}
              className={`w-7 h-7 rounded flex items-center justify-center text-sm transition-colors ${(btn as any).danger ? 'text-red-400 hover:bg-red-500/20 disabled:opacity-30' : 'text-gray-400 hover:bg-[#3d4449] hover:text-white disabled:opacity-30'} disabled:cursor-not-allowed`}
            >{btn.icon}</button>
      )}
    </div>
  );
}