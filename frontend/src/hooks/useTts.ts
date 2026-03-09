// frontend/src/hooks/useTts.ts
import { useState, useRef, useCallback } from 'react';
import { engineApi } from '../api/client';

const API = 'http://localhost:8000/api/plugins/tts';

export interface TtsProgress {
    done: number;
    total: number;
    pct: number;
}

export type TtsPhase = 'loading' | 'playing';

export const useTts = () => {
    const [visible,  setVisible]  = useState(false);
    const [status,   setStatus]   = useState('Reading…');
    const [phase,    setPhase]    = useState<TtsPhase>('loading');
    const [isPaused, setIsPaused] = useState(false);
    const [speed,    setSpeedVal] = useState(1.0);
    const [progress, setProgress] = useState<TtsProgress>({ done: 0, total: 0, pct: 0 });

    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const _clearPoll = () => {
        if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
        }
    };

    const _startPlaybackTransitionPoll = useCallback(() => {
        _clearPoll();

        let fakeDone = 0;
        pollRef.current = setInterval(() => {
            fakeDone = Math.min(fakeDone + 1, 9);
            setProgress({ done: fakeDone, total: 10, pct: fakeDone * 10 });
        }, 300);

        setTimeout(() => {
            _clearPoll();
            setProgress({ done: 10, total: 10, pct: 100 });
            setPhase('playing');
        }, 3000);
    }, []);

    const speak = useCallback(async (text: string, statusLabel = 'Reading…') => {
        if (!text?.trim()) return;

        setStatus(statusLabel);
        setPhase('loading');
        setProgress({ done: 0, total: 0, pct: 0 });
        setIsPaused(false);
        setVisible(true);

        try {
            await engineApi.ttsPlay(text.trim(), speed);
            _startPlaybackTransitionPoll();
        } catch (err: any) {
            console.error('[useTts] speak error:', err);
            setVisible(false);
            _clearPoll();
            alert('TTS error: ' + err.message);
        }
    }, [speed, _startPlaybackTransitionPoll]);

    const stop = useCallback(async () => {
        _clearPoll();
        try {
            await engineApi.ttsStop();
        } catch (err) {
            console.error('[useTts] stop error:', err);
        }
        setVisible(false);
        setPhase('loading');
        setIsPaused(false);
    }, []);

    const pauseResume = useCallback(async () => {
        try {
            const res = await fetch(`${API}/pause`, { method: 'POST' });
            const data = await res.json();
            setIsPaused(data.paused);
        } catch (err) {
            console.error('[useTts] pause error:', err);
        }
    }, []);

    const setSpeed = useCallback((val: number) => {
        setSpeedVal(val);
    }, []);

    return {
        tts: { visible, status, phase, progress, isPaused, speed },
        speak,
        stop,
        pauseResume,
        setSpeed,
    };
};