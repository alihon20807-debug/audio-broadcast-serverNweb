import asyncio
import logging
import os
import time
import secrets
from quart import Quart, render_template, request, jsonify
import socketio
import uvicorn

# eventlet.monkey_patch()  # No longer needed with asyncio


# ── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ── App ─────────────────────────────────────────────────────────────
app = Quart(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "dev-only-change-me-in-production"
)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB upload limit

# ADMIN TOKEN removed per user request
log.info("App initialized (control protection disabled)")


# sio handles the WebSocket layer
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    logger=False,
    engineio_logger=False,
)
# Combined into single app definition (CORE-01 fix)
# socket_app = socketio.ASGIApp(sio, app) # Defined later in the file or used in run


# ── High-precision epoch anchor ─────────────────────────────────────
# Sample both clocks multiple times to minimize the instantaneous offset
# between time.time() and perf_counter_ns().
def _calibrate_epoch_offset(samples: int = 10) -> float:
    """Return the best estimate of (epoch_ms - perf_counter_ms)."""
    best_rtt = float("inf")
    best_offset = 0.0
    for _ in range(samples):
        t1 = time.perf_counter_ns()
        wall = time.time()
        t2 = time.perf_counter_ns()
        rtt_ns = t2 - t1
        mid_perf_ms = ((t1 + t2) / 2) / 1_000_000.0
        wall_ms = wall * 1000.0
        if rtt_ns < best_rtt:
            best_rtt = rtt_ns
            best_offset = wall_ms - mid_perf_ms
    log.info(
        "Epoch anchor calibrated: offset=%.3fms (jitter=%.3fms, %d samples)",
        best_offset,
        best_rtt / 1_000_000.0,
        samples,
    )
    return best_offset


_EPOCH_OFFSET_MS = _calibrate_epoch_offset()


def get_now_ms() -> float:
    """Return high-precision server time in milliseconds on an Epoch scale."""
    return _EPOCH_OFFSET_MS + (time.perf_counter_ns() / 1_000_000.0)


# ── Shared play state ──────────────────────────────────────────────
state_lock = asyncio.Lock()
state = {
    "isPlaying": False,
    "startTime": None,
    "songUrl": "/static/music/mono_click_sync.wav",
    "songDurationMs": 10_000,
    "connectedClients": 0,
}

# ── Simple Rate Limiter ─────────────────────────────────────────────
_ip_activity = {}


def is_rate_limited(ip: str, limit: int = 10, window: int = 1) -> bool:
    """True if IP has > limit requests in window."""
    now = time.time()
    times = [t for t in _ip_activity.get(ip, []) if now - t < window]
    if len(times) >= limit:
        return True
    times.append(now)
    _ip_activity[ip] = times
    return False


@app.before_request
async def ensure_csrf_cookie():
    """Set a CSRF cookie if it doesn't exist."""
    if not request.cookies.get("csrf_token"):
        # We'll set it in the after_request handler to ensure it's sent
        pass


@app.after_request
async def add_security_headers(response):
    # (SEC-02) Set CSRF cookie for double-submit protection
    if not request.cookies.get("csrf_token"):
        response.set_cookie(
            "csrf_token",
            secrets.token_hex(16),
            samesite="Lax",
            httponly=False,  # Must be readable by JS for header injection
        )

    # (SEC-11) require-corp enables full crossOriginIsolated for high-res timers
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
    # Additional hardening
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline'; "
        "font-src 'self'; "
        "connect-src 'self' ws: wss: https://cdnjs.cloudflare.com; "
        "img-src 'self' data:; "
        "frame-ancestors 'none';"
    )
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


# ── Routes ──────────────────────────────────────────────────────────
@app.route("/")
async def index():
    return await render_template("index.html")


@app.route("/health")
async def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "time_ms": get_now_ms()})


@app.route("/timesync", methods=["POST"])
async def timesync():
    """Legacy endpoint for timesync.js compatibility."""
    # (SEC-02) Validate CSRF via double-submit cookie
    expected = request.cookies.get("csrf_token")
    actual = request.headers.get("X-CSRF-Token")
    if not expected or actual != expected:
        return jsonify({"error": "CSRF failure"}), 403

    ip = request.remote_addr
    if is_rate_limited(ip, limit=20, window=1):
        return jsonify({"error": "Rate limited"}), 429

    data = await request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
    req_id = data.get("id")
    if req_id is not None and not isinstance(req_id, (str, int)):
        return jsonify({"error": "Invalid id"}), 400
    return jsonify({"id": req_id, "result": get_now_ms()})


# ── Socket events ──────────────────────────────────────────────────
@sio.on("connect")
async def handle_connect(sid, environ):
    # (CORE-02) Minimize lock contention by reading state then emitting outside
    current_play_info = None
    async with state_lock:
        state["connectedClients"] += 1
        client_count = state["connectedClients"]
        if state["isPlaying"] and state["startTime"] is not None:
            elapsed = get_now_ms() - state["startTime"]
            if elapsed < state["songDurationMs"]:
                current_play_info = {
                    "targetTimeMs": state["startTime"],
                    "songUrl": state["songUrl"],
                    "isLateJoin": True,
                }
            else:
                state["isPlaying"] = False
                state["startTime"] = None

    log.info("Client connected: %s (%d total)", sid, client_count)
    await sio.emit("client_count", {"count": client_count})
    if current_play_info:
        await sio.emit("play_event", current_play_info, to=sid)


@sio.on("disconnect")
async def handle_disconnect(sid):
    async with state_lock:
        state["connectedClients"] = max(0, state["connectedClients"] - 1)
        client_count = state["connectedClients"]
        # Auto-stop if all clients leave
        if client_count == 0 and state["isPlaying"]:
            state["isPlaying"] = False
            state["startTime"] = None
            log.info("All clients disconnected — auto-stopped playback")

    log.info("Client disconnected: %s (%d remaining)", sid, client_count)
    await sio.emit("client_count", {"count": client_count})


@sio.on("sync_ping")
async def handle_sync_ping(sid, data):
    """High-precision Socket.IO time synchronization."""
    if not isinstance(data, dict):
        return
    client_ts = data.get("client_ts")
    if client_ts is None or not isinstance(client_ts, (int, float)):
        return
    await sio.emit(
        "sync_pong", {"client_ts": client_ts, "server_ts": get_now_ms()}, to=sid
    )


@sio.on("request_play")
async def handle_play(sid, data=None):

    delay_ms = 2000
    if isinstance(data, dict):
        try:
            delay_ms = max(500, min(int(data.get("delay_ms", 2000)), 30000))
        except (TypeError, ValueError):
            delay_ms = 2000

    future_start = get_now_ms() + delay_ms

    async with state_lock:
        state["isPlaying"] = True
        state["startTime"] = future_start
        song_url = state["songUrl"]  # read inside lock

    await sio.emit(
        "play_event",
        {"targetTimeMs": future_start, "songUrl": song_url},
    )
    log.info(
        "Play scheduled at +%dms (target=%.1f) by session %s",
        delay_ms,
        future_start,
        sid,
    )


@sio.on("request_stop")
async def handle_stop(sid, data=None):

    async with state_lock:
        state["isPlaying"] = False
        state["startTime"] = None
    await sio.emit("stop_event")
    log.info("Playback stopped by session %s", sid)


def main():
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))

    if debug_mode:
        log.warning("Running in DEBUG mode — do NOT expose to public network!")

    # Combine into ASGI application
    socket_app = socketio.ASGIApp(sio, app)

    uvicorn.run(
        socket_app,
        host=host,
        port=port,
        log_level="info",
    )


# ── Entry point ────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
