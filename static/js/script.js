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

document.querySelector("#btn-play").addEventListener("click", () => {
  socket.emit("play_request");

  playAudioFile(
    "/static/music/" + document.getElementById("file-select").value,
  );
});
