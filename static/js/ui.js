/**
 * ui.js
 * DOM caching and UI status management
 */

import { AppState } from './constants.js';

export const dom = {};

const DOT_CLASSES = {
    red:     'status-dot animate-pulse red',
    amber:   'status-dot animate-pulse amber',
    emerald: 'status-dot animate-pulse emerald',
    slate:   'status-dot slate',
};

const STATE_DISPLAY = {
    [AppState.OFFLINE]:     { dot: 'red',     text: 'Disconnected' },
    [AppState.CONNECTED]:   { dot: 'amber',   text: 'Connected — Tap Start' },
    [AppState.STABILIZING]: { dot: 'amber',   text: 'Stabilizing…' },
    [AppState.READY]:       { dot: 'emerald', text: 'System Ready' },
    [AppState.LOADING]:     { dot: 'amber',   text: 'Loading Audio…' },
    [AppState.PLAYING]:     { dot: 'emerald', text: 'Synchronized' },
    [AppState.LATE_JOIN]:   { dot: 'emerald', text: 'Late join synced' },
    [AppState.STOPPED]:     { dot: 'slate',   text: 'Stopped' },
    [AppState.ENDED]:       { dot: 'slate',   text: 'Playback complete' },
    [AppState.ERROR]:       { dot: 'red',     text: 'Error' },
};

export function cacheDom() {
    dom.status       = document.getElementById('status-text');
    dom.statusDot    = document.getElementById('status-dot');
    dom.clientBadge  = document.getElementById('client-badge');
    dom.clientCount  = document.getElementById('client-count');
    dom.offset       = document.getElementById('offset-display');
    dom.latency      = document.getElementById('latency-display');
    dom.mainBtn      = document.getElementById('main-btn');
    dom.stopBtn      = document.getElementById('stop-btn');
    dom.playDelay    = document.getElementById('play-delay');
    dom.fineTune     = document.getElementById('fine-tune');
    dom.playDelayVal = document.getElementById('play-delay-val');
    dom.fineTuneVal  = document.getElementById('fine-tune-val');
}

export function setDot(color) {
    if (dom.statusDot) {
        dom.statusDot.className = DOT_CLASSES[color] || DOT_CLASSES.slate;
    }
}

export function updateStatusUI(state, rtt, syncJitter, detail) {
    if (!dom.status) return;

    const display = STATE_DISPLAY[state] || STATE_DISPLAY[AppState.OFFLINE];
    setDot(display.dot);
    dom.status.innerText = detail || display.text;
    
    // Auto-show/hide client badge based on connection
    if (dom.clientBadge) {
        if (state === AppState.OFFLINE) {
            dom.clientBadge.classList.add('hidden');
        } else {
            dom.clientBadge.classList.remove('hidden');
        }
    }

    if (dom.latency && rtt !== undefined) {
        dom.latency.innerText = Math.round(rtt) + 'ms';
    }
    
    if (dom.offset && syncJitter !== undefined) {
        dom.offset.innerText  = '±' + syncJitter.toFixed(1) + 'ms';
    }
}

export function updateClientCount(count) {
    if (dom.clientCount) {
        dom.clientCount.innerText = `${count} ${count === 1 ? 'Client' : 'Clients'}`;
    }
    if (dom.clientBadge && count > 0) {
        dom.clientBadge.classList.remove('hidden');
    }
}

export function initSliders() {
    ['fine-tune', 'play-delay'].forEach(id => {
        const el = document.getElementById(id);
        const valEl = document.getElementById(id + '-val');
        if (el && valEl) {
            el.oninput = function () { 
                valEl.innerText = this.value + 'ms'; 
                el.setAttribute('aria-valuenow', this.value);
            };
        }
    });
}
