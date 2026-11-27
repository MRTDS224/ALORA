/**
 * ALORA Mobile-First Field Recorder
 * - Cross-browser MediaRecorder MIME negotiation (Chrome WebM, Firefox OGG, Safari MP4)
 * - Live Web Audio VU meter
 * - WAXAL duration target feedback (non-blocking warning + instant retake)
 * - Per-speaker stimulus rotation via GET /api/prompts/next
 * - Offline IndexedDB queue with automatic sync on reconnect
 */
(function () {
  let mediaRecorder = null;
  let audioChunks = [];
  let startTime = 0;
  let timerInterval = null;
  let audioBlob = null;
  let recordingDuration = 0;
  let audioContext = null;
  let vuRafId = null;
  let activeStream = null;
  const skippedPromptIds = new Set();

  const sessionSelect = document.getElementById("session_id");
  const promptSelect = document.getElementById("prompt_id");
  const btnNextPrompt = document.getElementById("btnNextPrompt");
  const btnRecord = document.getElementById("btnRecord");
  const btnStop = document.getElementById("btnStop");
  const btnRetake = document.getElementById("btnRetake");
  const btnUpload = document.getElementById("btnUpload");
  const recorderBox = document.getElementById("recorderBox");
  const timerDisplay = document.getElementById("timerDisplay");
  const durationGoal = document.getElementById("durationGoal");
  const durationGauge = document.getElementById("durationGauge");
  const durationGaugeFill = document.getElementById("durationGaugeFill");
  const durationIdealZone = document.getElementById("durationIdealZone");
  const durationTargetMarker = document.getElementById("durationTargetMarker");
  const gaugeTargetLabel = document.getElementById("gaugeTargetLabel");
  const vuMeterFill = document.getElementById("vuMeterFill");
  const HARD_MIN_SECONDS = 2.0;
  const IDEAL_MAX_SECONDS = 30.0;
  const SOFT_LONG_SECONDS = 40.0;
  const audioPreviewWrap = document.getElementById("audioPreviewWrap");
  const audioPreview = document.getElementById("audioPreview");
  const statusMsg = document.getElementById("statusMsg");
  const networkPill = document.getElementById("networkPill");
  const sessionProgressLabel = document.getElementById("sessionProgressLabel");
  const taskBadge = document.getElementById("sessionTaskBadge");
  const offlineBar = document.getElementById("offlineQueueBar");
  const offlineCountText = document.getElementById("offlineCountText");
  const btnSyncOffline = document.getElementById("btnSyncOffline");

  function pickSupportedMimeType() {
    if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) {
      return "";
    }
    const candidates = [
      "audio/webm;codecs=opus",
      "audio/ogg;codecs=opus",
      "audio/webm",
      "audio/ogg",
      "audio/mp4",
    ];
    for (const mime of candidates) {
      if (MediaRecorder.isTypeSupported(mime)) {
        return mime;
      }
    }
    return "";
  }

  function extensionFromMime(mime) {
    const m = (mime || "").toLowerCase();
    if (m.includes("webm")) return "webm";
    if (m.includes("ogg")) return "ogg";
    if (m.includes("mp4") || m.includes("m4a")) return "m4a";
    return "wav";
  }

  function getMinDurationTarget() {
    if (!promptSelect || !promptSelect.value) return 10;
    const opt = promptSelect.options[promptSelect.selectedIndex];
    const raw = opt ? opt.getAttribute("data-min-duration") : "";
    const parsed = parseFloat(raw);
    if (!Number.isNaN(parsed) && parsed > 0) return parsed;
    const pType = opt ? opt.getAttribute("data-type") : "";
    return pType === "image" ? 15 : 2;
  }

  function formatDuration(sec) {
    const total = Math.max(0, Math.floor(sec));
    const m = String(Math.floor(total / 60)).padStart(2, "0");
    const s = String(total % 60).padStart(2, "0");
    return `${m}:${s}`;
  }

  function updateDurationGoalUI(elapsedSec) {
    const target = getMinDurationTarget();
    const gaugeMax = Math.max(IDEAL_MAX_SECONDS, target * 2);
    const targetPct = Math.min(85, Math.round((target / gaugeMax) * 100));
    const fillPct = Math.min(100, (elapsedSec / gaugeMax) * 100);

    if (durationIdealZone) durationIdealZone.style.left = `${targetPct}%`;
    if (durationTargetMarker) durationTargetMarker.style.left = `${targetPct}%`;
    if (gaugeTargetLabel) gaugeTargetLabel.textContent = `${target}s cible`;

    if (durationGauge) {
      durationGauge.setAttribute("aria-valuemax", String(gaugeMax));
      durationGauge.setAttribute("aria-valuenow", String(Math.round(elapsedSec)));
    }

    if (durationGaugeFill) {
      durationGaugeFill.style.width = `${fillPct}%`;
      durationGaugeFill.classList.remove("is-blocked", "is-ideal", "is-long");
      if (elapsedSec > 0 && elapsedSec < HARD_MIN_SECONDS) {
        durationGaugeFill.classList.add("is-blocked");
      } else if (elapsedSec >= target && elapsedSec <= SOFT_LONG_SECONDS) {
        durationGaugeFill.classList.add("is-ideal");
      } else if (elapsedSec > SOFT_LONG_SECONDS) {
        durationGaugeFill.classList.add("is-long");
      }
    }

    if (!durationGoal) return;
    durationGoal.classList.remove("goal-met", "goal-long", "goal-too-short");

    if (elapsedSec <= 0) {
      durationGoal.textContent = `Zone idéale : ${target}s – ${gaugeMax}s (minimum absolu : ${HARD_MIN_SECONDS}s)`;
    } else if (elapsedSec < HARD_MIN_SECONDS) {
      durationGoal.textContent = `Trop court (${elapsedSec.toFixed(1)}s) — parlez au moins ${HARD_MIN_SECONDS}s`;
      durationGoal.classList.add("goal-too-short");
    } else if (elapsedSec < target) {
      const remaining = Math.ceil(target - elapsedSec);
      durationGoal.textContent = `Continuez encore ~${remaining}s pour atteindre la zone idéale (${target}s – ${gaugeMax}s)`;
    } else if (elapsedSec <= SOFT_LONG_SECONDS) {
      durationGoal.textContent = `Zone idéale atteinte (${formatDuration(elapsedSec)} · cible ${target}s – ${gaugeMax}s)`;
      durationGoal.classList.add("goal-met");
    } else {
      durationGoal.textContent = `C'est déjà très riche (${formatDuration(elapsedSec)}) — vous pouvez arrêter quand vous avez fini.`;
      durationGoal.classList.add("goal-long");
    }
  }

  function updateSessionMetaUI() {
    if (!sessionSelect) return;
    const opt = sessionSelect.options[sessionSelect.selectedIndex];
    const task = opt ? opt.getAttribute("data-task") || "asr" : "asr";
    if (taskBadge) {
      taskBadge.textContent = task === "tts" ? "Mode TTS · Studio" : "Mode ASR · Terrain";
      taskBadge.className = `badge ${task === "tts" ? "badge-tts" : "badge-asr"}`;
    }
  }

  function renderPromptCard() {
    if (!promptSelect) return;
    const opt = promptSelect.options[promptSelect.selectedIndex];
    const box = document.getElementById("promptBox");
    const imgWrap = document.getElementById("promptImageWrap");
    const imgEl = document.getElementById("promptImage");
    const badgeEl = document.getElementById("promptBadge");
    const topicEl = document.getElementById("promptTopic");
    const titleEl = document.getElementById("promptTitle");
    const contentEl = document.getElementById("promptContent");
    const descEl = document.getElementById("promptDesc");

    if (!box) return;

    if (promptSelect.value && opt) {
      const pType = opt.getAttribute("data-type") || "sentence";
      const pTopic = opt.getAttribute("data-topic") || "";
      const pTitle = opt.getAttribute("data-title") || "";
      const pContent = opt.getAttribute("data-content") || "";
      const pDesc = opt.getAttribute("data-desc") || "";
      const mediaUrl = opt.getAttribute("data-media-url") || "";

      if (badgeEl) badgeEl.textContent = pType === "image" ? "Description d'image" : pType;
      if (topicEl) {
        topicEl.textContent = pTopic ? `Thème : ${pTopic}` : "";
        topicEl.style.display = pTopic ? "inline-flex" : "none";
      }
      if (titleEl) titleEl.textContent = pTitle;
      if (contentEl) {
        contentEl.textContent = pType === "image" ? pContent : `« ${pContent} »`;
      }
      if (descEl) {
        descEl.textContent = pDesc ? `Note / Traduction : ${pDesc}` : "";
        descEl.style.display = pDesc ? "block" : "none";
      }
      const cuesEl = document.getElementById("imageCues");
      if (cuesEl) {
        cuesEl.style.display = pType === "image" ? "flex" : "none";
      }
      if (imgWrap && imgEl) {
        if (mediaUrl) {
          imgEl.src = mediaUrl;
          imgEl.alt = pTitle || "Image à décrire en soussou";
          imgWrap.style.display = "flex";
        } else {
          imgEl.removeAttribute("src");
          imgWrap.style.display = "none";
        }
      }
      box.style.display = "block";
    } else {
      box.style.display = "none";
    }

    updateDurationGoalUI(0);
  }

  async function loadNextRotatedPrompt(skipCurrent) {
    if (!sessionSelect || !sessionSelect.value) {
      if (statusMsg) {
        statusMsg.innerHTML = `<div class="alert alert-warning">Sélectionnez d'abord une session pour activer la rotation automatique des prompts.</div>`;
      }
      return;
    }

    if (skipCurrent && promptSelect && promptSelect.value) {
      skippedPromptIds.add(promptSelect.value);
    }

    const params = new URLSearchParams({ session_id: sessionSelect.value });
    if (skippedPromptIds.size > 0) {
      params.set("exclude_ids", Array.from(skippedPromptIds).join(","));
    }

    try {
      const resp = await fetch(`/api/prompts/next?${params.toString()}`);
      if (!resp.ok) throw new Error("Impossible de charger le prompt suivant");
      const data = await resp.json();

      if (sessionProgressLabel) {
        sessionProgressLabel.textContent = `${data.completed_in_session} prise(s) · ${data.remaining_for_speaker} stimulus restant(s)`;
      }

      if (!data.prompt) {
        if (statusMsg) {
          statusMsg.innerHTML = `<div class="alert alert-info">Tous les prompts actifs ont déjà été enregistrés pour ce locuteur. Vous pouvez passer en parole libre ou ajouter de nouveaux stimuli.</div>`;
        }
        return;
      }

      // Select matching option in dropdown (or add it if missing)
      const targetId = String(data.prompt.id);
      let found = false;
      for (let i = 0; i < promptSelect.options.length; i++) {
        if (promptSelect.options[i].value === targetId) {
          promptSelect.selectedIndex = i;
          found = true;
          break;
        }
      }
      if (!found) {
        const opt = document.createElement("option");
        opt.value = targetId;
        opt.textContent = `[${data.prompt.prompt_code}] ${data.prompt.title} (${data.prompt.prompt_type})`;
        opt.setAttribute("data-title", data.prompt.title || "");
        opt.setAttribute("data-content", data.prompt.content || "");
        opt.setAttribute("data-desc", data.prompt.description || "");
        opt.setAttribute("data-type", data.prompt.prompt_type || "sentence");
        opt.setAttribute("data-topic", data.prompt.topic || "");
        opt.setAttribute("data-min-duration", data.prompt.min_duration_seconds || "");
        if (data.prompt.media_object_key) {
          opt.setAttribute("data-media-url", `/api/prompts/${targetId}/media`);
        }
        promptSelect.appendChild(opt);
        promptSelect.value = targetId;
      }

      resetRecorderUI();
      renderPromptCard();
    } catch (err) {
      if (statusMsg) {
        statusMsg.innerHTML = `<div class="alert alert-warning">Rotation indisponible hors-ligne : sélectionnez un prompt manuellement dans la liste.</div>`;
      }
    }
  }

  function startVuMeter(stream) {
    stopVuMeter();
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx || !vuMeterFill) return;
      audioContext = new AudioCtx();
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);

      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      function tick() {
        analyser.getByteTimeDomainData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
          const normalized = (dataArray[i] - 128) / 128;
          sum += normalized * normalized;
        }
        const rms = Math.sqrt(sum / dataArray.length);
        const pct = Math.min(100, Math.round(rms * 280));
        vuMeterFill.style.width = `${pct}%`;
        vuRafId = requestAnimationFrame(tick);
      }
      tick();
    } catch (_) {
      // Non-fatal on restricted devices
    }
  }

  function stopVuMeter() {
    if (vuRafId) {
      cancelAnimationFrame(vuRafId);
      vuRafId = null;
    }
    if (audioContext) {
      try {
        audioContext.close();
      } catch (_) {}
      audioContext = null;
    }
    if (vuMeterFill) vuMeterFill.style.width = "0%";
  }

  function resetRecorderUI() {
    audioChunks = [];
    audioBlob = null;
    recordingDuration = 0;
    if (timerDisplay) {
      timerDisplay.textContent = "00:00";
      timerDisplay.classList.remove("active");
    }
    if (recorderBox) recorderBox.classList.remove("is-recording");
    if (audioPreviewWrap) audioPreviewWrap.style.display = "none";
    if (audioPreview) {
      try {
        audioPreview.pause();
        audioPreview.currentTime = 0;
      } catch (_) {}
      if (audioPreview.src && audioPreview.src.startsWith("blob:")) {
        try { URL.revokeObjectURL(audioPreview.src); } catch (_) {}
      }
      audioPreview.removeAttribute("src");
      audioPreview.load();
    }
    if (btnUpload) btnUpload.disabled = true;
    if (btnRetake) btnRetake.style.display = "none";
    if (statusMsg) statusMsg.innerHTML = "";
    updateDurationGoalUI(0);
  }

  async function startRecording() {
    if (!sessionSelect || !sessionSelect.value) {
      if (statusMsg) {
        statusMsg.innerHTML = `<div class="alert alert-warning">Veuillez sélectionner une session avant d'enregistrer.</div>`;
      }
      sessionSelect && sessionSelect.focus();
      return;
    }

    resetRecorderUI();

    try {
      activeStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: false,
          autoGainControl: true,
        },
      });

      const mimeType = pickSupportedMimeType();
      mediaRecorder = mimeType
        ? new MediaRecorder(activeStream, { mimeType })
        : new MediaRecorder(activeStream);

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunks.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        stopVuMeter();
        if (activeStream) {
          activeStream.getTracks().forEach((track) => track.stop());
          activeStream = null;
        }
        const finalMime = mediaRecorder.mimeType || mimeType || "audio/webm";
        audioBlob = new Blob(audioChunks, { type: finalMime });
        const audioUrl = URL.createObjectURL(audioBlob);

        if (audioPreview) audioPreview.src = audioUrl;
        if (audioPreviewWrap) audioPreviewWrap.style.display = "block";
        if (btnRetake) btnRetake.style.display = "inline-flex";

        if (!audioBlob || audioBlob.size < 1024) {
          if (btnUpload) btnUpload.disabled = true;
          if (statusMsg) {
            statusMsg.innerHTML = `<div class="alert alert-danger"><strong>Enregistrement vide détecté.</strong> Cliquez sur <em>Recommencer</em> (ou utilisez Chrome/Safari).</div>`;
          }
          return;
        }

        const minTarget = getMinDurationTarget();
        if (recordingDuration < HARD_MIN_SECONDS) {
          // Plancher dur anti-erreur (< 2s) : empêche les appuis accidentels
          if (btnUpload) btnUpload.disabled = true;
          if (statusMsg) {
            statusMsg.innerHTML = `
              <div class="alert alert-danger">
                <strong>Enregistrement trop court (${recordingDuration.toFixed(1)}s — minimum absolu : ${HARD_MIN_SECONDS}s).</strong>
                L'envoi est bloqué pour éviter les fausses manipulations. Cliquez sur <em>Recommencer</em> et parlez quelques secondes.
              </div>
            `;
          }
        } else if (recordingDuration < minTarget) {
          // Zone intermédiaire (2s -> 14.9s) : avertissement non bloquant
          if (btnUpload) btnUpload.disabled = false;
          if (statusMsg) {
            statusMsg.innerHTML = `
              <div class="alert alert-warning">
                <strong>Durée courte (${recordingDuration.toFixed(1)}s / ${minTarget}s recommandés).</strong>
                Vous pouvez cliquer sur <em>Recommencer</em> pour détailler davantage, ou envoyer la prise telle quelle.
              </div>
            `;
          }
        } else {
          if (btnUpload) btnUpload.disabled = false;
          if (statusMsg) {
            statusMsg.innerHTML = `<div class="alert alert-success">Zone idéale atteinte (${recordingDuration.toFixed(1)}s). Écoutez l'aperçu puis envoyez.</div>`;
          }
        }
      };

      // Avoid timeslice chunking (e.g. start(250)) which can emit corrupted fragmented MP4s on iOS WebKit
      mediaRecorder.start();
      startVuMeter(activeStream);

      startTime = Date.now();
      timerInterval = setInterval(() => {
        recordingDuration = (Date.now() - startTime) / 1000;
        if (timerDisplay) timerDisplay.textContent = formatDuration(recordingDuration);
        updateDurationGoalUI(recordingDuration);
      }, 200);

      if (btnRecord) btnRecord.disabled = true;
      if (btnStop) btnStop.disabled = false;
      if (btnUpload) btnUpload.disabled = true;
      if (timerDisplay) timerDisplay.classList.add("active");
      if (recorderBox) recorderBox.classList.add("is-recording");
      if (statusMsg) statusMsg.innerHTML = `<div class="alert alert-info">Enregistrement en cours… Parlez naturellement en soussou.</div>`;
    } catch (err) {
      if (statusMsg) {
        statusMsg.innerHTML = `<div class="alert alert-danger">Impossible d'accéder au microphone : ${err.message}</div>`;
      }
    }
  }

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      recordingDuration = (Date.now() - startTime) / 1000;
      if (timerDisplay) timerDisplay.textContent = formatDuration(recordingDuration);
      updateDurationGoalUI(recordingDuration);

      // Stop microphone tracks inside mediaRecorder.onstop so final chunks flush cleanly
      mediaRecorder.stop();
      clearInterval(timerInterval);
      if (timerDisplay) timerDisplay.classList.remove("active");
      if (recorderBox) recorderBox.classList.remove("is-recording");
      if (btnRecord) btnRecord.disabled = false;
      if (btnStop) btnStop.disabled = true;
    }
  }

  function formatFlags(flagsCsv) {
    if (!flagsCsv) return `<span class="badge badge-validated">Contrôle auto OK</span>`;
    const labels = {
      too_short: "Durée courte",
      low_snr: "Bruit ambiant élevé",
      clipping: "Saturation détectée",
      silence_only: "Silence / voix trop faible",
    };
    return flagsCsv
      .split(",")
      .filter(Boolean)
      .map((f) => `<span class="badge badge-warn">${labels[f] || f}</span>`)
      .join(" ");
  }

  async function sendAudioBlobToServer(blob, sessionId, promptId, durationSec) {
    const formData = new FormData();
    const mimeType = blob.type || "audio/webm";
    const ext = extensionFromMime(mimeType);
    formData.append("file", blob, `recording.${ext}`);
    formData.append("session_id", sessionId);
    if (promptId) formData.append("prompt_id", promptId);
    formData.append("duration_seconds", String(Number(durationSec || 0).toFixed(2)));

    const response = await fetch("/api/recordings", {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      let detail = "Erreur lors de l'envoi";
      try {
        const err = await response.json();
        detail = err.detail || detail;
      } catch (_) {}
      throw new Error(detail);
    }
    return response.json();
  }

  async function refreshOfflineBanner() {
    if (networkPill) {
      if (navigator.onLine) {
        networkPill.textContent = "En ligne";
        networkPill.classList.remove("is-offline");
      } else {
        networkPill.textContent = "Hors-ligne (sauvegarde locale)";
        networkPill.classList.add("is-offline");
      }
    }

    if (!window.AloraOfflineQueue || !offlineBar || !offlineCountText) return;
    try {
      const items = await window.AloraOfflineQueue.listPending();
      if (items.length > 0) {
        offlineCountText.textContent = `${items.length} audio(s) en attente de synchronisation locale`;
        offlineBar.classList.add("has-items");
      } else {
        offlineBar.classList.remove("has-items");
      }
    } catch (_) {}
  }

  async function syncPendingOfflineQueue() {
    if (!window.AloraOfflineQueue || !navigator.onLine) {
      await refreshOfflineBanner();
      return;
    }
    let items = [];
    try {
      items = await window.AloraOfflineQueue.listPending();
    } catch (_) {
      return;
    }
    if (!items.length) {
      await refreshOfflineBanner();
      return;
    }

    if (btnSyncOffline) btnSyncOffline.disabled = true;
    let synced = 0;

    for (const item of items) {
      try {
        await sendAudioBlobToServer(item.blob, item.sessionId, item.promptId, item.durationSeconds);
        await window.AloraOfflineQueue.removePending(item.id);
        synced++;
      } catch (_) {
        break; // Stop if network failed again
      }
    }

    if (btnSyncOffline) btnSyncOffline.disabled = false;
    await refreshOfflineBanner();

    if (synced > 0 && statusMsg) {
      statusMsg.innerHTML = `<div class="alert alert-success">${synced} enregistrement(s) hors-ligne synchronisé(s) avec succès.</div>`;
    }
  }

  async function uploadRecording() {
    if (!audioBlob) return;
    if (recordingDuration < HARD_MIN_SECONDS) {
      if (statusMsg) {
        statusMsg.innerHTML = `<div class="alert alert-danger">Enregistrement trop court (&lt; ${HARD_MIN_SECONDS}s). Cliquez sur Recommencer.</div>`;
      }
      return;
    }
    const sessionId = sessionSelect ? sessionSelect.value : "";
    const promptId = promptSelect ? promptSelect.value : "";
    if (!sessionId) return;

    if (btnUpload) btnUpload.disabled = true;
    if (statusMsg) statusMsg.innerHTML = `<div class="alert alert-info">Envoi et analyse acoustique FFmpeg en cours…</div>`;

    // Offline fallback directly to IndexedDB
    if (!navigator.onLine && window.AloraOfflineQueue) {
      try {
        await window.AloraOfflineQueue.addPending({
          blob: audioBlob,
          sessionId,
          promptId,
          durationSeconds: recordingDuration,
        });
        await refreshOfflineBanner();
        if (statusMsg) {
          statusMsg.innerHTML = `
            <div class="alert alert-warning">
              <strong>Réseau absent : audio sauvegardé localement sur cet appareil.</strong><br>
              Il sera envoyé automatiquement dès le retour de la connexion.
              <div style="margin-top: 0.75rem;">
                <button type="button" class="btn btn-primary btn-sm" id="btnAfterSaveNext">Prompt suivant →</button>
              </div>
            </div>
          `;
          const nextBtn = document.getElementById("btnAfterSaveNext");
          if (nextBtn) nextBtn.addEventListener("click", () => loadNextRotatedPrompt(true));
        }
        return;
      } catch (e) {
        if (btnUpload) btnUpload.disabled = false;
        if (statusMsg) statusMsg.innerHTML = `<div class="alert alert-danger">Échec sauvegarde locale : ${e.message}</div>`;
        return;
      }
    }

    try {
      const data = await sendAudioBlobToServer(audioBlob, sessionId, promptId, recordingDuration);
      const snrText = data.snr_db !== null && data.snr_db !== undefined ? `${data.snr_db} dB` : "—";
      const speechPct = data.speech_ratio !== null && data.speech_ratio !== undefined ? `${Math.round(data.speech_ratio * 100)} %` : "—";
      const durText = data.duration_seconds !== null && data.duration_seconds !== undefined ? `${Number(data.duration_seconds).toFixed(1)} s` : "—";

      if (statusMsg) {
        statusMsg.innerHTML = `
          <div class="alert ${data.auto_quality_flags ? "alert-warning" : "alert-success"}" style="text-align: left;">
            <strong>Enregistrement sauvegardé : ${data.recording_code}</strong>
            <div style="margin-top: 0.45rem;">${formatFlags(data.auto_quality_flags)}</div>
            <div class="qa-metrics-grid">
              <div class="qa-metric-box"><span>Durée réelle</span><strong>${durText}</strong></div>
              <div class="qa-metric-box"><span>SNR estimé</span><strong>${snrText}</strong></div>
              <div class="qa-metric-box"><span>Activité vocale</span><strong>${speechPct}</strong></div>
            </div>
            <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.75rem;">
              <button type="button" class="btn btn-primary btn-sm" id="btnAfterUploadNext">Prompt suivant (Rotation) →</button>
              <a href="/recordings/${data.id}" class="btn btn-secondary btn-sm">Voir la fiche</a>
            </div>
          </div>
        `;
        const nextBtn = document.getElementById("btnAfterUploadNext");
        if (nextBtn) nextBtn.addEventListener("click", () => loadNextRotatedPrompt(false));
      }

      // Sync any older queued offline items as well
      syncPendingOfflineQueue();
    } catch (err) {
      // Network error fallback to IndexedDB
      if (window.AloraOfflineQueue && err instanceof TypeError) {
        await window.AloraOfflineQueue.addPending({
          blob: audioBlob,
          sessionId,
          promptId,
          durationSeconds: recordingDuration,
        });
        await refreshOfflineBanner();
        if (statusMsg) {
          statusMsg.innerHTML = `<div class="alert alert-warning">Coupure réseau détectée : prise sauvegardée localement en file d'attente hors-ligne.</div>`;
        }
        return;
      }

      if (btnUpload) btnUpload.disabled = false;
      if (statusMsg) {
        statusMsg.innerHTML = `<div class="alert alert-danger">Échec de l'envoi : ${err.message}</div>`;
      }
    }
  }

  // Event wiring
  if (btnRecord) btnRecord.addEventListener("click", startRecording);
  if (btnStop) btnStop.addEventListener("click", stopRecording);
  if (btnRetake) btnRetake.addEventListener("click", resetRecorderUI);
  if (btnUpload) btnUpload.addEventListener("click", uploadRecording);
  if (btnNextPrompt) btnNextPrompt.addEventListener("click", () => loadNextRotatedPrompt(true));
  if (btnSyncOffline) btnSyncOffline.addEventListener("click", syncPendingOfflineQueue);

  if (sessionSelect) {
    sessionSelect.addEventListener("change", () => {
      skippedPromptIds.clear();
      updateSessionMetaUI();
      if (sessionSelect.value && (!promptSelect || !promptSelect.value)) {
        loadNextRotatedPrompt(false);
      }
    });
  }

  if (promptSelect) {
    promptSelect.addEventListener("change", () => {
      resetRecorderUI();
      renderPromptCard();
    });
  }

  window.addEventListener("online", () => {
    refreshOfflineBanner();
    syncPendingOfflineQueue();
  });
  window.addEventListener("offline", refreshOfflineBanner);

  document.addEventListener("DOMContentLoaded", () => {
    updateSessionMetaUI();
    renderPromptCard();
    refreshOfflineBanner();
    if (sessionSelect && sessionSelect.value && promptSelect && !promptSelect.value) {
      loadNextRotatedPrompt(false);
    }
  });
})();
