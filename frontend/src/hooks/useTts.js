// frontend/src/hooks/useTts.js
import { useState, useRef, useCallback } from 'react';
import { engineApi } from '../api/client';

const API = 'http://localhost:8000/api/plugins/tts';

/**
 * useTts — manages all TTS state.
 *
 * Mirrors TtsController from the desktop app.
 */
export const useTts = () => {
    const [visible,  setVisible]  = useState(false);
    const [status,   setStatus]   = useState('Reading…');
    const [phase,    setPhase]    = useState('loading'); // 'loading' | 'playing'
    const [isPaused, setIsPaused] = useState(false);
    const [speed,    setSpeedVal] = useState(1.0);
    const [progress, setProgress] = useState({ done: 0, total: 0, pct: 0 });

    // Ref for the polling interval so we can clear it on stop
    const pollRef = useRef(null);

    const _clearPoll = () => {
        if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
        }
    };

    /**
     * Start a poll that transitions phase from 'loading' → 'playing' after
     * a short delay.
     */
    const _startPlaybackTransitionPoll = useCallback(() => {
        _clearPoll();

        // Simulate progress ticks during loading phase
        let fakeDone = 0;
        pollRef.current = setInterval(() => {
            fakeDone = Math.min(fakeDone + 1, 9);  // 0..9 out of an assumed 10
            setProgress({ done: fakeDone, total: 10, pct: fakeDone * 10 });
        }, 300);

        // After ~3s, assume playback has started (conservative for cold starts)
        setTimeout(() => {
            _clearPoll();
            setProgress({ done: 10, total: 10, pct: 100 });
            setPhase('playing');
        }, 3000);
    }, []);

    const speak = useCallback(async (text, statusLabel = 'Reading…') => {
        if (!text?.trim()) return;

        // Show bar immediately in loading state
        setStatus(statusLabel);
        setPhase('loading');
        setProgress({ done: 0, total: 0, pct: 0 });
        setIsPaused(false);
        setVisible(true);

        try {
            await engineApi.ttsPlay(text.trim(), speed);
            _startPlaybackTransitionPoll();
        } catch (err) {
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
            // Note: Keeping native fetch here since ttsPause isn't defined in client.ts yet
            const res = await fetch(`${API}/pause`, { method: 'POST' });
            const data = await res.json();
            // Use the authoritative paused state from the backend
            setIsPaused(data.paused);
        } catch (err) {
            console.error('[useTts] pause error:', err);
        }
    }, []);

    const setSpeed = useCallback((val) => {
        setSpeedVal(val);
        // Speed is snapshotted per-chunk in the backend, so changing it mid-
        // playback takes effect at the next chunk boundary automatically.
        // No extra API call needed; next speak() will use the new value.
    }, []);

    return {
        tts: { visible, status, phase, progress, isPaused, speed },
        speak,
        stop,
        pauseResume,
        setSpeed,
    };
};