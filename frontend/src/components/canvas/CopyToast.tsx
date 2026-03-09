import React from 'react';

export const CopyToast = ({ visible }: { visible: boolean }) => (
  <div className={`fixed bottom-10 left-1/2 -translate-x-1/2 bg-[#2d3338] text-white border border-white/[0.07] px-4 py-2 rounded-lg text-sm font-medium shadow-xl flex items-center gap-2 pointer-events-none z-50 transition-all duration-200 ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}>
    <span className="text-green-400">✓</span> Copied to clipboard
  </div>
);