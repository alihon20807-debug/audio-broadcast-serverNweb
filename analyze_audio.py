import librosa
import numpy as np
import os
import matplotlib.pyplot as plt
from scipy.signal import correlate

# Configuration
REFERENCE_FILE = "reference.wav"
PRODUCTION_FILE = "prod_output.wav"
SYNC_THRESHOLD_MS = 10.0 # Stricter threshold for high-precision
CORRELATION_MIN_PASS = 0.6 # Minimum correlation coefficient to assume matching audio

def analyze_audio_sync():
    print(f"\n--- Starting High-Precision Correlation Analysis: {REFERENCE_FILE} vs {PRODUCTION_FILE} ---")
    
    if not os.path.exists(REFERENCE_FILE) or not os.path.exists(PRODUCTION_FILE):
        print("[ERROR] One of the wav files is missing. Run record_sync_test.py first.")
        return

    # Load audio (mono for correlation)
    y_ref, sr = librosa.load(REFERENCE_FILE, sr=None, mono=True)
    y_prod, _ = librosa.load(PRODUCTION_FILE, sr=sr, mono=True)

    # Trim silence to focus on active audio
    y_ref_trimmed, _ = librosa.effects.trim(y_ref)
    y_prod_trimmed, _ = librosa.effects.trim(y_prod)

    # 1. High-Precision Cross-Correlation
    # We correlate a segment of the audio to find the best alignment
    # Using a 2-second window for speed and reliability
    win_len = min(int(sr * 2.0), len(y_ref_trimmed), len(y_prod_trimmed))
    sig_ref = y_ref_trimmed[:win_len]
    sig_prod = y_prod_trimmed[:win_len]
    
    # Normalize signals for correlation
    sig_ref = (sig_ref - np.mean(sig_ref)) / (np.std(sig_ref) * len(sig_ref))
    sig_prod = (sig_prod - np.mean(sig_prod)) / (np.std(sig_prod))

    corr = correlate(sig_prod, sig_ref, mode='full')
    lags = np.arange(-win_len + 1, win_len)
    
    # Find the peak correlation
    peak_idx = np.argmax(corr)
    max_corr = corr[peak_idx]
    best_lag = lags[peak_idx]
    
    drift_ms = (best_lag / sr) * 1000.0

    print(f"[INFO] Max Correlation Coefficient: {max_corr:.4f}")
    if max_corr < CORRELATION_MIN_PASS:
        print("[WARNING] Low correlation! The recordings may be entirely different or corrupted.")
        print("[WARNING] Fallback to simple onset check recommended if this was expected.")
        # Proceed anyway but with a warning.
    
    # 2. Splay/Smear Analysis (Peak Width)
    # A perfect sync has a sharp correlation peak. 
    # Jitter creates multiple "mini-peaks" or a rounded top.
    # We measure the width at 90% height to estimate the sync "blur".
    threshold = max_corr * 0.9
    within_width = np.where(corr > threshold)[0]
    if len(within_width) > 0:
        width_samples = (np.max(within_width) - np.min(within_width))
        width_ms = (width_samples / sr) * 1000.0
    else:
        width_ms = 0.0

    is_synced = (abs(drift_ms) < SYNC_THRESHOLD_MS) and (width_ms < SYNC_THRESHOLD_MS)

    print("\n--- HIGH-PRECISION SYNC REPORT ---")
    print(f"Sample-Level Drift: {drift_ms:.4f}ms ({best_lag} samples)")
    print(f"Audio Smear (Phase Blur): {width_ms:.4f}ms")
    print(f"Sync Threshold: {SYNC_THRESHOLD_MS}ms")
    
    if is_synced:
        print("\n✅ RESULT: SYNC PASS")
        print(f"Phase alignment is within {drift_ms:.2f}ms with minimal blur.")
    else:
        print("\n❌ RESULT: SYNC FAIL")
        if abs(drift_ms) >= SYNC_THRESHOLD_MS:
            print(f"Drift exceeded threshold: {abs(drift_ms):.2f}ms > {SYNC_THRESHOLD_MS}ms")
        if width_ms >= SYNC_THRESHOLD_MS:
            print(f"Audio smear (jitter) exceeded threshold: {width_ms:.2f}ms > {SYNC_THRESHOLD_MS}ms")

    # 3. Enhanced Visualization (Zoomed In)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    
    # Waveform Overview
    ds_factor = 100
    ax1.plot(y_ref[::ds_factor], label='Reference', alpha=0.6, color='#2ecc71')
    ax1.plot(y_prod[::ds_factor], label='Mixed Production', alpha=0.4, color='#e74c3c')
    ax1.set_title("Waveform Overview (Downsampled)")
    ax1.legend()

    # Zoomed-In correlation view
    # We find the first major onset to zoom in on
    onsets = librosa.onset.onset_detect(y=y_ref_trimmed, sr=sr, units='samples')
    if len(onsets) > 0:
        zoom_start = onsets[0] - 500
        zoom_end = onsets[0] + 1500
        zoom_ref = y_ref_trimmed[zoom_start:zoom_end]
        zoom_prod = y_prod_trimmed[zoom_start:zoom_end]
        
        ax2.plot(zoom_ref, label='Reference', color='#2ecc71', linewidth=2)
        ax2.plot(zoom_prod, label='Production', color='#e74c3c', alpha=0.7)
        ax2.set_title(f"Sub-MS Alignment Zoom (Drift: {drift_ms:.2f}ms, Blur: {width_ms:.2f}ms)")
        ax2.set_xlabel("Samples")
        ax2.legend()
    else:
        ax2.text(0.5, 0.5, "No clear onsets for zoom", ha='center')

    plt.tight_layout()
    plt.savefig("sync_waveform_report.png")
    print("[INFO] High-precision waveform report saved to sync_waveform_report.png")

if __name__ == "__main__":
    analyze_audio_sync()
