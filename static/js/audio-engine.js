/**
 * audio-engine.js
 * AudioContext lifecycle and synchronized playback management
 */

import { AppState, FETCH_TIMEOUT_MS } from './constants.js';
import { getSynchronizedTime } from './sync-engine.js';

let audioCtx       = null;
let audioBuffer    = null;
let source         = null;
let loadedSongUrl  = null;

export function getAudioCtx() { return audioCtx; }

export async function ensureAudioCtx(setStateCallback) {
    try {
        if (!audioCtx || audioCtx.state === 'closed') {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)({
                latencyHint: 'interactive',
            });
        }
        if (audioCtx.state === 'suspended') {
            const resumePromise = audioCtx.resume();
            const timeoutPromise = new Promise((_, r) => setTimeout(() => r(new Error('AudioContext.resume timeout')), 3000));
            await Promise.race([resumePromise, timeoutPromise]).catch(e => console.warn('[AUDIO] Resume warning:', e));
        }
        
        if (audioCtx.state === 'running') {
            const t1 = audioCtx.currentTime;
            await new Promise(r => setTimeout(r, 10));
            if (audioCtx.currentTime === t1) {
                console.warn('[AUDIO] Clock is STALLED — logic might fail.');
            }
        }
        return audioCtx;
    } catch (e) {
        console.error('[AUDIO] Failed to create/resume AudioContext:', e);
        if (setStateCallback) setStateCallback(AppState.ERROR, 'Audio init failed: ' + e.message);
        throw e;
    }
}

export function stopSource() {
    if (source) {
        try { source.onended = null; } catch (_) {}
        try { source.stop(); } catch (_) {}
        source = null;
    }
}

export async function preloadAudio(url, setStateCallback) {
    try {
        if (setStateCallback) setStateCallback(AppState.LOADING);
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

        const res = await fetch(url, {
            signal: controller.signal,
            mode: 'same-origin',
        });
        clearTimeout(timeout);

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        
        const arrayBuffer = await res.arrayBuffer();
        
        const decodePromise = audioCtx.decodeAudioData(arrayBuffer);
        const timeoutPromise = new Promise((_, reject) => 
            setTimeout(() => reject(new Error("decodeAudioData timeout")), 10000)
        );
        
        audioBuffer = await Promise.race([decodePromise, timeoutPromise]);
        
        loadedSongUrl = new URL(url, location.origin).href;

        return true;
    } catch (e) {
        console.error('Audio load failed:', e);
        if (setStateCallback) setStateCallback(AppState.ERROR, 'Load error: ' + e.message);
        throw e;
    }
}

export function schedulePlayback(data, fineTune, setStateCallback) {
    if (!audioBuffer) return;
    
    stopSource();

    source = audioCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(audioCtx.destination);
    


    const msUntilPlay = (data.targetTimeMs + fineTune) - getSynchronizedTime();

    let statusState, logMsg;

    try {
        if (msUntilPlay > 0) {
            const whenSec = audioCtx.currentTime + (msUntilPlay / 1000);
            source.start(whenSec);

            statusState = AppState.PLAYING;
            logMsg = `[SYNC] Scheduling in ${msUntilPlay.toFixed(2)}ms`;
        } else {
            const offsetSec = -msUntilPlay / 1000;
            if (offsetSec < audioBuffer.duration) {
                const latencyComp = (audioCtx.outputLatency || 0) + (audioCtx.baseLatency || 0);
                source.start(0, offsetSec + latencyComp);

                statusState = AppState.LATE_JOIN;
                logMsg = `[SYNC] Late join at offset ${offsetSec.toFixed(4)}s`;
            } else {
                console.warn('[SYNC] Song already finished.');
                if (setStateCallback) setStateCallback(AppState.ENDED);
                source = null;
                return { finished: true };
            }
        }
    } catch (e) {
        console.error('[SYNC] source.start() failed:', e);
        if (setStateCallback) setStateCallback(AppState.ERROR, 'Playback error');
        source = null;
        return { error: e };
    }

    source.onended = () => {
        if (source && source.buffer) {
            if (setStateCallback) setStateCallback(AppState.ENDED);
        }
    };

    return { statusState, logMsg, msUntilPlay };
}

export function isSongLoaded(url) {
    if (!audioBuffer) return false;
    const canonicalUrl = new URL(url, location.origin).href;
    return canonicalUrl === loadedSongUrl;
}
