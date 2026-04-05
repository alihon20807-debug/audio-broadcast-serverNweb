const socket = io();

function load_songs() {
  fetch("/api/files")
    .then((response) => response.json())
    .then((data) => {
      const file_select = document.getElementById("file-select");
      file_select.innerHTML = "";
      data.forEach((file) => {
        const option = document.createElement("option");
        option.value = file;
        option.text = file;
        file_select.appendChild(option);
      });

      file_select.addEventListener("change", () => {
        if (typeof audioCtx !== "undefined" && audioCtx) {
          loadAudio(audioCtx, "/static/music/" + file_select.value);
        }
      });
      loadAudio(audioCtx, "/static/music/" + file_select.firstChild.value);
    });
}

function getCurrentEpochTime() {
  return performance.timeOrigin + performance.now();
}

socket.on("connect", () => {
  console.log("Connected to server");
  document.getElementById("stat-conn-text").innerText = "Connected";
  load_songs();
});

socket.on("disconnect", () => {
  console.log("Disconnected from server");
});
socket.on("message", (data) => {
  console.log("Message from server:", data);
});

socket.on("remote_play", (data) => {
  playAudioFile("/static/music/" + data.filename, data.startTime);
  console.log("Recieved Remote play:", data);
});

document.querySelector("#btn-play").addEventListener("click", () => {
  let startTime = getCurrentEpochTime() + 5000;
  socket.emit("schedule_play", {
    startTime: startTime,
    filename: document.getElementById("file-select").value,
  });

  // THIS IS SO INSANELY RETARDED
  // Cuz of all recivebraodcast ==> double fire
  // playAudioFile(
  //   "/static/music/" + document.getElementById("file-select").value,
  //   startTime,
  // );

  console.log("Sent Scheduled play at", startTime);
});
