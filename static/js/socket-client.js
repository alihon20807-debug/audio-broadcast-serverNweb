/**
 * socket-client.js
 * Socket.io initialization and high-level event handling
 */

const isNgrok = window.location.hostname.includes('ngrok');

export const socket = io({
    transports: isNgrok ? ['polling'] : ['websocket', 'polling'],
    upgrade: !isNgrok,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    extraHeaders: isNgrok ? { "ngrok-skip-browser-warning": "true" } : {}
});

export function syncTime() {
    if (socket.connected) {
        socket.emit('sync_ping', { client_ts: performance.now() });
    }
}

export function requestPlay(delay) {
    socket.emit('request_play', { delay_ms: delay });
}

export function requestStop() {
    socket.emit('request_stop', {});
}
