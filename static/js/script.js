const socket = io({
    transports: ['websocket'],
    upgrade: false
});

// ── Test & Telemetry Hooks ─────────────────────────────────────────
// Bug #21: Expose internal state for high-fidelity automation
window.__sync_telemetry = {
    rtt: 0,
    serverOffset: 0,
    syncJitter: 0,
    isReady: false,
    lastScheduledMs: 0,
    targetTimeMs: 0,
    playbackStartLocal: 0
};

let audioCtx = null;
let audioBuffer = null;
let source = null;
let isReady = false;

// High-precision sync variables
// NOTE on precision (Bug #7): performance.now() is monotonic and high-resolution (~5μs).
// The serverOffset is large (~epoch ms ≈ 1.7×10¹²) but IEEE 754 doubles give ~15.9 significant
// digits, so at 10¹³ magnitude we retain ~0.001ms precision — adequate for audio sync.
// We use median filtering (not mean) to reject outlier RTT samples for better sync quality.
let serverOffset = 0;
let rtt = 0;
let syncJitter = 0;
let offsetSamples = [];
const MAX_SAMPLES = 10;

// ── Internal Recorder (Automation Component) ──────────────────────
// Bug #25: Web-native loopback recording for automated testing
let recorder = null;
let chunks = [];
let recordingStream = null;

// Bug #12: Track which URL is currently loaded so we re-fetch on change
let loadedSongUrl = null;

// ── Status UI updater ──────────────────────────────────────────────
// Bug #8 & #9: Properly toggle status dot and text for all states
function updateStatusUI() {
    const dot = document.getElementById('statusDot');
    const statusEl = document.getElementById('status');
    const latencyEl = document.getElementById('latencyDisplay');
    const offsetEl = document.getElementById('offsetDisplay');

    if (!socket.connected) {
        dot.className = 'w-2 h-2 rounded-full bg-red-500 animate-pulse';
        statusEl.innerText = 'Disconnected';
    } else if (isReady) {
        dot.className = 'w-2 h-2 rounded-full bg-emerald-500 animate-pulse';
        // Don't override status during playback
        if (statusEl.innerText === 'Disconnected' || statusEl.innerText === 'Hardware Offline') {
            statusEl.innerText = 'System Ready';
        }
    } else {
        dot.className = 'w-2 h-2 rounded-full bg-amber-500 animate-pulse';
        if (statusEl.innerText === 'Disconnected') {
            statusEl.innerText = 'Connected — Tap Start';
        }
    }

    latencyEl.innerText = Math.round(rtt) + 'ms';
    // Display sync jitter (std dev of offset samples) — lower is better
    offsetEl.innerText = '±' + syncJitter.toFixed(1) + 'ms';
}

setInterval(updateStatusUI, 500);

// ── Socket connection lifecycle ────────────────────────────────────
// Bug #9: Handle disconnect and reconnect for status feedback
socket.on('disconnect', () => {
    isReady = false;
    document.getElementById('status').innerText = 'Disconnected';
    updateStatusUI();
});

socket.on('connect', () => {
    document.getElementById('status').innerText = 'Connected';
    updateStatusUI();
    // Re-burst sync on reconnect
    for (let i = 0; i < 5; i++) setTimeout(syncTime, i * 200);
});

// ── Time synchronization ───────────────────────────────────────────
function syncTime() {
    if (!socket.connected) return;
    socket.emit('sync_ping', { client_ts: performance.now() });
}

socket.on('sync_pong', (data) => {
    const now = performance.now();
    const currentRtt = now - data.client_ts;
    rtt = currentRtt;

    // Server time is at the midpoint of RTT (one-way estimate)
    // offset = estimated_server_now - local_now
    const latestOffset = (data.server_ts + (currentRtt / 2)) - now;

    offsetSamples.push(latestOffset);
    if (offsetSamples.length > MAX_SAMPLES) offsetSamples.shift();

    // Bug #7: Use median instead of mean to reject outlier RTT samples
    // Median is far more robust against network jitter spikes
    serverOffset = medianOf(offsetSamples);

    // Compute jitter: standard deviation of offset samples around the median
    if (offsetSamples.length > 1) {
        const mean = offsetSamples.reduce((a, b) => a + b, 0) / offsetSamples.length;
        const variance = offsetSamples.reduce((sum, v) => sum + (v - mean) ** 2, 0) / offsetSamples.length;
        syncJitter = Math.sqrt(variance);
    }

    // Update telemetry for automation
    window.__sync_telemetry.rtt = rtt;
    window.__sync_telemetry.serverOffset = serverOffset;
    window.__sync_telemetry.syncJitter = syncJitter;
    window.__sync_telemetry.isReady = isReady;
});

