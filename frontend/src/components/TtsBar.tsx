// TtsBar.tsx — slide-up text-to-speech bar

interface TtsBarProps {
  visible: boolean;
  status?: string;
  phase?: 'loading' | 'playing';
  progress?: { pct: number };
  isPaused?: boolean;
  speed?: number;
  onStop: () => void;
  onPauseResume: () => void;
  onSpeedChange: (s: number) => void;
}

export function TtsBar({ visible, status, phase, progress, isPaused, speed = 1, onStop, onPauseResume, onSpeedChange }: TtsBarProps) {
  if (!visible) return null;
  return (
    <div className="h-10 bg-[#1e2327] border-t border-white/[0.05] flex items-center gap-0 flex-shrink-0 animate-slide-up shadow-2xl">
      <button
        onClick={onStop}
        className="w-10 h-full flex items-center justify-center text-gray-400 hover:text-white transition-colors text-sm"
      >✕</button>
      <div className="w-px h-5 bg-white/10 flex-shrink-0" />
      <span className="text-xs font-semibold text-[#4a90e2] px-3 font-mono whitespace-nowrap">
        {phase === 'loading' ? '⏳' : isPaused ? '⏸' : '🔊'} {status}
      </span>
      <div className="w-px h-5 bg-white/10 flex-shrink-0" />

      {phase === 'loading' && (
        <div className="flex items-center gap-2 px-3 flex-1">
          <div className="flex-1 max-w-[160px] h-1 bg-[#2d3338] rounded-full overflow-hidden">
            <div className="h-full bg-[#4a90e2] rounded-full transition-all" style={{ width: `${progress?.pct ?? 0}%` }} />
          </div>
          <span className="text-[10px] text-gray-500 font-mono">{progress?.pct ?? 0}%</span>
        </div>
      )}

      {phase === 'playing' && (
        <div className="flex items-center gap-2 px-3">
          <button
            onClick={onPauseResume}
            className={`h-6 px-3 rounded text-xs font-medium transition-colors border
              ${isPaused
                ? 'bg-green-500/10 border-green-500/30 text-green-400 hover:bg-green-500/20'
                : 'bg-[#4a90e2]/10 border-[#4a90e2]/30 text-[#4a90e2] hover:bg-[#4a90e2]/20'
              }`}
          >
            {isPaused ? '▶ Resume' : '⏸ Pause'}
          </button>
          <button
            onClick={onStop}
            className="h-6 px-3 rounded text-xs font-medium bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 transition-colors"
          >
            ◼ Stop
          </button>
          <div className="w-px h-4 bg-white/10 mx-1 flex-shrink-0" />
          <span className="text-[11px] text-gray-500">Speed</span>
          <input
            type="range" min={0.25} max={4} step={0.25} value={speed}
            onChange={e => onSpeedChange(parseFloat(e.target.value))}
            className="w-20 accent-[#4a90e2] cursor-pointer"
          />
          <span className="text-xs font-semibold text-white font-mono min-w-[28px]">{speed}×</span>
        </div>
      )}
    </div>
  );
}
