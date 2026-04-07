from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import threading
import time
import os

app = Flask(__name__)
# Bug #2: Use environment variable, fall back to random secret
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(24).hex())

# Setting async_mode explicitly to 'threading' to avoid eventlet's start_joinable_thread error
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Offset boot-time-based performance counter to wall-clock epoch scale for clearer sync offsets
_EPOCH_OFFSET_MS = (time.time() * 1000) - (time.perf_counter_ns() / 1_000_000)


def get_now_ms():
    """Return high-precision server time in milliseconds on an Epoch scale."""
    return _EPOCH_OFFSET_MS + (time.perf_counter_ns() / 1_000_000.0)


# Bug #5: Thread-safe state with a lock
state_lock = threading.Lock()
state = {
    "isPlaying": False,
    "startTime": 0,
    "songUrl": "/static/music/mono_click_sync.wav",
}


@app.route("/")
def index():
    return render_template("index.html")


@app.after_request
def add_security_headers(response):
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Embedder-Policy"] = "credentialless"
    return response


# Bug #3: Removed redundant /static/music/ route — Flask serves /static/ automatically.


@app.route("/timesync", methods=["POST"])
def timesync():
    """Legacy endpoint for timesync.js compatibility."""
    data = request.get_json()
    # Bug #4: Validate input
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
    return jsonify({"id": data.get("id"), "result": get_now_ms()})


@socketio.on("sync_ping")
def handle_sync_ping(data):
    """
    High-precision Socket.IO time synchronization.
    Returns: client's original timestamp and the server's current epoch.
    """
    emit("sync_pong", {
        "client_ts": data.get("client_ts"),
        "server_ts": get_now_ms()
    })


@socketio.on("request_play")
def handle_play(data=None):
    # Bug #11: Validate and clamp delay_ms
    delay_ms = 2000
    if data and isinstance(data, dict):
        try:
            delay_ms = max(500, min(int(data.get("delay_ms", 2000)), 30000))
        except (TypeError, ValueError):
            delay_ms = 2000

    future_start = get_now_ms() + delay_ms

    # Bug #5: Thread-safe state mutation
    with state_lock:
        state["isPlaying"] = True
        state["startTime"] = future_start

    emit(
        "play_event",
        {"targetTimeMs": future_start, "songUrl": state["songUrl"]},
        broadcast=True,
    )


@socketio.on("request_stop")
def handle_stop():
    # Bug #5: Thread-safe state mutation
    with state_lock:
        state["isPlaying"] = False
        state["startTime"] = 0
    emit("stop_event", broadcast=True)


@socketio.on("connect")
def handle_connect():
    # Bug #5 & #6: Thread-safe read + late-join guard
    with state_lock:
        if state["isPlaying"] and state["startTime"] > 0:
            emit(
                "play_event",
                {
                    "targetTimeMs": state["startTime"],
                    "songUrl": state["songUrl"],
                    "isLateJoin": True,
                },
            )


# ── Testing & Automation Endpoints ─────────────────────────────────
# Bug #24: Receive parallel audio uploads for automated mixing
@app.route("/test/upload", methods=["POST"])
def upload_test_audio():
    if "audio" not in request.files:
        return jsonify({"error": "No file"}), 400
    
    file = request.files["audio"]
    tab_id = request.form.get("tab_id", "unknown")
    
    # Save to a dedicated test directory
    upload_dir = os.path.join(os.getcwd(), "tmp_sync")
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
        
    save_path = os.path.join(upload_dir, f"tab_{tab_id}.wav")
    file.save(save_path)
    return jsonify({"success": True, "path": save_path})


if __name__ == "__main__":
    socketio.run(app, debug=True, port=5000, host="0.0.0.0", allow_unsafe_werkzeug=True)
