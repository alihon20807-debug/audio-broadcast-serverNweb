/**
 * main.js
 * Entry point for SyncAmp Precision Audio Sync Client
 */

import { 
    SYNC_JITTER_MS, 
    SYNC_BURST_GAP_MS, 
    SYNC_BURST_COUNT, 
    SYNC_INTERVAL_MS, 
    STATUS_POLL_MS,
    AppState 
} from './constants.js';

import { 
    dom, 
    cacheDom, 
    updateStatusUI, 
    updateClientCount,
    initSliders 
} from './ui.js';

import { 
    socket, 
    syncTime, 
    requestPlay, 
    requestStop 
} from './socket-client.js';

import { 
    resetSyncState, 
    processSyncPong, 
    getSyncState, 
    clearOffsetSamples 
} from './sync-engine.js';

import { 
    ensureAudioCtx, 
    stopSource, 
    preloadAudio, 
    schedulePlayback, 
    isSongLoaded,
    getAudioCtx
} from './audio-engine.js';



let appState = AppState.OFFLINE;
let syncIntervalId = null;
let statusIntervalId = null;

function setState(s, detail) {
    appState = s;
    const { rtt, syncJitter } = getSyncState();
    updateStatusUI(appState, rtt, syncJitter, detail);
}

// ADMIN_TOKEN prompting removed

function fireSyncBurst() {
    for (let i = 0; i < SYNC_BURST_COUNT; i++) {
        const jitter = (Math.random() - 0.5) * SYNC_JITTER_MS;
        setTimeout(syncTime, (i * SYNC_BURST_GAP_MS) + jitter);
    }
}

function startPeriodicSync() {
    if (syncIntervalId) clearInterval(syncIntervalId);
    syncIntervalId = setInterval(syncTime, SYNC_INTERVAL_MS);
}

async function initAndPlay() {

    const delay = Number(dom.playDelay?.value || 5000);
    try {
        await ensureAudioCtx(setState);
        fireSyncBurst();
    } catch (_) {
        return;
    }
    if (dom.mainBtn) dom.mainBtn.innerText = 'Requesting Play…';
    requestPlay(delay);
}

function stopPlayback() {

    if (socket.connected) {
        requestStop();
    } else {
        setState(AppState.OFFLINE);
    }
}

// ── Socket Events ──────────────────────────────────────────────────
socket.on('connect', () => {
    resetSyncState();
    setState(AppState.CONNECTED);
    fireSyncBurst();
    startPeriodicSync();
});

socket.on('disconnect', () => {
    setState(AppState.OFFLINE);
});

socket.on('client_count', (data) => {
    updateClientCount(data.count);
});

socket.on('sync_pong', (data) => {
    const result = processSyncPong(data, socket);
    if (!result) return;

    const { stable, rtt, syncJitter } = result;
    
    // UI update handled by status poll, but we update state here
    if (appState === AppState.CONNECTED || appState === AppState.STABILIZING) {
        setState(stable ? AppState.READY : AppState.STABILIZING);
    }
});

socket.on('play_event', async (data) => {
    stopSource();
    clearOffsetSamples();
    


    if (!getAudioCtx()) {
        console.warn('[SYNC] play_event before AudioContext init.');
        if (dom.mainBtn) dom.mainBtn.innerText = 'Join Playback';
        setState(AppState.CONNECTED, 'Tap Start to join playback');
        return;
    }

    try {
        if (!isSongLoaded(data.songUrl)) {
            await preloadAudio(data.songUrl, setState);
        }
    } catch (_) {
        return;
    }

    const fineTune = Number(dom.fineTune?.value || 0);
    const result = schedulePlayback(data, fineTune, setState);
    
    if (result && !result.error && !result.finished) {
        if (dom.mainBtn) dom.mainBtn.innerText = '▶ Playing';
        setState(result.statusState);
        console.log(result.logMsg);
        

    } else if (result && result.finished) {
        if (dom.mainBtn) dom.mainBtn.innerText = 'Start System';
    }
});

socket.on('stop_event', () => {
    stopSource();
    if (dom.mainBtn) dom.mainBtn.innerText = 'Start System';
    setState(AppState.STOPPED);
});

// ── Lifecycle ──────────────────────────────────────────────────────
function onDomReady() {
    cacheDom();
    if (dom.mainBtn) dom.mainBtn.addEventListener('click', initAndPlay);
    if (dom.stopBtn) dom.stopBtn.addEventListener('click', stopPlayback);
    initSliders();
    
    // Initial UI sync
    setState(appState);

    
    statusIntervalId = setInterval(() => {
        const { rtt, syncJitter } = getSyncState();
        updateStatusUI(appState, rtt, syncJitter);
    }, STATUS_POLL_MS);
}

document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        if (syncIntervalId) { clearInterval(syncIntervalId); syncIntervalId = null; }
        if (statusIntervalId) { clearInterval(statusIntervalId); statusIntervalId = null; }
    } else {
        fireSyncBurst();
        startPeriodicSync();
        statusIntervalId = setInterval(() => {
            const { rtt, syncJitter } = getSyncState();
            updateStatusUI(appState, rtt, syncJitter);
        }, STATUS_POLL_MS);
    }
});

window.addEventListener('beforeunload', () => {
    stopSource();
    const ctx = getAudioCtx();
    if (ctx && ctx.state !== 'closed') {
        ctx.close().catch(() => {});
    }
    if (syncIntervalId) clearInterval(syncIntervalId);
    if (statusIntervalId) clearInterval(statusIntervalId);
    socket.disconnect();
});

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', onDomReady);
} else {
    onDomReady();
}
