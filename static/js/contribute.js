/**
 * ALORA Public Voluntary Contributor Flow (/contribuer)
 * Designed for non-technical smartphone users in Guinea:
 *  - One-time anonymous profile (no account, no jargon)
 *  - Big thumb controls + 15s-30s visual gauge + 2s hard minimum guard
 *  - Automatic offline IndexedDB queue & sync on reconnect
 */
(function () {
  const HARD_MIN_SECONDS = 2.0;
  const TARGET_SECONDS = 15.0;
  const GAUGE_MAX = 30.0;
  const SEEN_STORAGE_KEY = "alora_contrib_seen_v1";
  const MAX_LOCAL_SEEN = 150;

  let currentPrompt = null;
  let mediaRecorder = null;
  let activeStream = null;
  let audioChunks = [];
  let audioBlob = null;
  let startTime = 0;
  let durationSec = 0;
  let timerId = null;
  let audioCtx = null;
  let vuRaf = null;

  function loadStoredSeen() {
    try {
      const raw = localStorage.getItem(SEEN_STORAGE_KEY);
      if (!raw) return new Set();
      const arr = JSON.parse(raw);
      return new Set(Array.isArray(arr) ? arr.slice(-MAX_LOCAL_SEEN) : []);
    } catch (_) {
      return new Set();
    }
  }

  function saveStoredSeen(set) {
    try {
      localStorage.setItem(SEEN_STORAGE_KEY, JSON.stringify(Array.from(set).slice(-MAX_LOCAL_SEEN)));
    } catch (_) {}
  }

  const skippedIds = loadStoredSeen();

  function markPromptSeen(id) {
    if (!id) return;
    skippedIds.add(id);
    saveStoredSeen(skippedIds);
  }

  function clearPromptSeen() {
    skippedIds.clear();
    try { localStorage.removeItem(SEEN_STORAGE_KEY); } catch (_) {}
  }

  const stepOnboarding = document.getElementById("stepOnboarding");
  const stepRecord = document.getElementById("stepRecord");
  const stepDone = document.getElementById("stepDone");
  const onboardingForm = document.getElementById("onboardingForm");
  const onboardingError = document.getElementById("onboardingError");
  const btnStartContributing = document.getElementById("btnStartContributing");

  const cbCountBadge = document.getElementById("cbCountBadge");
  const btnChangePerson = document.getElementById("btnChangePerson");
  const cbPhotoTopic = document.getElementById("cbPhotoTopic");
  const cbPhotoFrame = document.getElementById("cbPhotoFrame");
  const cbPhotoImg = document.getElementById("cbPhotoImg");
  const cbPhotoCredit = document.getElementById("cbPhotoCredit");
  const recordInstruction = document.getElementById("recordInstruction");

  const cbRecorderCard = document.getElementById("cbRecorderCard");
  const cbTimer = document.getElementById("cbTimer");
  const cbHint = document.getElementById("cbHint");
  const cbGauge = document.getElementById("cbGauge");
  const cbGaugeFill = document.getElementById("cbGaugeFill");
  const cbVuFill = document.getElementById("cbVuFill");

  const stateIdle = document.getElementById("cbStateIdle");
  const stateRecording = document.getElementById("cbStateRecording");
  const stateReview = document.getElementById("cbStateReview");
  const btnRecord = document.getElementById("cbBtnRecord");
  const btnStop = document.getElementById("cbBtnStop");
  const btnSend = document.getElementById("cbBtnSend");
  const btnRetake = document.getElementById("cbBtnRetake");
  const btnSkip = document.getElementById("cbBtnSkip");
  const audioPreview = document.getElementById("cbAudioPreview");
  const reviewMsg = document.getElementById("cbReviewMsg");
  const feedbackMsg = document.getElementById("cbFeedback");

  const offlineBanner = document.getElementById("cbOfflineBanner");
  const offlineText = document.getElementById("cbOfflineText");
  const syncBtn = document.getElementById("cbSyncBtn");

  function fmtTime(sec) {
    const t = Math.max(0, Math.floor(sec));
    return `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`;
  }

  function pickMime() {
    if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) return "";
    for (const m of ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/webm", "audio/mp4"]) {
      if (MediaRecorder.isTypeSupported(m)) return m;
    }
    return "";
  }

  function extFromMime(mime) {
    const m = (mime || "").toLowerCase();
    if (m.includes("webm")) return "webm";
    if (m.includes("ogg")) return "ogg";
    if (m.includes("mp4") || m.includes("m4a")) return "m4a";
    return "wav";
  }

  function updateCount(n) {
    const plural = n > 1 ? "photos décrites" : "photo décrite";
    cbCountBadge.textContent = `${n} ${plural} · Merci !`;
  }

  function updateGauge(sec) {
    const pct = Math.min(100, (sec / GAUGE_MAX) * 100);
    cbGaugeFill.style.width = `${pct}%`;
    cbGauge.setAttribute("aria-valuenow", String(Math.round(sec)));
    cbGaugeFill.classList.remove("is-short", "is-good");
    cbHint.classList.remove("is-short", "is-good");

    if (sec <= 0) {
      cbHint.textContent = "Essayez de parler environ 15 secondes";
    } else if (sec < HARD_MIN_SECONDS) {
      cbGaugeFill.classList.add("is-short");
      cbHint.classList.add("is-short");
      cbHint.textContent = "Parlez encore quelques secondes…";
    } else if (sec < TARGET_SECONDS) {
      cbHint.textContent = "Très bien ! Continuez encore un peu…";
    } else {
      cbGaugeFill.classList.add("is-good");
      cbHint.classList.add("is-good");
      cbHint.textContent = "Super ! Vous pouvez arrêter quand vous voulez.";
    }
  }

  function setUiState(mode) {
    stateIdle.style.display = mode === "idle" ? "block" : "none";
    stateRecording.style.display = mode === "recording" ? "block" : "none";
    stateReview.style.display = mode === "review" ? "block" : "none";
    cbRecorderCard.classList.toggle("is-recording", mode === "recording");
    cbTimer.classList.toggle("active", mode === "recording");
  }

  function resetTake() {
    audioChunks = [];
    audioBlob = null;
    durationSec = 0;
    cbTimer.textContent = "00:00";
    updateGauge(0);
    audioPreview.removeAttribute("src");
    reviewMsg.style.display = "none";
    feedbackMsg.style.display = "none";
    setUiState("idle");
  }

  function startVu(stream) {
    stopVu();
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      audioCtx = new Ctx();
      const src = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      src.connect(analyser);
      const buf = new Uint8Array(analyser.frequencyBinCount);
      function loop() {
        analyser.getByteTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) {
          const v = (buf[i] - 128) / 128;
          sum += v * v;
        }
        cbVuFill.style.width = `${Math.min(100, Math.round(Math.sqrt(sum / buf.length) * 280))}%`;
        vuRaf = requestAnimationFrame(loop);
      }
      loop();
    } catch (_) {}
  }

  function stopVu() {
    if (vuRaf) { cancelAnimationFrame(vuRaf); vuRaf = null; }
    if (audioCtx) { try { audioCtx.close(); } catch (_) {} audioCtx = null; }
    cbVuFill.style.width = "0%";
  }

  async function loadNextPhoto() {
    resetTake();
    const params = new URLSearchParams();
    if (skippedIds.size > 0) params.set("exclude_ids", Array.from(skippedIds).join(","));

    try {
      const res = await fetch(`/api/public/next-prompt?${params.toString()}`);
      if (res.status === 401) {
        stepRecord.style.display = "none";
        stepOnboarding.style.display = "block";
        return;
      }
      const data = await res.json();
      updateCount(data.completed_count || 0);

      if (!data.prompt) {
        stepRecord.style.display = "none";
        stepDone.style.display = "block";
        return;
      }

      currentPrompt = data.prompt;
      cbPhotoTopic.textContent = currentPrompt.topic || "Scène du quotidien";
      recordInstruction.textContent =
        currentPrompt.prompt_type === "image"
          ? currentPrompt.content || "Racontez en soussou ce que vous voyez sur cette photo"
          : `Lisez cette phrase en soussou : « ${currentPrompt.content} »`;

      if (currentPrompt.media_object_key) {
        cbPhotoImg.src = `/api/prompts/${currentPrompt.id}/media`;
        cbPhotoImg.alt = currentPrompt.title || "Photo à décrire en soussou";
        cbPhotoFrame.style.display = "flex";
        cbPhotoCredit.textContent = currentPrompt.media_attribution
          ? `Photo : ${currentPrompt.media_attribution}${currentPrompt.media_license ? " · " + currentPrompt.media_license : ""}`
          : "";
      } else {
        cbPhotoFrame.style.display = "none";
        cbPhotoCredit.textContent = "";
      }
    } catch (_) {
      feedbackMsg.className = "cb-msg cb-msg-warn";
      feedbackMsg.textContent = "Connexion lente ou absente : vous pouvez réessayer dans un instant.";
      feedbackMsg.style.display = "block";
    }
  }

  async function refreshOfflineUI() {
    if (!window.AloraOfflineQueue) return;
    try {
      const items = (await window.AloraOfflineQueue.listPending()).filter((x) => x.mode === "public");
      if (!navigator.onLine || items.length > 0) {
        offlineBanner.style.display = "flex";
        offlineText.textContent =
          items.length > 0
            ? `${items.length} enregistrement(s) gardé(s) sur votre téléphone`
            : "Pas de connexion internet : vos voix seront gardées sur le téléphone.";
        syncBtn.style.display = items.length > 0 && navigator.onLine ? "inline-flex" : "none";
      } else {
        offlineBanner.style.display = "none";
      }
    } catch (_) {}
  }

  async function uploadPublicBlob(blob, promptId, durSec) {
    const fd = new FormData();
    const mime = blob.type || "audio/webm";
    fd.append("file", blob, `voix.${extFromMime(mime)}`);
    if (promptId) fd.append("prompt_id", promptId);
    fd.append("duration_seconds", String(Number(durSec || 0).toFixed(2)));

    const res = await fetch("/api/public/recordings", { method: "POST", body: fd });
    if (!res.ok) {
      let msg = "Erreur d'envoi";
      try { msg = (await res.json()).detail || msg; } catch (_) {}
      throw new Error(msg);
    }
    return res.json();
  }

  async function syncOfflinePublic() {
    if (!window.AloraOfflineQueue || !navigator.onLine) return;
    const all = await window.AloraOfflineQueue.listPending();
    const pub = all.filter((x) => x.mode === "public");
    for (const item of pub) {
      try {
        const data = await uploadPublicBlob(item.blob, item.promptId, item.durationSeconds);
        await window.AloraOfflineQueue.removePending(item.id);
        if (data.completed_count !== undefined) updateCount(data.completed_count);
      } catch (_) {
        break;
      }
    }
    await refreshOfflineUI();
  }

  async function startRec() {
    resetTake();
    try {
      activeStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: false, autoGainControl: true },
      });
      const mime = pickMime();
      mediaRecorder = mime ? new MediaRecorder(activeStream, { mimeType: mime }) : new MediaRecorder(activeStream);
      mediaRecorder.ondataavailable = (e) => { if (e.data && e.data.size > 0) audioChunks.push(e.data); };
      mediaRecorder.onstop = () => {
        stopVu();
        audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType || mime || "audio/webm" });
        audioPreview.src = URL.createObjectURL(audioBlob);
        setUiState("review");

        if (durationSec < HARD_MIN_SECONDS) {
          btnSend.disabled = true;
          reviewMsg.className = "cb-msg cb-msg-error";
          reviewMsg.textContent = "C'était trop court (moins de 2 secondes). Appuyez sur « Recommencer » et parlez quelques secondes.";
          reviewMsg.style.display = "block";
        } else if (durationSec < TARGET_SECONDS) {
          btnSend.disabled = false;
          reviewMsg.className = "cb-msg cb-msg-warn";
          reviewMsg.textContent = `C'est un peu court (${Math.round(durationSec)} s). Vous pouvez recommencer pour raconter plus de détails, ou envoyer directement.`;
          reviewMsg.style.display = "block";
        } else {
          btnSend.disabled = false;
          reviewMsg.className = "cb-msg cb-msg-ok";
          reviewMsg.textContent = `Bravo (${Math.round(durationSec)} s) ! Réécoutez si vous voulez, puis envoyez.`;
          reviewMsg.style.display = "block";
        }
      };

      mediaRecorder.start(250);
      startVu(activeStream);
      startTime = Date.now();
      setUiState("recording");

      timerId = setInterval(() => {
        durationSec = (Date.now() - startTime) / 1000;
        cbTimer.textContent = fmtTime(durationSec);
        updateGauge(durationSec);
      }, 200);
    } catch (err) {
      feedbackMsg.className = "cb-msg cb-msg-error";
      feedbackMsg.textContent = "Impossible d'ouvrir le micro. Autorisez le microphone dans votre navigateur puis réessayez.";
      feedbackMsg.style.display = "block";
      try {
        fetch("/api/public/client-error", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            context: "contribute_mic",
            error_name: err && err.name ? err.name : "MicError",
            error_message: err && err.message ? err.message : String(err),
            page_url: window.location.pathname,
          }),
        }).catch(() => {});
      } catch (_) {}
    }
  }

  function stopRec() {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      durationSec = (Date.now() - startTime) / 1000;
      cbTimer.textContent = fmtTime(durationSec);
      updateGauge(durationSec);
      clearInterval(timerId);
      mediaRecorder.stop();
      if (activeStream) {
        activeStream.getTracks().forEach((t) => t.stop());
        activeStream = null;
      }
    }
  }

  async function sendRec() {
    if (!audioBlob || durationSec < HARD_MIN_SECONDS) return;
    btnSend.disabled = true;
    btnSend.textContent = "Envoi en cours…";

    const pId = currentPrompt ? currentPrompt.id : null;

    if (!navigator.onLine && window.AloraOfflineQueue) {
      await window.AloraOfflineQueue.addPending({
        mode: "public",
        blob: audioBlob,
        promptId: pId,
        durationSeconds: durationSec,
      });
      await refreshOfflineUI();
      btnSend.textContent = "Envoyer et voir la photo suivante →";
      if (pId) markPromptSeen(pId);
      await loadNextPhoto();
      return;
    }

    try {
      const data = await uploadPublicBlob(audioBlob, pId, durationSec);
      if (pId) markPromptSeen(pId);
      updateCount(data.completed_count || 0);
      btnSend.textContent = "Envoyer et voir la photo suivante →";
      await loadNextPhoto();
      syncOfflinePublic();
    } catch (err) {
      if (window.AloraOfflineQueue && err instanceof TypeError) {
        await window.AloraOfflineQueue.addPending({
          mode: "public",
          blob: audioBlob,
          promptId: pId,
          durationSeconds: durationSec,
        });
        await refreshOfflineUI();
        btnSend.textContent = "Envoyer et voir la photo suivante →";
        feedbackMsg.className = "cb-msg cb-msg-warn";
        feedbackMsg.textContent = "Pas de souci ! Votre voix est gardée sur le téléphone et sera envoyée dès que la connexion revient.";
        feedbackMsg.style.display = "block";
        return;
      }
      btnSend.disabled = false;
      btnSend.textContent = "Envoyer et voir la photo suivante →";
      reviewMsg.className = "cb-msg cb-msg-error";
      reviewMsg.textContent = err.message || "Erreur lors de l'envoi.";
      reviewMsg.style.display = "block";
    }
  }

  // Onboarding submit
  onboardingForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    onboardingError.style.display = "none";
    const fd = new FormData(onboardingForm);
    const consent = document.getElementById("cbConsent").checked;

    btnStartContributing.disabled = true;
    try {
      const res = await fetch("/api/public/onboarding", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          gender: fd.get("gender") || "female",
          age_group: fd.get("age_group") || "18-25",
          region: fd.get("region") || "Conakry",
          language: "sus",
          is_native_speaker: fd.get("is_native_speaker") !== "no",
          consent_accepted: consent,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Erreur");
      }
      stepOnboarding.style.display = "none";
      stepRecord.style.display = "block";
      await loadNextPhoto();
    } catch (err) {
      onboardingError.textContent = err.message;
      onboardingError.style.display = "block";
    } finally {
      btnStartContributing.disabled = false;
    }
  });

  btnChangePerson.addEventListener("click", async () => {
    await fetch("/api/public/reset-profile", { method: "POST" });
    clearPromptSeen();
    stepRecord.style.display = "none";
    stepDone.style.display = "none";
    stepOnboarding.style.display = "block";
  });

  const btnResetSeen = document.getElementById("cbResetSeenBtn");
  if (btnResetSeen) {
    btnResetSeen.addEventListener("click", async () => {
      clearPromptSeen();
      stepDone.style.display = "none";
      stepRecord.style.display = "block";
      await loadNextPhoto();
    });
  }

  const bugBtn = document.getElementById("cbOpenBugModal");
  const bugDialog = document.getElementById("cbBugDialog");
  const bugClose = document.getElementById("cbBugClose");
  const bugForm = document.getElementById("cbBugForm");
  const bugStatus = document.getElementById("cbBugStatus");
  const bugSubmit = document.getElementById("cbBugSubmit");
  if (bugBtn && bugDialog && bugForm) {
    bugBtn.addEventListener("click", () => {
      if (bugStatus) bugStatus.style.display = "none";
      bugDialog.showModal();
    });
    if (bugClose) bugClose.addEventListener("click", () => bugDialog.close());
    bugForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (bugSubmit) bugSubmit.disabled = true;
      const fd = new FormData(bugForm);
      try {
        const res = await fetch("/api/public/bug-report", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: fd.get("message"),
            sender_contact: fd.get("sender_contact") || "",
            page_url: window.location.pathname,
            user_agent: navigator.userAgent,
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Erreur d'envoi");
        if (bugStatus) {
          bugStatus.className = "cb-msg cb-msg-ok";
          bugStatus.textContent = data.message || "Merci ! Signalement envoyé.";
          bugStatus.style.display = "block";
        }
        bugForm.reset();
      } catch (err) {
        if (bugStatus) {
          bugStatus.className = "cb-msg cb-msg-error";
          bugStatus.textContent = err.message || "Impossible d'envoyer.";
          bugStatus.style.display = "block";
        }
      } finally {
        if (bugSubmit) bugSubmit.disabled = false;
      }
    });
  }

  btnRecord.addEventListener("click", startRec);
  btnStop.addEventListener("click", stopRec);
  btnSend.addEventListener("click", sendRec);
  btnRetake.addEventListener("click", resetTake);
  btnSkip.addEventListener("click", () => {
    if (currentPrompt) markPromptSeen(currentPrompt.id);
    loadNextPhoto();
  });
  syncBtn.addEventListener("click", syncOfflinePublic);

  window.addEventListener("online", () => { refreshOfflineUI(); syncOfflinePublic(); });
  window.addEventListener("offline", refreshOfflineUI);

  document.addEventListener("DOMContentLoaded", async () => {
    await refreshOfflineUI();
    try {
      const me = await (await fetch("/api/public/me")).json();
      if (me.has_profile) {
        stepOnboarding.style.display = "none";
        stepRecord.style.display = "block";
        updateCount(me.completed_count || 0);
        await loadNextPhoto();
      }
    } catch (_) {}
  });
})();
