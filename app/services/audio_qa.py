import array
import io
import math
import wave
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AcousticQAMetrics:
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    peak_amplitude: Optional[float] = None
    clipping_detected: bool = False
    snr_db: Optional[float] = None
    speech_ratio: Optional[float] = None
    flags: List[str] = field(default_factory=list)

    @property
    def flags_csv(self) -> Optional[str]:
        return ",".join(self.flags) if self.flags else None


def _percentile(sorted_vals: List[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * pct
    low = int(math.floor(pos))
    high = int(math.ceil(pos))
    if low == high:
        return sorted_vals[low]
    weight = pos - low
    return sorted_vals[low] * (1.0 - weight) + sorted_vals[high] * weight


def analyze_wav_bytes(
    wav_bytes: bytes,
    target_task: str = "asr",
    prompt_type: Optional[str] = None,
    min_duration_seconds: Optional[float] = None,
    fallback_duration: Optional[float] = None,
) -> AcousticQAMetrics:
    """
    Computes lightweight acoustic quality metrics on 16-bit PCM WAV bytes using
    only the Python standard library (wave, array, math):
      - Exact duration
      - Peak amplitude & clipping detection
      - Frame-level energy (20 ms) -> speech activity ratio & estimated SNR (dB)
      - Contextual automatic QA flags (too_short, silence_only, clipping, low_snr)
    """
    metrics = AcousticQAMetrics(duration_seconds=fallback_duration)
    if not wav_bytes or len(wav_bytes) < 44:
        return metrics

    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            nframes = wf.getnframes()

            metrics.channels = channels
            metrics.sample_rate = framerate

            if nframes == 0 or framerate <= 0:
                return metrics

            duration = round(nframes / float(framerate), 3)
            metrics.duration_seconds = duration

            if sampwidth != 2:
                return metrics

            raw = wf.readframes(nframes)
            actual_frames = len(raw) // (channels * sampwidth)
            if actual_frames == 0:
                return metrics
            metrics.duration_seconds = round(actual_frames / float(framerate), 3)
    except Exception:
        return metrics

    samples = array.array("h")
    samples.frombytes(raw)
    if not samples:
        return metrics

    # Downmix to mono if needed by striding
    if metrics.channels and metrics.channels > 1:
        samples = samples[:: metrics.channels]

    total_samples = len(samples)
    max_abs = 0
    clipped_count = 0
    consecutive_clipped = 0
    max_consecutive_clipped = 0

    for s in samples:
        a = abs(s)
        if a > max_abs:
            max_abs = a
        if a >= 32700:
            clipped_count += 1
            consecutive_clipped += 1
            if consecutive_clipped > max_consecutive_clipped:
                max_consecutive_clipped = consecutive_clipped
        else:
            consecutive_clipped = 0

    peak_amp = round(min(1.0, max_abs / 32768.0), 4)
    clipping_ratio = clipped_count / float(total_samples)
    clipping_detected = (clipping_ratio >= 0.001) or (max_consecutive_clipped >= 10)

    metrics.peak_amplitude = peak_amp
    metrics.clipping_detected = clipping_detected

    # 20 ms frame RMS calculation
    frame_len = max(1, int((metrics.sample_rate or 16000) * 0.02))
    frame_rms_list: List[float] = []
    for start in range(0, total_samples, frame_len):
        end = min(start + frame_len, total_samples)
        chunk = samples[start:end]
        if not chunk:
            continue
        sum_sq = sum((v / 32768.0) ** 2 for v in chunk)
        frame_rms_list.append(math.sqrt(sum_sq / len(chunk)))

    speech_level = 0.0
    if frame_rms_list:
        sorted_rms = sorted(frame_rms_list)
        noise_floor = max(_percentile(sorted_rms, 0.15), 1e-5)
        speech_level = max(_percentile(sorted_rms, 0.85), 1e-5)
        raw_snr = 20.0 * math.log10(speech_level / noise_floor)
        snr_db = round(max(0.0, min(60.0, raw_snr)), 1)

        activity_threshold = max(0.015, noise_floor * 1.4)
        active_frames = sum(1 for r in frame_rms_list if r >= activity_threshold)
        speech_ratio = round(active_frames / float(len(frame_rms_list)), 3)

        metrics.snr_db = snr_db
        metrics.speech_ratio = speech_ratio

    # Contextual quality flags (non-blocking warnings for field collectors & reviewers)
    flags: List[str] = []

    is_silent = (peak_amp < 0.015) or (speech_level < 0.01) or (
        metrics.speech_ratio is not None and metrics.speech_ratio < 0.05 and (metrics.snr_db or 0.0) < 3.0
    )
    if is_silent:
        flags.append("silence_only")

    if clipping_detected:
        flags.append("clipping")

    effective_min_dur = min_duration_seconds
    if effective_min_dur is None:
        if prompt_type == "image":
            effective_min_dur = 15.0
        else:
            effective_min_dur = 1.5

    if metrics.duration_seconds is not None and metrics.duration_seconds < effective_min_dur:
        flags.append("too_short")

    snr_threshold = 20.0 if target_task == "tts" else 12.0
    if not is_silent and metrics.snr_db is not None and metrics.snr_db < snr_threshold:
        flags.append("low_snr")

    metrics.flags = flags
    return metrics
