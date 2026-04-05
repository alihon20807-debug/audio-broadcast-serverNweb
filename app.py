from flask import render_template
from flask import Flask, render_template_string, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import time
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = "sync_secret_key_123"

# Setting async_mode explicitly to 'threading' to avoid eventlet's start_joinable_thread error
# In a true production environment with eventlet, you would use 'eventlet' and
# call eventlet.monkey_patch() at the very top of the file.
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
# Offset boot-time-based performance counter to wall-clock epoch scale for clearer sync offsets
_EPOCH_OFFSET_MS = (time.time() * 1000) - (time.perf_counter_ns() / 1_000_000)

def get_now_ms():
    """Return high-precision server time in milliseconds on an Epoch scale."""
    return _EPOCH_OFFSET_MS + (time.perf_counter_ns() / 1_000_000)

# In-memory state for the current playback session
state = {
    "isPlaying": False,
    "startTime": 0,
    # Path to your local static file
    "songUrl": "/static/music/mono_click_sync.wav",
}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/static/music/<path:filename>")
def serve_music(filename):
    """Explicitly serve the music file from the static directory."""
    return send_from_directory("static/music", filename)


@app.route("/timesync", methods=["POST"])
def timesync():
    """
    Endpoint for timesync.js.
    It expects a JSON with an 'id' and returns the server's current epoch.
    """
    data = request.get_json()
    return jsonify({"id": data.get("id"), "result": get_now_ms()})


@socketio.on("request_play")
def handle_play():
    # Schedule start 2 seconds (2000ms) into the future
    future_start = get_now_ms() + 2000
    state["isPlaying"] = True
    state["startTime"] = future_start

    emit(
        "play_event",
        {"targetTimeMs": future_start, "songUrl": state["songUrl"]},
        broadcast=True,
    )


@socketio.on("request_stop")
def handle_stop():
    state["isPlaying"] = False
    emit("stop_event", broadcast=True)


@socketio.on("connect")
def handle_connect():
    if state["isPlaying"]:
        emit(
            "play_event",
            {"targetTimeMs": state["startTime"], "songUrl": state["songUrl"]},
        )


if __name__ == "__main__":
    # Use 'threading' mode to avoid eventlet compatibility issues in basic environments
    socketio.run(app, debug=True, port=5000, host="0.0.0.0", allow_unsafe_werkzeug=True)
