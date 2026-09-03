let mediaRecorder;
let audioChunks = [];
let startTime;
let timerInterval;
let audioBlob = null;
let recordingDuration = 0;

const btnRecord = document.getElementById("btnRecord");
const btnStop = document.getElementById("btnStop");
const btnPlay = document.getElementById("btnPlay");
const btnUpload = document.getElementById("btnUpload");
const timerDisplay = document.getElementById("timerDisplay");
const audioPreview = document.getElementById("audioPreview");
const statusMsg = document.getElementById("statusMsg");

if (btnRecord) {
  btnRecord.addEventListener("click", startRecording);
}
if (btnStop) {
  btnStop.addEventListener("click", stopRecording);
}
if (btnUpload) {
  btnUpload.addEventListener("click", uploadRecording);
}

async function startRecording() {
  const sessionId = document.getElementById("session_id").value;
  if (!sessionId) {
    alert("Veuillez sélectionner une session avant d'enregistrer.");
    return;
  }

  audioChunks = [];
  audioBlob = null;

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data);
      }
    };

    mediaRecorder.onstop = () => {
      audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType || "audio/wav" });
      const audioUrl = URL.createObjectURL(audioBlob);
      audioPreview.src = audioUrl;
      audioPreview.style.display = "block";
      btnUpload.disabled = false;
      if (statusMsg) {
        statusMsg.innerHTML = `<span style="color: var(--success); font-weight: 600;">Enregistrement terminé ! Cliquez sur "Envoyer la donnée" pour enregistrer dans le corpus.</span>`;
      }
    };

    mediaRecorder.start();
    startTime = Date.now();
    timerInterval = setInterval(updateTimer, 1000);

    btnRecord.disabled = true;
    btnStop.disabled = false;
    btnUpload.disabled = true;
    timerDisplay.classList.add("active");
    if (statusMsg) statusMsg.textContent = "🔴 Enregistrement en cours...";
  } catch (err) {
    alert("Impossible d'accéder au microphone : " + err.message);
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
    mediaRecorder.stream.getTracks().forEach((track) => track.stop());
    clearInterval(timerInterval);
    timerDisplay.classList.remove("active");
    btnRecord.disabled = false;
    btnStop.disabled = true;
  }
}

function updateTimer() {
  const elapsedSeconds = Math.floor((Date.now() - startTime) / 1000);
  recordingDuration = elapsedSeconds;
  const minutes = String(Math.floor(elapsedSeconds / 60)).padStart(2, "0");
  const seconds = String(elapsedSeconds % 60).padStart(2, "0");
  timerDisplay.textContent = `${minutes}:${seconds}`;
}

async function uploadRecording() {
  if (!audioBlob) {
    alert("Aucun enregistrement disponible à envoyer.");
    return;
  }

  const sessionId = document.getElementById("session_id").value;
  const promptId = document.getElementById("prompt_id").value;

  if (!sessionId) {
    alert("Session manquante.");
    return;
  }

  const formData = new FormData();
  const mimeType = audioBlob.type || "audio/wav";
  let ext = "wav";
  if (mimeType.includes("webm")) ext = "webm";
  else if (mimeType.includes("ogg")) ext = "ogg";

  formData.append("file", audioBlob, `recording.${ext}`);
  formData.append("session_id", sessionId);
  if (promptId) formData.append("prompt_id", promptId);
  formData.append("duration_seconds", recordingDuration);

  btnUpload.disabled = true;
  if (statusMsg) statusMsg.textContent = "⏳ Upload vers MinIO et enregistrement des métadonnées...";

  try {
    const response = await fetch("/api/recordings", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || "Erreur lors de l'upload");
    }

    const data = await response.json();
    if (statusMsg) {
      statusMsg.innerHTML = `
        <div style="background: var(--success-light); border: 1px solid var(--success); padding: 1rem; border-radius: 8px;">
          <strong style="color: var(--success);">✅ Enregistrement réussi !</strong><br>
          Code Enregistrement : <strong>${data.recording_code}</strong><br>
          Clé MinIO : <code>${data.audio_object_key}</code><br>
          Statut : <span class="badge badge-uploaded">${data.recording_status}</span><br>
          <a href="/recordings/${data.id}" class="btn btn-secondary btn-sm" style="margin-top: 0.5rem;">Consulter / Valider l'audio</a>
        </div>
      `;
    }
  } catch (err) {
    btnUpload.disabled = false;
    if (statusMsg) {
      statusMsg.innerHTML = `<span style="color: var(--danger); font-weight: 600;">❌ Échec de l'enregistrement : ${err.message}</span>`;
    }
  }
}
