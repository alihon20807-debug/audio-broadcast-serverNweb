/**
 * constants.js
 * Configuration and State enums for SyncAmp
 */

export const SYNC_BURST_GAP_MS = 200;    // base ms between burst pings
export const SYNC_JITTER_MS    = 50;     // (SYNC-03) random jitter to prevent burst collisions
export const SYNC_INTERVAL_MS  = 3000;   // periodic sync interval
export const MAX_OFFSET_SAMPLES = 20;    // sliding window size
export const MIN_RTT_LIFETIME_MS = 60000;// expire best-RTT anchor after 60s
export const SPIKE_FACTOR       = 3;     // reject RTT > minRtt × this
export const STATUS_POLL_MS     = 500;   // UI update interval
export const FETCH_TIMEOUT_MS   = 10000; // audio fetch timeout
export const MAX_RTT_HISTORY    = 200;   // cap telemetry array
export const SYNC_BURST_COUNT   = 10;    // number of pings in initial burst

export const AppState = Object.freeze({
    OFFLINE:      'OFFLINE',
    CONNECTED:    'CONNECTED',
    STABILIZING:  'STABILIZING',
    READY:        'READY',
    LOADING:      'LOADING',
    PLAYING:      'PLAYING',
    LATE_JOIN:    'LATE_JOIN',
    STOPPED:      'STOPPED',
    ENDED:        'ENDED',
    ERROR:        'ERROR',
});
