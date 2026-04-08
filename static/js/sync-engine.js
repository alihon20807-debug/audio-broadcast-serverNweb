/**
 * sync-engine.js
 * Core synchronization logic for SyncAmp
 */

import { 
    MAX_OFFSET_SAMPLES, 
    MIN_RTT_LIFETIME_MS, 
    SPIKE_FACTOR, 
    MAX_RTT_HISTORY,
    AppState 
} from './constants.js';

let serverOffset    = 0;
let rtt             = 0;
let minRtt          = Infinity;
let minRttTimestamp = 0;
let offsetAtMinRtt  = 0;
let syncJitter      = 0;
let offsetSamples   = [];

/**
 * Compute the median of a numerical array.
 */
function medianOf(arr) {
    if (!arr.length) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 !== 0 
        ? sorted[mid] 
        : (sorted[mid - 1] + sorted[mid]) / 2;
}

export function resetSyncState() {
    serverOffset   = 0;
    rtt            = 0;
    minRtt         = Infinity;
    minRttTimestamp = 0;
    offsetAtMinRtt = 0;
    syncJitter     = 0;
    offsetSamples  = [];
    if (window.__sync_telemetry) {
        window.__sync_telemetry.rttHistory = [];
        window.__sync_telemetry.offsets = [];
    }
    console.log('[SYNC] Sync state reset.');
}

export function getSynchronizedTime() {
    return performance.now() + serverOffset;
}

export function processSyncPong(data, socket) {
    const now = performance.now();

    const clientTs = data?.client_ts;
    const serverTs = data?.server_ts;
    if (typeof clientTs !== 'number' || typeof serverTs !== 'number') {
        console.warn('[SYNC] Invalid sync_pong data — skipping.');
        return null;
    }

    const currentRtt = now - clientTs;

    if (currentRtt < 0 || !isFinite(currentRtt)) {
        console.warn(`[SYNC] Invalid RTT: ${currentRtt}ms — discarding.`);
        return null;
    }

    rtt = currentRtt;
    const computedOffset = serverTs - now + (currentRtt / 2);

    if (performance.now() - minRttTimestamp > MIN_RTT_LIFETIME_MS) {
        minRtt = Infinity;
    }

    if (currentRtt < minRtt) {
        minRtt = currentRtt;
        minRttTimestamp = performance.now();
        offsetAtMinRtt = computedOffset;
    }

    const spikeThreshold = Math.max(minRtt * SPIKE_FACTOR, minRtt + 50);
    if (isFinite(minRtt) && currentRtt > spikeThreshold) {
        console.warn(`[SYNC] Rejected spike: RTT=${currentRtt.toFixed(2)}ms (threshold=${spikeThreshold.toFixed(0)}ms)`);
    } else {
        offsetSamples.push(computedOffset);
        if (offsetSamples.length > MAX_OFFSET_SAMPLES) offsetSamples.shift();
    }

    serverOffset = medianOf(offsetSamples);

    if (offsetSamples.length > 1) {
        const mean = offsetSamples.reduce((a, b) => a + b, 0) / offsetSamples.length;
        const variance = offsetSamples.reduce((s, v) => s + (v - mean) ** 2, 0) / offsetSamples.length;
        syncJitter = Math.sqrt(variance);
    }

    const stable = syncJitter < 20 && offsetSamples.length >= 5;

    // Update telemetry
    const telemetry = window.__sync_telemetry;
    if (telemetry) {
        Object.assign(telemetry, {
            rtt: currentRtt,
            serverOffset,
            syncJitter,
            isStable: stable,
            lastRawOffset: computedOffset,
            transport: socket?.io?.engine?.transport?.name || 'unknown',
            offsets: offsetSamples,
        });
        if (telemetry.rttHistory.length >= MAX_RTT_HISTORY) {
            telemetry.rttHistory.shift();
        }
        telemetry.rttHistory.push(currentRtt);
    }

    return { stable, rtt, syncJitter, serverOffset };
}

export function clearOffsetSamples() {
    offsetSamples = [];
}

export function getSyncState() {
    return { rtt, serverOffset, syncJitter };
}