function medianOf(arr) {
    if (arr.length === 0) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 !== 0
        ? sorted[mid]
        : (sorted[mid - 1] + sorted[mid]) / 2;
}

// Initial sync burst, then regular keep-alive
for (let i = 0; i < 5; i++) setTimeout(syncTime, i * 200);
setInterval(syncTime, 3000);

function getSynchronizedTime() {
    return performance.now() + serverOffset;
}

// ── Init & Play ────────────────────────────────────────────────────
async function initAndPlay() {
    // Bug #15: Use Number() instead of parseInt for robustness
    const delay = Number(document.getElementById('playDelay').value);

    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)({
            latencyHint: 'interactive'
        });
    }

    // Bug #20: Update button text through lifecycle
    document.getElementById('mainBtn').innerText = 'Requesting Play…';

    if (audioCtx.state === 'suspended') await audioCtx.resume();
    socket.emit('request_play', { delay_ms: delay });
}

// ── Join System & Record (Test Components) ────────────────────────
// Bug #22 & #25: Automated testing hooks
async function joinSystem() {
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)({
            latencyHint: 'interactive'
        });
    }
    if (audioCtx.state === 'suspended') await audioCtx.resume();
    document.getElementById('status').innerText = 'Joined — Waiting…';
    return true;
}

async function startInternalRecording() {
    if (!audioCtx) await joinSystem();
    
    console.log('[TEST] Initializing AudioWorklet for capture...');
    // Register the processor (idempotent check not possible in standard API, but we store the node)
    try {
        await audioCtx.audioWorklet.addModule('/static/js/recorder-worker.js');
    } catch (e) {
        console.warn('[TEST] AudioWorklet already added or failed to load:', e);
    }
    
    window.__pcm_chunks = [];
    
    // Create the recorder node
    const recorderNode = new AudioWorkletNode(audioCtx, 'recorder-worker', {
        numberOfInputs: 1,
        numberOfOutputs: 1,
        outputChannelCount: [2]
    });
    
    // Handle interleaved chunks from the worker thread
    recorderNode.port.onmessage = (e) => {
        if (window.__pcm_chunks) {
            window.__pcm_chunks.push(e.data);
        }
    };
    
    // Connect to destination to keep it alive (silent output)
    recorderNode.connect(audioCtx.destination);
    
    window.__test_recorder_node = recorderNode;
    window.__test_dest = recorderNode; // Link to our play_event connector
    
    console.log('[TEST] Internal AudioWorklet recording started.');
}

async function stopInternalRecording() {
    if (window.__test_recorder_node) {
        window.__test_recorder_node.disconnect();
        
        // Flatten and convert to Int16 for the server
        const totalLength = window.__pcm_chunks.reduce((acc, chunk) => acc + chunk.length, 0);
        const flatBuffer = new Float32Array(totalLength);
        let offset = 0;
        for (const chunk of window.__pcm_chunks) {
            flatBuffer.set(chunk, offset);
            offset += chunk.length;
        }

        // Send raw PCM to server
        const blob = new Blob([flatBuffer.buffer], { type: 'application/octet-stream' });
        const formData = new FormData();
        formData.append('audio', blob, 'sync_test.raw');
        formData.append('tab_id', Math.random().toString(36).substring(7));
        await fetch('/test/upload', { method: 'POST', body: formData });
        console.log('[TEST] Uploaded raw PCM recording.');
    }
}

// ── Audio preloader ────────────────────────────────────────────────
async function preloadAudio(url) {
    try {
        document.getElementById('status').innerText = 'Loading Audio…';
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const arrayBuffer = await response.arrayBuffer();
        audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
        loadedSongUrl = url;
        isReady = true;
        window.__sync_telemetry.isReady = true;
        document.getElementById('status').innerText = 'Audio Loaded';
    } catch (e) {
        console.error('Failed to load audio:', e);
        document.getElementById('status').innerText = 'Error: ' + e.message;
        isReady = false;
    }
}

