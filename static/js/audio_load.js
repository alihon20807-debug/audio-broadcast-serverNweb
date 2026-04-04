const AudioContextClass = window.AudioContext || window.webkitAudioContext;
let audioCtx = new AudioContextClass();
let AudioBuffer;

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

  console.log("Test tone played");
}

function playSound(ctx, audioBuffer) {
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
  source.start();

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

async function playAudioFile(url) {
  const buffer = await loadAudio(audioCtx, url);
  playSound(audioCtx, buffer);
}

document.querySelector("#btn-stop").addEventListener("click", () => {
  stopSound(audioCtx);
});

document.querySelector("#btn-join").addEventListener("click", () => {
  initAudio(audioCtx);
});
