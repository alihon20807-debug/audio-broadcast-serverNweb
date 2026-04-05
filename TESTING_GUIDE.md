# Audio Synchronization Testing Suite: User Guide

This testing suite provides high-fidelity, sub-millisecond measurement of audio synchronization across multiple browser instances. It combines automated Playwright orchestration with a high-precision cross-correlation analysis engine.

---

## 1. Prerequisites

Ensure you have the following installed on your machine:

### Python Dependencies
```bash
pip install playwright librosa numpy scipy matplotlib flask flask-socketio
playwright install chromium
```

### Server Setup
The test assumes the `audio broad` application is available and can be started via `python app.py`.

---

## 2. Using the Test Suite

The test workflow consists of two main phases: **Recording** and **Analysis**.

### Phase 1: Recording Sync Test
This script automatically starts the Flask server, launches a "Reference" (1 tab) recording, and then a "Production" (6 tabs) recording.

**Command:**
```bash
python record_sync_test.py
```

- **Output**: 
  - `reference.wav`: Baseline recording (single tab).
  - `prod_output.wav`: Combined recording (six synchronized tabs).
- **Simultaneity**: The script triggers `Record` and `Play` commands to all tabs exactly at the same time using `asyncio.gather`.

### Phase 2: High-Precision Analysis
Once the `.wav` files are generated, use the analysis script to measure the synchronization accuracy.

**Command:**
```bash
python analyze_audio.py
```

- **Output**: 
  - `sync_waveform_report.png`: A visual report showing the waveform overview and a millisecond-scale alignment zoom.
  - **Terminal Report**: Detailed drift and smear measurements.

---

## 3. Interpreting Results

The analysis engine provides several key metrics to help you assess the quality of the synchronization:

### Sample-Level Drift
- **What it is**: The time difference (in ms) between the first significant peak in the Reference and the first significant peak in the Production recording.
- **Ideal Value**: < 10.0ms.

### Audio Smear (Phase Blur)
- **What it is**: A measure of the "width" of the correlation peak. If tabs are perfectly in phase, the smear will be low (near 0ms). If tabs are slightly staggered, the peak will appear "smeared" or wide.
- **Why it matters**: High smear indicates **jitter** (inconsistent offsets), which causes the audio to sound "flangy" or echoey even if the average drift is low.

### Correlation Coefficient
- **What it is**: A value from 0 to 1 indicating how similar the Production audio is to the Reference.
- **Threshold**: Values below **0.60** indicate that the recordings do not match well (possibly due to massive lag or corrupted recording).

---

## 4. Visualization Report (`sync_waveform_report.png`)

- **Waveform Overview**: Shows the entire recording. Useful for checking for major drops or volume issues.
- **Sub-MS Alignment Zoom**: Zooms in on the very first transient (the first "click") to show you exactly how the waveforms align at the micro level. Green is Reference, Red is Production.

---

## 5. Configuration (Adjusting Thresholds)

You can modify settings at the top of the scripts:

### `analyze_audio.py`
- `SYNC_THRESHOLD_MS`: Set your "Pass/Fail" limit (Default: 10.0ms).
- `CORRELATION_MIN_PASS`: Minimum similarity check (Default: 0.6).

### `record_sync_test.py`
- `RECORD_SECONDS`: How long each test phase runs (Default: 15s).
- `SERVER_URL`: The target address of your Flask app.

---

## Troubleshooting

> [!WARNING]
> **Headless Environments**: If running in a CI environment (like GitHub Actions), ensure that audio hardware is emulated correctly. Playwright handles this by default in Chromium, but other browsers might vary.

> [!CAUTION]
> **CPU Pressure**: Launching 6+ browsers simultaneously is CPU-intensive. If your machine is under heavy load, the reported "Audio Smear" may increase artificially.
