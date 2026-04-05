const AudioContextClass = window.AudioContext || window.webkitAudioContext;
let audioCtx = new AudioContextClass();
let audioCtxStartTime = performance.now();
let AudioBuffer;
let CurrentFileUrl = "";

/**
 * Converts a future Epoch/Unix timestamp (in milliseconds)
 * to the equivalent AudioContext.currentTime.
 */
function epochToAudioTime(epochTargetMs, audioCtx) {
  const ts = audioCtx.getOutputTimestamp();

  // performanceTime: The performance.now() value for this sample
  // contextTime: The audioCtx.currentTime value for this sample
  const { performanceTime, contextTime } = ts;

  // 1. Calculate how far the target is from the page's time origin
  const targetPerfTime = epochTargetMs - performance.timeOrigin;

  // 2. Find the delta between now and target in performance-time
  const deltaMs = targetPerfTime - performanceTime;

  // 3. Add that delta (in seconds) to the audio context time
  return contextTime + deltaMs / 1000;
}

function audioTimeToEpoch(audioTime, audioCtx) {
  const ts = audioCtx.getOutputTimestamp();

  // 1. Calculate the distance (in seconds) between
  //    the target audioTime and the snapshot contextTime
  const deltaSeconds = audioTime - ts.contextTime;

  // 2. Convert that delta to milliseconds
  const deltaMs = deltaSeconds * 1000;

  // 3. Map it to the Performance clock, then to the Wall clock
  const targetPerfTime = ts.performanceTime + deltaMs;
  const epochTime = performance.timeOrigin + targetPerfTime;

  return epochTime;
}

function getCurrentEpochTime() {
  return performance.timeOrigin + performance.now();
}

function calcAccuracy() {
  const audioTime = epochToAudioTime(
    performance.timeOrigin + performance.now(),
    audioCtx,
  );
  return audioTime - audioCtx.currentTime;
}

function initAudio(ctx) {
  if (ctx.state === "suspended") {
    ctx.resume();
  }

  console.log("Audio Context is active:", ctx.state);

  playTestTone(ctx);

  document.getElementById("join-section").style.display = "none";
  document.getElementById("controls-section").style.display = "block";
  document.getElementById("controls-section").style.opacity = 1;
}

function playTestTone(ctx) {
  const oscillator = ctx.createOscillator();
  const gainNode = ctx.createGain();

  oscillator.type = "sine";
  oscillator.frequency.setValueAtTime(440, ctx.currentTime); // A4 tone

  gainNode.gain.setValueAtTime(0.1, ctx.currentTime);
  gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);

  oscillator.connect(gainNode);
  gainNode.connect(ctx.destination);

  oscillator.start();
  oscillator.stop(ctx.currentTime + 0.5);
  console.log(ctx.currentTime);

  console.log("Test tone played");
}

function playSound(ctx, audioBuffer, epochStartTime = 0) {
  if (!ctx || !audioBuffer) return;

  if (ctx.state === "suspended") {
    ctx.resume();
  }

  // stop the previous one
  if (ctx.activeSource) {
    try {
      ctx.activeSource.stop();
    } catch (e) {
      // Ignored: already stopped or finished
    }
  }

  const source = ctx.createBufferSource();
  source.buffer = audioBuffer;

  source.connect(ctx.destination);
  startTime =
    epochStartTime == 0
      ? ctx.currentTime
      : // : ctx.currentTime + (epochStartTime - getCurrentEpochTime()) / 1000;
      epochToAudioTime(epochStartTime, ctx);

  console.log("Current time", ctx.currentTime);
  console.log("Current Epoch Time", getCurrentEpochTime());
  console.log("Gonna play audio at", startTime);
  console.log("Scheduled Epoch Start Time", epochStartTime);
  console.log("Scheduled Audio Epoch Time", audioTimeToEpoch(startTime, ctx));
  source.start(startTime);

  ctx.activeSource = source;

  source.onended = () => {
    if (ctx.activeSource === source) {
      ctx.activeSource = null;
    }
  };

  return source;
}

async function loadAudio(ctx, url) {
  const response = await fetch(url);
  const arrayBuffer = await response.arrayBuffer();
  const audioBuffer = await ctx.decodeAudioData(arrayBuffer);
  AudioBuffer = audioBuffer;
  console.log("Loaded Buffer of " + url);
  return audioBuffer;
}

function stopSound(ctx) {
  if (ctx.activeSource) {
    try {
      ctx.activeSource.stop();
    } catch (e) {
      console.log("Audio already stopped");
    }
    ctx.activeSource = null;
  }
}

async function playAudioFile(url, startTime = 0) {
  const buffer = await loadAudio(audioCtx, url);
  playSound(audioCtx, buffer, startTime);
}

document.querySelector("#btn-stop").addEventListener("click", () => {
  stopSound(audioCtx);
});

document.querySelector("#btn-join").addEventListener("click", () => {
  initAudio(audioCtx);
});
