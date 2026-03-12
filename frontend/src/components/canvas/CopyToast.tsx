// frontend/src/components/canvas/CopyToast.tsx
//
// Singleton toast rendered once at the app level via ToastProvider.
// Replaces the per-page fixed toast that could stack when multiple pages
// triggered a copy simultaneously.

import React, { createContext, useCallback, useContext, useRef, useState } from 'react';

// ── Context ───────────────────────────────────────────────────────────────────

interface ToastContextValue {
  showCopyToast: () => void;
}

const ToastContext = createContext<ToastContextValue>({ showCopyToast: () => {} });

export function useToast() {
  return useContext(ToastContext);
}

// ── Provider ──────────────────────────────────────────────────────────────────

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  const showCopyToast = useCallback(() => {
    setVisible(true);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setVisible(false), 2000);
  }, []);

  return (
    <ToastContext.Provider value={{ showCopyToast }}>
      {children}
      <CopyToast visible={visible} />
    </ToastContext.Provider>
  );
}

// ── Toast UI ──────────────────────────────────────────────────────────────────

export function CopyToast({ visible }: { visible: boolean }) {
  return (
    <div
      className={`
        fixed bottom-10 left-1/2 -translate-x-1/2
        bg-[#2d3338] text-white border border-white/[0.07]
        px-4 py-2 rounded-lg text-sm font-medium shadow-xl
        flex items-center gap-2 pointer-events-none z-[99999]
        transition-all duration-200
        ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}
      `}
    >
      <span className="text-green-400">✓</span> Copied to clipboard
    </div>
  );
}