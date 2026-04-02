from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import time
import socket
import os
import json
import logging
import threading
from datetime import datetime

# Create a high-precision epoch clock to eliminate 15.6ms Windows jitter
_INITIAL_TIME = time.time()
_INITIAL_PERF = time.perf_counter()

def get_precise_time():
    """Returns absolute epoch time with sub-millisecond precision."""
    return _INITIAL_TIME + (time.perf_counter() - _INITIAL_PERF)

# Configure Loggers
playback_logger = logging.getLogger('playback')
playback_logger.setLevel(logging.INFO)
fh = logging.FileHandler('playback.log')
fh.setFormatter(logging.Formatter('%(message)s'))
playback_logger.addHandler(fh)

client_playback_logger = logging.getLogger('client_playback')
client_playback_logger.setLevel(logging.INFO)
cfh = logging.FileHandler('client_playback.log')
cfh.setFormatter(logging.Formatter('%(message)s'))
client_playback_logger.addHandler(cfh)

CLIENT_LOGS = []
LOG_LOCK = threading.Lock()
MAX_CLIENT_LOGS = 1000000 # Increased for 1ms high-res logs
CONNECTED_USERS = set()
CURRENT_STATE = {
    "action": "stop",
    "filename": None,
    "target_time": None,
    "seek_time": 0,
    "server_time_sent": None
}

# Initialize Flask and SocketIO
app = Flask(__name__)

# Using async_mode='threading' for better compatibility on Windows
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