// ── Play event handler ─────────────────────────────────────────────
socket.on('play_event', async (data) => {
    // Bug #18: Inform the user if AudioContext isn't initialized yet
    if (!audioCtx) {
        console.warn('[SYNC] Received play_event but AudioContext not initialized.');
        document.getElementById('status').innerText = 'Tap Start to join playback';
        document.getElementById('mainBtn').innerText = 'Join Playback';
        return;
    }

    // Bug #12: Re-fetch if the song URL changed
    if (!audioBuffer || data.songUrl !== loadedSongUrl) {
        await preloadAudio(data.songUrl);
    }
    if (!audioBuffer) return;

    // Bug #13: Stop and null the old source cleanly
    if (source) {
        try { source.stop(); } catch (e) { /* already stopped */ }
        source = null;
    }

    source = audioCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(audioCtx.destination);
    
    // Automation: Also connect to test recorder if present
    if (window.__test_dest) {
        source.connect(window.__test_dest);
    }

    const targetTimeMs = data.targetTimeMs;
    const currentServerTimeMs = getSynchronizedTime();

    // Bug #14: Use Number() instead of parseInt
    const fineTuneMs = Number(document.getElementById('fineTune').value);
    const adjustedTargetMs = targetTimeMs + fineTuneMs;

    const msUntilPlay = adjustedTargetMs - currentServerTimeMs;

    if (msUntilPlay > 0) {
        // High-precision scheduling via Web Audio clock
        const playTimeInAudioCtx = audioCtx.currentTime + (msUntilPlay / 1000);
        source.start(playTimeInAudioCtx);

        // Update telemetry for automation
        window.__sync_telemetry.lastScheduledMs = msUntilPlay;
        window.__sync_telemetry.targetTimeMs = targetTimeMs;
        window.__sync_telemetry.playbackStartLocal = performance.now() + msUntilPlay;

        // Bug #20: Update button to show playing state
        document.getElementById('mainBtn').innerText = '▶ Playing';
        document.getElementById('status').innerText = 'Synchronized';

        console.log(`[SYNC] Scheduling in ${msUntilPlay.toFixed(2)}ms | RTT: ${rtt.toFixed(1)}ms | Offset: ${serverOffset.toFixed(1)}ms`);
    } else {
        // Late join — start from the correct offset into the track
        const offsetSec = Math.abs(msUntilPlay) / 1000;

        // Bug #6: Guard against song having already finished
        if (offsetSec < audioBuffer.duration) {
            source.start(0, offsetSec);
            
            // Update telemetry for late join
            window.__sync_telemetry.lastScheduledMs = msUntilPlay;
            window.__sync_telemetry.targetTimeMs = targetTimeMs;
            window.__sync_telemetry.playbackStartLocal = performance.now();

            document.getElementById('mainBtn').innerText = '▶ Playing';
            document.getElementById('status').innerText = 'Late join synced';
            console.log(`[SYNC] Late join with offset ${offsetSec.toFixed(4)}s`);
        } else {
            console.warn('[SYNC] Song already finished, not joining.');
            document.getElementById('status').innerText = 'Song ended';
            document.getElementById('mainBtn').innerText = 'Start System';
            source = null;
        }
    }

    // Auto-reset button when playback ends naturally
    source && (source.onended = () => {
        document.getElementById('mainBtn').innerText = 'Start System';
        document.getElementById('status').innerText = 'Playback complete';
    });
});

// ── Stop event handler ─────────────────────────────────────────────
// Bug #10: Wrap in try/catch to prevent InvalidStateError
// Bug #19 & #20: Reset all UI state on stop
socket.on('stop_event', () => {
    if (source) {
        try { source.stop(); } catch (e) { /* already stopped */ }
        source = null;
    }
    document.getElementById('mainBtn').innerText = 'Start System';
    document.getElementById('status').innerText = 'Stopped';
});

// ── Slider label updaters ──────────────────────────────────────────
document.getElementById('fineTune').oninput = function () {
    document.getElementById('fineTuneVal').innerText = this.value + 'ms';
};

document.getElementById('playDelay').oninput = function () {
    document.getElementById('playDelayVal').innerText = this.value + 'ms';
};