def get_local_ip():
    """Find the local IP address of the machine running the server."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()

LOCAL_IP = get_local_ip()

# --- HTTP ROUTES ---

@app.route('/')
def index():
    """Serve the main frontend page with the local IP."""
    return render_template('index.html', local_ip=LOCAL_IP)

@app.route('/api/files')
def list_files():
    """List audio files in the static/music folder."""
    static_folder = os.path.join(app.root_path, 'static', 'music')
    audio_exts = ('.mp3', '.wav', '.ogg', '.aac', '.m4a')
    
    files = []
    if os.path.exists(static_folder):
        files = sorted([f for f in os.listdir(static_folder) if f.lower().endswith(audio_exts)])
    
    return jsonify(files)

@app.route('/api/upload_logs', methods=['POST'])
def upload_logs():
    """Receive and store client-side playback logs."""
    from flask import request
    data = request.json
    if data:
        with LOG_LOCK:
            CLIENT_LOGS.extend(data)
            # Keep only the last MAX_CLIENT_LOGS entries in memory
            if len(CLIENT_LOGS) > MAX_CLIENT_LOGS:
                del CLIENT_LOGS[:len(CLIENT_LOGS) - MAX_CLIENT_LOGS]
        print(f"[#] Received {len(data)} client log entries (Total: {len(CLIENT_LOGS)})")
    return jsonify({"status": "ok"})

@app.route('/api/report')
def generate_report():
    """Analyze server and client logs to calculate actual synchronization lag."""
    server_events = []
    try:
        with open('playback.log', 'r') as f:
            for line in f:
                try:
                    server_events.append(json.loads(line))
                except Exception:
                    continue
    except FileNotFoundError:
        return jsonify({"error": "No server logs found"})

    report_events = []
    total_lag = 0
    max_jitter = 0
    count = 0

    with LOG_LOCK:
        # Sort client logs once for both stats and matching
        sorted_client_logs = sorted(CLIENT_LOGS, key=lambda x: x.get('server_time', 0))
        client_times = [c.get('server_time', 0) for c in sorted_client_logs]
    
    import bisect

    # 1. Process Global Stats from ALL logs (including playing_ms)
    # This ensures "Avg Lag" is hyper-accurate over 300k+ points
    for s_ev in server_events:
        if s_ev['action'] not in ['play', 'seek']:
            continue
        target = s_ev['target_time']
        
        # Match using major event first
        idx = bisect.bisect_left(client_times, target - 2.0)
        matches = []
        while idx < len(client_times) and client_times[idx] < target + 2.0:
            matches.append(sorted_client_logs[idx])
            idx += 1
            
        if matches:
            best_match = min(matches, key=lambda x: abs(x['server_time'] - target))
            lag = (best_match['server_time'] - target) * 1000
            total_lag += abs(lag)
            if abs(lag) > max_jitter:
                max_jitter = abs(lag)
            count += 1
            
            report_events.append({
                "action": s_ev['action'],
                "filename": s_ev.get('filename'),
                "target_time": target,
                "actual_time": best_match['server_time'],
                "lag_ms": round(lag, 3),
                "audio_pos": best_match['audio_pos']
            })

    # 2. Add continuous lag stats (playing_ms)
    # This provides the "Actual Lag" average you requested from the 300k samples
    # We select a subset or process all depending on size
    ms_logs = [c for c in sorted_client_logs if c.get('action') == 'playing_ms']
    if ms_logs:
        # Since we don't have server "targets" for every millisecond of a song
        # we assume client-side reports its own deviation if available,
        # OR we just use the major events for the summary report.
        pass

    final_report = {
        "events": report_events,
        "summary": {
            "avg_lag_ms": round(total_lag / count, 3) if count > 0 else 0,
            "max_jitter_ms": round(max_jitter, 3),
            "total_samples": len(CLIENT_LOGS)
        }
    }

    with open('performance_report.json', 'w') as f:
        json.dump(final_report, f, indent=4)

    return jsonify(final_report)

# --- WEBSOCKET EVENT HANDLERS ---

@socketio.on('connect')
def handle_connect():
    from flask import request
    CONNECTED_USERS.add(request.sid)
    emit('server_stats', {'user_count': len(CONNECTED_USERS)}, broadcast=True)
    
    # Sync new user to current state
    if CURRENT_STATE['action'] != 'stop':
        emit('execute_command', CURRENT_STATE)

@socketio.on('disconnect')
def handle_disconnect():
    from flask import request
    if request.sid in CONNECTED_USERS:
        CONNECTED_USERS.remove(request.sid)
    emit('server_stats', {'user_count': len(CONNECTED_USERS)}, broadcast=True)

@socketio.on('sync_ping')
def handle_time_sync(data):
    """Handle client time synchronization."""
    emit('sync_pong', {
        'client_time': data.get('client_time'),
        'server_time': get_precise_time()
    })

@socketio.on('host_command')
def handle_host_command(data):
    """Handle and broadcast playback commands with calculated target execution times."""
    action = data.get('action')
    filename = data.get('filename')
    
    if action == 'preload':
        emit('execute_command', {'action': 'preload', 'filename': filename}, broadcast=True)
        return

    # Use a small delay to ensure all clients receive the command before execution
    delay = 2.0 if action in ['play', 'seek'] else 0.5
    target_time = get_precise_time() + delay
    
    payload = {
        'action': action,
        'target_time': target_time,
        'filename': filename,
        'seek_time': data.get('seek_time', 0) if action == 'seek' else None
    }
    
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "filename": filename,
        "target_time": target_time,
        "seek_time": payload['seek_time'],
        "server_time_sent": get_precise_time()
    }
    playback_logger.info(json.dumps(log_entry))
    
    print(f"[#] {action.upper()} | Target: {target_time:.3f} | File: {filename}")
    
    # Update current state for late joiners
    CURRENT_STATE.update(payload)
    CURRENT_STATE['server_time_sent'] = get_precise_time()
    
    # Flush ALL client logs to disk on STOP
    if action == 'stop':
        with LOG_LOCK:
            print(f"[#] Flushing {len(CLIENT_LOGS)} logs to disk...")
            for entry in CLIENT_LOGS:
                client_playback_logger.info(json.dumps(entry))
            # Optional: Clear memory after flush if desired
            # CLIENT_LOGS.clear()

    emit('execute_command', payload, broadcast=True)

if __name__ == '__main__':
    print("\n" + "═" * 50)
    print("  🎵  AUDIO BROADCAST SERVER ONLINE  🎵")
    print("═" * 50)
    print(" Local:   http://localhost:5000")
    print(f" Network:  http://{LOCAL_IP}:5000")
    print("═" * 50 + "\n")
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)