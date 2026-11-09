#!/usr/bin/env python3
"""Build a corrected SRT — Whisper timestamps + Gemini audio transcription.

Pipeline:
  1. Audio is extracted from the video and (if larger than the per-request API
     limit) split into chunks. Every chunk is processed independently.
  2. OpenAI's hosted Whisper API transcribes each chunk to a raw SRT. We keep
     Whisper's TIMESTAMPS and discard its text — Whisper is the timing source.
  3. Gemini transcribes each chunk's audio directly → accurate transcript.
  4. Gemini re-aligns per chunk: new SRT with Whisper's timestamps but the segment
     text replaced by the corresponding portion of Gemini's accurate transcript.
  5. Per-chunk results are stitched: timestamps shifted by chunk offset and segment
     numbers renumbered into one continuous sequence.

Every intermediate artifact is persisted next to the video in
`<video_dir>/.extract-srt-cache/` with a per-artifact JSON sidecar recording
the inputs (sha256s + model + ffmpeg params) that, if changed, must invalidate
it. A killed run can be resumed by re-invoking — already-cached chunks are
reused; only missing or invalid artifacts trigger fresh API calls. A
filesystem-level advisory lock (`.extract-srt-cache/.lock`) prevents two
concurrent invocations on the same video from double-billing the APIs.

To force a full cold run, `rm -rf <video_dir>/.extract-srt-cache/`.

Outputs (next to the video):
  <base>-raw.srt   — Whisper's original SRT (per-chunk, stitched), preserved
  <base>.srt       — final corrected SRT

Requires: ffmpeg, OPENAI_API_KEY, and one Gemini login: a gcloud login (Vertex,
Flex by default) or GEMINI_API_KEY. See --gemini-auth.
"""

import argparse
import base64
import fcntl
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

OPENAI_WHISPER_MODEL = "whisper-1"
OPENAI_TRANSCRIBE_URL = "https://api.openai.com/v1/audio/transcriptions"
OPENAI_AUDIO_LIMIT_BYTES = 19 * 1024 * 1024  # API caps at 20 MB; leave headroom
GEMINI_MODEL = "gemini-3.1-pro-preview"
GEMINI_API_KEY_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
GEMINI_VERTEX_URL = (
    "https://aiplatform.googleapis.com/v1/projects/{project}/locations/global/"
    "publishers/google/models/{model}:generateContent"
)
GEMINI_TIMEOUT = 600
GEMINI_AUDIO_LIMIT_BYTES = 19 * 1024 * 1024  # under the 20 MB inline-request cap
# Cap chunk duration so each Gemini realignment call has a manageable number of
# SRT segments to emit — long chunks hit the model's effective output budget
# and get truncated. ~10 min ≈ 150-200 segments, well under any output cap.
MAX_CHUNK_SECONDS = 600

DEFAULT_LANGUAGE = "bg"
# The ISO 639-1 codes that OpenAI Whisper documents as supported.
LANGUAGE_NAMES = {
    "af": "Afrikaans", "ar": "Arabic", "az": "Azerbaijani", "be": "Belarusian",
    "bg": "Bulgarian", "bs": "Bosnian", "ca": "Catalan", "cs": "Czech", "cy": "Welsh",
    "da": "Danish", "de": "German", "el": "Greek", "en": "English", "es": "Spanish",
    "et": "Estonian", "fa": "Persian", "fi": "Finnish", "fr": "French", "gl": "Galician",
    "he": "Hebrew", "hi": "Hindi", "hr": "Croatian", "hu": "Hungarian", "hy": "Armenian",
    "id": "Indonesian", "is": "Icelandic", "it": "Italian", "ja": "Japanese",
    "kk": "Kazakh", "kn": "Kannada", "ko": "Korean", "lt": "Lithuanian", "lv": "Latvian",
    "mi": "Maori", "mk": "Macedonian", "mr": "Marathi", "ms": "Malay", "ne": "Nepali",
    "nl": "Dutch", "no": "Norwegian", "pl": "Polish", "pt": "Portuguese", "ro": "Romanian",
    "ru": "Russian", "sk": "Slovak", "sl": "Slovenian", "sr": "Serbian", "sv": "Swedish",
    "sw": "Swahili", "ta": "Tamil", "th": "Thai", "tl": "Tagalog", "tr": "Turkish",
    "uk": "Ukrainian", "ur": "Urdu", "vi": "Vietnamese", "zh": "Chinese",
}

GEMINI_TRANSCRIBE_PROMPT = """You will receive a {language}-language audio recording.

Produce an accurate {language} transcript. Rules:
- Apply correct {language} spelling, capitalization, and punctuation.
- Preserve the speaker's exact wording and tone — do not paraphrase, summarize, or omit content.
- If a word is unintelligible, leave it out rather than guess.
- Return ONLY the {language} transcript — no preamble, no commentary, no quotes{no_english}."""

REALIGN_PROMPT = """You will receive two inputs:

1. A "Raw SRT" — auto-generated subtitles produced by Whisper. The TIMESTAMPS are accurate. The TEXT is noisy: it may have spelling errors, recognition errors, or even missing words.
2. An "Accurate transcript" — the same speech, transcribed cleanly from the original audio by a separate model. This text is the source of truth for CONTENT.

Produce a new SRT file with:
- The SAME segment numbers (1, 2, 3, ...) as the Raw SRT.
- The SAME timestamps as the Raw SRT — do not change a single millisecond.
- Each segment's text replaced by the corresponding portion of the Accurate transcript, distributed proportionally to the original segment lengths so the meaning aligns with the timing windows.
- All content from the Accurate transcript must appear somewhere; do not drop or summarize.
- Use the same number of segments as the Raw SRT.
- Trust the Accurate transcript over the Raw SRT for what the speaker said. If the Raw SRT is missing a word that exists in the Accurate transcript, include it.

Output ONLY the new SRT, in valid SRT format. No code fences, no commentary, no preamble.

Raw SRT:
---
{raw_srt}
---

Accurate transcript:
---
{accurate_text}
---"""


class GeminiTruncatedError(Exception):
    """Gemini stopped at MAX_TOKENS, so the text it returned is incomplete."""


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def stop_on_failed_realign(failed_chunks: list[int], chunk_count: int) -> None:
    if not failed_chunks:
        return
    names = ", ".join(f"{i + 1}/{chunk_count}" for i in sorted(failed_chunks))
    die(f"Realign failed for chunk {names}. No final SRT was written. "
        "Finished chunks are cached; re-run the same command.")


def transcribe_prompt(language: str) -> str:
    no_english = "" if language == "en" else ", no English"
    return GEMINI_TRANSCRIBE_PROMPT.format(
        language=LANGUAGE_NAMES[language], no_english=no_english,
    )


def language_matches(sidecar: dict, language: str) -> bool:
    """Compare a cache sidecar's language; a sidecar without one has the default language."""
    return sidecar.get("language", DEFAULT_LANGUAGE) == language


# --- Cache helpers ------------------------------------------------------

FLOAT_TOL_SEC = 1e-3  # 1 ms tolerance for offset_sec/duration_sec equality


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _tmp_sibling(target: Path) -> Path:
    return target.with_name(f"{target.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")


def atomic_write_bytes(target: Path, data: bytes) -> None:
    tmp = _tmp_sibling(target)
    tmp.write_bytes(data)
    os.replace(tmp, target)


def atomic_write_text(target: Path, text: str) -> None:
    tmp = _tmp_sibling(target)
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, target)


def read_sidecar(path: Path) -> dict | None:
    side = path.with_name(path.name + ".json")
    if not side.is_file():
        return None
    try:
        return json.loads(side.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_sidecar(path: Path, data: dict) -> None:
    side = path.with_name(path.name + ".json")
    atomic_write_text(side, json.dumps(data, indent=2, sort_keys=True))


def floats_close(a: float, b: float) -> bool:
    return math.isclose(a, b, abs_tol=FLOAT_TOL_SEC)


# --- Gemini (Vertex with Flex by default, or an API key) -----------------

@dataclass(frozen=True)
class GeminiAuth:
    """How to reach Gemini: an API key when set, otherwise Vertex in this project."""

    api_key: str = field(default="", repr=False)
    project: str = ""


_VERTEX_TOKEN: tuple[str, float] | None = None
_TOKEN_TTL_S = 50 * 60
_TOKEN_RE = re.compile(r"^[A-Za-z0-9._~+/-]{20,}$")


def _gcloud_project() -> str:
    env = (os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCLOUD_PROJECT") or "").strip()
    if env:
        return env
    try:
        out = subprocess.check_output(
            ["gcloud", "config", "get-value", "project"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("No Google project. Set GOOGLE_CLOUD_PROJECT.") from exc
    if not out or out == "(unset)":
        raise RuntimeError("gcloud has no project configured")
    return out


def _parse_access_token(stdout: str) -> str:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if len(lines) != 1 or _TOKEN_RE.fullmatch(lines[0]) is None:
        raise RuntimeError(
            "gcloud auth print-access-token did not return a single token line"
        )
    return lines[0]


def _vertex_token(*, force: bool = False) -> str:
    global _VERTEX_TOKEN
    env = (os.environ.get("GEMINI_VERTEX_TOKEN") or "").strip()
    if env:
        return env
    now = time.monotonic()
    if (
        not force
        and _VERTEX_TOKEN is not None
        and now - _VERTEX_TOKEN[1] < _TOKEN_TTL_S
    ):
        return _VERTEX_TOKEN[0]
    try:
        proc = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RuntimeError("Vertex login is missing. Run: gcloud auth login") from exc
    if proc.returncode != 0:
        raise RuntimeError("Vertex login is missing. Run: gcloud auth login")
    token = _parse_access_token(proc.stdout)
    _VERTEX_TOKEN = (token, now)
    return token


def _vertex_auth() -> GeminiAuth:
    _vertex_token()
    return GeminiAuth(project=_gcloud_project())


def _env_api_key() -> str:
    return (os.environ.get("GEMINI_API_KEY") or "").strip()


def _api_key_auth() -> GeminiAuth:
    key = _env_api_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set in the environment")
    return GeminiAuth(api_key=key)


def resolve_gemini_auth(mode: str) -> GeminiAuth:
    """Pick the Gemini login. `auto` tries Vertex first, then GEMINI_API_KEY."""
    if mode == "api-key":
        return _api_key_auth()
    if mode == "vertex":
        return _vertex_auth()
    try:
        return _vertex_auth()
    except RuntimeError as vertex_error:
        if _env_api_key():
            return _api_key_auth()
        raise RuntimeError(
            f"No Gemini login ({vertex_error}). "
            "Run: gcloud auth login, or set GEMINI_API_KEY."
        ) from vertex_error


def _vertex_flex_headers() -> dict[str, str]:
    tier = (os.environ.get("GEMINI_SERVICE_TIER") or "flex").strip().lower()
    if tier == "standard":
        return {}
    return {
        "X-Vertex-AI-LLM-Request-Type": "shared",
        "X-Vertex-AI-LLM-Shared-Request-Type": "flex",
        "X-Server-Timeout": "600",
    }


def gemini_target(auth: GeminiAuth, model: str) -> tuple[str, dict[str, str]]:
    """Return the generateContent URL and the auth headers for this login."""
    if auth.api_key:
        return GEMINI_API_KEY_URL.format(model=model), {"x-goog-api-key": auth.api_key}
    url = GEMINI_VERTEX_URL.format(project=auth.project, model=model)
    return url, {"Authorization": "Bearer " + _vertex_token(), **_vertex_flex_headers()}


def gemini_safety_settings(auth: GeminiAuth) -> list[dict[str, str]]:
    categories = [
        "HARM_CATEGORY_HARASSMENT",
        "HARM_CATEGORY_HATE_SPEECH",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "HARM_CATEGORY_DANGEROUS_CONTENT",
    ]
    # The Developer API (API key) no longer lists this category.
    if not auth.api_key:
        categories.append("HARM_CATEGORY_CIVIC_INTEGRITY")
    return [{"category": c, "threshold": "BLOCK_NONE"} for c in categories]


GEMINI_RETRY_REASONS = {"RECITATION", "SAFETY", "OTHER", "BLOCKLIST", "PROHIBITED_CONTENT"}


def _gemini_request(parts: list, auth: GeminiAuth, model: str, disable_thinking: bool) -> dict:
    generation_config: dict = {"temperature": 0.2, "maxOutputTokens": 65536}
    # Pro variants reject thinkingBudget=0 with HTTP 400 — they only operate in
    # thinking mode. The budget-tuning trick only applies to flash variants,
    # where thinking tokens count against the output budget; disable for
    # mechanical tasks (realignment) so the budget goes to output.
    if disable_thinking and "flash" in model:
        generation_config["thinkingConfig"] = {"thinkingBudget": 0}
    # Mechanical transcription/realignment shouldn't trip safety filters, but
    # in practice the default Gemini thresholds occasionally PROHIBITED_CONTENT
    # an innocuous audio chunk or its text-only realign pass. The script
    # `die()`s on those, leaving the video partially transcribed. Setting
    # BLOCK_NONE on every category is appropriate here because the caller
    # already trusts the source material.
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": generation_config,
        "safetySettings": gemini_safety_settings(auth),
    }
    # Vertex rejects a contents entry with no role.
    body["contents"][0]["role"] = "user"
    url, auth_headers = gemini_target(auth, model)
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", **auth_headers},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=GEMINI_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def gemini_call(
    parts: list, auth: GeminiAuth, model: str,
    disable_thinking: bool = False, max_retries: int = 3,
) -> str:
    last_err: str = ""
    for attempt in range(1, max_retries + 1):
        try:
            data = _gemini_request(parts, auth, model, disable_thinking)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code == 401 and attempt < max_retries:
                global _VERTEX_TOKEN
                _VERTEX_TOKEN = None
                print(f"  retry {attempt}/{max_retries - 1}: HTTP 401, refreshing login")
                continue
            if e.code in (429, 500, 503) and attempt < max_retries:
                print(f"  retry {attempt}/{max_retries - 1}: HTTP {e.code}")
                time.sleep(min(60, 15 * attempt))
                continue
            die(f"Gemini HTTP {e.code}: {body[:600]}")
        except urllib.error.URLError as e:
            if attempt < max_retries:
                print(f"  retry {attempt}/{max_retries - 1}: network {e.reason}")
                time.sleep(min(60, 15 * attempt))
                continue
            die(f"Gemini network error: {e.reason}")

        candidates = data.get("candidates") or []
        if not candidates:
            last_err = f"no candidates in response:\n{json.dumps(data, indent=2)[:800]}"
            if attempt < max_retries:
                print(f"  retry {attempt}/{max_retries - 1}: {last_err.splitlines()[0]}")
                time.sleep(2 * attempt)
                continue
            die(last_err)

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason", "")
        parts_out = (candidate.get("content") or {}).get("parts") or []
        text = parts_out[0].get("text", "").strip() if parts_out else ""

        if finish_reason in GEMINI_RETRY_REASONS:
            last_err = f"finishReason={finish_reason}"
            if attempt < max_retries:
                print(f"  retry {attempt}/{max_retries - 1}: {last_err} (will retry)")
                time.sleep(2 * attempt)
                continue
            die(f"Gemini refused after {max_retries} attempts ({last_err}).")

        # Pro models spend the output budget on thinking and can stop mid-text.
        if finish_reason == "MAX_TOKENS":
            raise GeminiTruncatedError(f"MAX_TOKENS: output truncated at {len(text)} chars")

        if not text:
            last_err = (
                f"empty text (finishReason={finish_reason or 'unset'}):\n"
                f"{json.dumps(data, indent=2)[:800]}"
            )
            if attempt < max_retries:
                print(f"  retry {attempt}/{max_retries - 1}: empty response (will retry)")
                time.sleep(2 * attempt)
                continue
            die(last_err)

        if finish_reason and finish_reason not in ("STOP", "FINISH_REASON_UNSPECIFIED"):
            die(
                f"Gemini stopped with unexpected finishReason={finish_reason}. "
                f"Got {len(text)} chars."
            )
        return text

    die(f"Gemini call exhausted retries: {last_err}")


def gemini_transcribe_one(
    audio_chunk: Path, auth: GeminiAuth, model: str, language: str,
    duration_seconds: float | None = None,
) -> str:
    """Send a single audio chunk (<20 MB) to Gemini and return the transcript.

    Retries if Gemini returns implausibly long output — a known failure mode
    where the model gets into a loop and repeats text. Speech is at most
    ~30 chars/sec, so anything over 3x that is treated as hallucination.
    """
    audio_bytes = audio_chunk.read_bytes()
    if len(audio_bytes) > GEMINI_AUDIO_LIMIT_BYTES:
        die(
            f"Audio chunk {audio_chunk.name} is {len(audio_bytes) / 1024 / 1024:.1f} MB — "
            f"over Gemini's {GEMINI_AUDIO_LIMIT_BYTES // 1024 // 1024} MB inline cap."
        )
    parts = [
        {"inline_data": {
            "mime_type": "audio/mp3",
            "data": base64.b64encode(audio_bytes).decode("ascii"),
        }},
        {"text": transcribe_prompt(language)},
    ]
    # Generous upper bound: 100 chars/sec, min 30K chars (covers short chunks).
    max_chars = max(30_000, int((duration_seconds or 600) * 100))
    last_text = ""
    for attempt in range(1, 4):
        try:
            text = gemini_call(parts, auth, model)
        except GeminiTruncatedError as truncated:
            print(f"  attempt {attempt}/3 failed: {truncated}")
            time.sleep(2 * attempt)
            continue
        if len(text) <= max_chars:
            return text
        last_text = text
        print(f"  retry {attempt}/2: transcript {len(text)} chars exceeds "
              f"sanity cap {max_chars} (likely hallucination loop)")
        time.sleep(2 * attempt)
    if not last_text:
        die(f"Gemini truncated the transcript of {audio_chunk.name} on every attempt. "
            "Nothing was cached; re-run the same command.")
    print(f"  WARN: transcript still {len(last_text)} chars after retries; "
          "passing it through anyway.")
    return last_text


# --- Audio chunking -----------------------------------------------------

def ffprobe_duration_seconds(audio: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        die("ffprobe failed:\n" + (result.stderr or "")[-800:])
    try:
        return float(result.stdout.strip())
    except ValueError:
        die(f"Could not parse audio duration from ffprobe: {result.stdout!r}")


@dataclass(frozen=True)
class ChunkPlanEntry:
    idx: int
    offset_sec: float
    duration_sec: float


def compute_chunk_plan(
    audio: Path, limit_bytes: int, max_seconds: float | None,
) -> list[ChunkPlanEntry]:
    """Plan the chunk boundaries for an audio file. Pure — no ffmpeg, no writes.

    When the audio already fits both caps, returns a single entry covering the
    full duration so the caller's loop is uniform.
    """
    size = audio.stat().st_size
    duration = ffprobe_duration_seconds(audio)
    over_size = size > limit_bytes
    over_time = max_seconds is not None and duration > max_seconds
    if not (over_size or over_time):
        return [ChunkPlanEntry(idx=0, offset_sec=0.0, duration_sec=duration)]

    # 90% of the limit as the effective per-chunk byte budget to absorb mp3
    # frame-boundary slop and small encode variability.
    by_size = math.ceil(size / (limit_bytes * 0.90)) if over_size else 1
    by_time = math.ceil(duration / max_seconds) if max_seconds else 1
    chunk_count = max(2, by_size, by_time)
    chunk_seconds = duration / chunk_count
    return [
        ChunkPlanEntry(idx=i, offset_sec=i * chunk_seconds, duration_sec=chunk_seconds)
        for i in range(chunk_count)
    ]


def extract_one_chunk(
    audio: Path, offset_sec: float, duration_sec: float, dst: Path,
) -> None:
    """Run ffmpeg `-c copy` for one chunk window. Writes via tmp + os.replace."""
    tmp = _tmp_sibling(dst)
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{offset_sec:.3f}",
        "-i", str(audio),
        "-t", f"{duration_sec:.3f}",
        "-c", "copy",
        "-f", "mp3",
        str(tmp),
    ]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        # Drop any partial tmp ffmpeg may have left behind.
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        die(
            f"ffmpeg split (offset {offset_sec:.3f}s) failed:\n"
            + r.stderr.decode("utf-8", "replace")[-800:]
        )
    os.replace(tmp, dst)


# --- Whisper engines ----------------------------------------------------

def extract_audio(video: Path, dst: Path) -> None:
    """Extract mono 16 kHz 64 kbps mp3 — small and ideal for transcription.

    Some source MP4s carry non-monotonic DTS (a VFR/recording artifact). Without
    correction, libmp3lame silently drops frames "backward in time" and the
    extracted audio ends up much shorter than the source — which then truncates
    every downstream chunk. `aresample=async=1:first_pts=0` resamples to a
    monotonic clock (padding/dropping samples as needed) so the full audio
    track makes it through.
    """
    tmp = _tmp_sibling(dst)
    cmd = [
        "ffmpeg", "-y",
        "-fflags", "+genpts",
        "-i", str(video),
        "-vn",
        "-af", "aresample=async=1:first_pts=0",
        "-ac", "1", "-ar", "16000",
        "-c:a", "libmp3lame", "-b:a", "64k",
        "-f", "mp3",
        str(tmp),
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        die("ffmpeg failed:\n" + result.stderr.decode("utf-8", "replace")[-800:])
    os.replace(tmp, dst)


# Parameters that, if changed, must invalidate the cached audio.mp3.
FFMPEG_AUDIO_PARAMS = {
    "input_fflags": "+genpts",
    "ar": 16000,
    "ac": 1,
    "bitrate": "64k",
    "codec": "libmp3lame",
    "filter": "aresample=async=1:first_pts=0",
}


def openai_whisper_srt_one(
    audio: Path, api_key: str, language: str, max_retries: int = 4,
) -> str:
    """Send a single audio chunk (<20 MB) to OpenAI Whisper. Return raw SRT body.

    Retries on transient HTTP errors (429/5xx) and curl network/timeout errors
    with exponential backoff. Fails fast on non-retriable errors (4xx).
    """
    last_err = ""
    for attempt in range(1, max_retries + 1):
        result = subprocess.run(
            [
                "curl", "--silent", "--show-error",
                "--max-time", "300",
                "--write-out", "\n__HTTP_STATUS__%{http_code}",
                "-X", "POST", OPENAI_TRANSCRIBE_URL,
                # The key goes through stdin: argv is readable by other processes.
                "-H", "@-",
                "-F", f"file=@{audio}",
                "-F", f"model={OPENAI_WHISPER_MODEL}",
                "-F", f"language={language}",
                "-F", "response_format=srt",
            ],
            input=f"Authorization: Bearer {api_key}\n",
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            # Network/timeout/etc. - retry transient curl errors.
            last_err = (
                f"curl exit {result.returncode}: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
            if attempt < max_retries and result.returncode in (6, 7, 28, 35, 52, 56):
                wait = 2 ** attempt
                print(f"  retry {attempt}/{max_retries - 1} after {wait}s: {last_err}")
                time.sleep(wait)
                continue
            die(f"OpenAI Whisper API call failed ({last_err})")

        body, _, status_line = result.stdout.rpartition("\n__HTTP_STATUS__")
        status = status_line.strip()
        if status == "200":
            stripped = body.lstrip()
            if stripped.startswith("{") or stripped.startswith("["):
                die(f"OpenAI Whisper API returned JSON instead of SRT:\n{body[:600]}")
            return body
        last_err = f"HTTP {status}: {body.strip()[:400]}"
        if attempt < max_retries and (status == "429" or status.startswith("5")):
            wait = 2 ** attempt
            print(f"  retry {attempt}/{max_retries - 1} after {wait}s: {last_err}")
            time.sleep(wait)
            continue
        die(f"OpenAI Whisper API call failed ({last_err})")

    die(f"OpenAI Whisper API exhausted retries: {last_err}")


# --- SRT helpers --------------------------------------------------------

SRT_TIMESTAMP_RE = re.compile(r"\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,\.]\d{3}")
SRT_TS_PAIR_RE = re.compile(
    r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})"
)


def count_srt_segments(srt_text: str) -> int:
    return len(SRT_TIMESTAMP_RE.findall(srt_text))


def parse_srt_ts(ts: str) -> float:
    h, m, s = ts.replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def format_srt_ts(seconds: float) -> str:
    # Round the total first, so 59.9996 s carries into the minute.
    total_ms = round(max(seconds, 0.0) * 1000)
    total_s, ms = divmod(total_ms, 1000)
    total_m, s = divmod(total_s, 60)
    h, m = divmod(total_m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def shift_and_renumber_srt(
    srt_text: str, offset_seconds: float, start_index: int,
) -> tuple[str, int]:
    """Shift every timestamp by offset_seconds and renumber blocks starting at start_index.

    Returns (shifted_srt_text, next_index_after_last_block).
    """
    blocks = re.split(r"\n\s*\n", srt_text.strip())
    out_blocks: list[str] = []
    idx = start_index
    for block in blocks:
        lines = [ln for ln in block.strip().split("\n") if ln.strip()]
        if len(lines) < 3 or not lines[0].strip().isdigit():
            continue
        m = SRT_TS_PAIR_RE.search(lines[1])
        if not m:
            continue
        start = parse_srt_ts(m.group(1)) + offset_seconds
        end = parse_srt_ts(m.group(2)) + offset_seconds
        new_ts = f"{format_srt_ts(start)} --> {format_srt_ts(end)}"
        out_blocks.append("\n".join([str(idx), new_ts] + lines[2:]))
        idx += 1
    return ("\n\n".join(out_blocks), idx)


def strip_code_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:srt|SRT)?\s*\n", "", text)
    text = re.sub(r"\n```\s*$", "", text)
    return text.strip()


def validate_srt(srt_text: str) -> tuple[bool, str]:
    """Return (ok, reason). Quick structural check on the realigned output."""
    if not srt_text.strip():
        return False, "empty output"
    blocks = re.split(r"\n\s*\n", srt_text.strip())
    if not blocks:
        return False, "no blocks parsed"
    for i, block in enumerate(blocks, start=1):
        lines = [ln for ln in block.strip().split("\n") if ln.strip()]
        if len(lines) < 3:
            return False, f"block {i} has fewer than 3 lines"
        if not lines[0].strip().isdigit():
            return False, f"block {i} does not start with a segment number"
        if not SRT_TIMESTAMP_RE.search(lines[1]):
            return False, f"block {i} missing timestamp on line 2"
    return True, "ok"


def _srt_blocks(srt_text: str) -> list[tuple[str, str, list[str]]]:
    """Parse SRT into [(segment_number, timestamp_line, text_lines), ...]."""
    out: list[tuple[str, str, list[str]]] = []
    for block in re.split(r"\n\s*\n", srt_text.strip()):
        lines = [ln for ln in block.strip().split("\n") if ln.strip()]
        if len(lines) < 3 or not lines[0].strip().isdigit():
            continue
        if not SRT_TIMESTAMP_RE.search(lines[1]):
            continue
        out.append((lines[0].strip(), lines[1].strip(), lines[2:]))
    return out


def transplant_timestamps(raw_srt: str, realigned_srt: str) -> tuple[str | None, bool]:
    """Replace realigned timestamps with raw's, by segment index.

    Gemini sometimes fabricates timestamps despite the realign prompt's
    explicit instruction to preserve them — the structural validator can't
    detect this because the fabricated timestamps look well-formed. When
    segment counts match, the raw Whisper timestamps are the source of truth.

    Returns (patched_srt, changed) when segment counts match (changed=True
    if any timestamp was rewritten), or (None, False) when counts diverge
    and a 1:1 transplant would misalign text to time.
    """
    raw_blocks = _srt_blocks(raw_srt)
    realigned_blocks = _srt_blocks(realigned_srt)
    if len(raw_blocks) != len(realigned_blocks):
        return None, False
    changed = False
    out: list[str] = []
    for (_, raw_ts, _), (rea_num, rea_ts, rea_text) in zip(raw_blocks, realigned_blocks):
        if raw_ts != rea_ts:
            changed = True
        out.append("\n".join([rea_num, raw_ts, *rea_text]))
    return "\n\n".join(out), changed


# --- entrypoint ---------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("video", help="Path to the video file")
    ap.add_argument("--gemini-model", default=GEMINI_MODEL,
                    help=f"Gemini model for transcription + realignment (default: {GEMINI_MODEL})")
    ap.add_argument("--workers", type=int, default=1,
                    help="Parallel workers for the Gemini transcribe+realign phase "
                         "(default 1 = sequential, backward-compatible). Each chunk's "
                         "transcribe+realign is fully independent of others. Bumping "
                         "to 4-8 gives a large wall-clock win on long videos; cap based "
                         "on your Gemini RPM tier.")
    ap.add_argument("--language", default=DEFAULT_LANGUAGE, choices=sorted(LANGUAGE_NAMES),
                    help=f"Spoken language, ISO 639-1 (default: {DEFAULT_LANGUAGE})")
    ap.add_argument("--gemini-auth", default="auto", choices=("auto", "vertex", "api-key"),
                    help="Gemini login: vertex = gcloud login, api-key = GEMINI_API_KEY, "
                         "auto = Vertex when usable, otherwise the API key (default: auto)")
    args = ap.parse_args()

    video = Path(args.video).expanduser().resolve()
    if not video.is_file():
        die(f"Video not found: {video}")

    try:
        gemini_auth = resolve_gemini_auth(args.gemini_auth)
    except RuntimeError as exc:
        die(str(exc))
    print(f"Gemini login: {'API key' if gemini_auth.api_key else 'Vertex AI'}\n")

    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        die("OPENAI_API_KEY is not set in the environment")

    out_dir = video.parent
    # Strip a trailing "-compressed" so outputs land on the canonical base name.
    out_stem = re.sub(r"-compressed$", "", video.stem)
    raw_srt = out_dir / f"{out_stem}-raw.srt"
    final_srt = out_dir / f"{out_stem}.srt"

    cache_dir = video.parent / ".extract-srt-cache"
    cache_dir.mkdir(exist_ok=True)
    # Acquire an advisory lock for the lifetime of this process. The fd MUST
    # stay open until main() returns — using `with open(...)` would release the
    # lock the moment the context manager closes the file. OS releases the
    # lock automatically on process exit. Assigning to a local keeps it alive.
    lock_path = cache_dir / ".lock"
    lock_fp = open(lock_path, "a+")  # noqa: SIM115 — intentional: see comment above.
    try:
        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        die(
            f"Another extract-srt.py is already running on this video. "
            f"If you're sure no other process holds it, rm {lock_path} and retry."
        )
    # Keep lock_fp referenced so it stays open for the lifetime of main().
    _ = lock_fp

    audio = cache_dir / "audio.mp3"
    video_sha256 = sha256_of_file(video)
    audio_side = read_sidecar(audio)
    if (
        audio.is_file()
        and audio_side is not None
        and audio_side.get("video_sha256") == video_sha256
        and audio_side.get("ffmpeg_audio_params") == FFMPEG_AUDIO_PARAMS
    ):
        audio_sha256 = audio_side["audio_sha256"]
        size_mb = audio.stat().st_size / 1024 / 1024
        print(f"=== Extract audio (cached, {size_mb:.2f} MB) ===\n")
    else:
        print("=== Extract audio ===")
        extract_audio(video, audio)
        audio_sha256 = sha256_of_file(audio)
        write_sidecar(audio, {
            "video_sha256": video_sha256,
            "ffmpeg_audio_params": FFMPEG_AUDIO_PARAMS,
            "audio_sha256": audio_sha256,
        })
        size_mb = audio.stat().st_size / 1024 / 1024
        print(f"  audio.mp3: {size_mb:.2f} MB\n")

    chunk_limit = min(OPENAI_AUDIO_LIMIT_BYTES, GEMINI_AUDIO_LIMIT_BYTES)
    plan = compute_chunk_plan(audio, chunk_limit, MAX_CHUNK_SECONDS)
    chunk_count = len(plan)
    if chunk_count > 1:
        per_mb = chunk_limit // 1024 // 1024
        print(f"=== Audio split into {chunk_count} chunks (per-chunk cap {per_mb} MB) ===\n")

    # Surface stale per-chunk artifacts from a prior run with more chunks. The
    # script never auto-deletes them — the user wipes the cache dir manually.
    stale = []
    for pat in ("chunk-*.mp3", "whisper-*.srt",
                "gemini-transcribe-*.txt", "gemini-realign-*.srt"):
        for p in cache_dir.glob(pat):
            m = re.search(r"-(\d{3})\.", p.name)
            if m and int(m.group(1)) >= chunk_count:
                stale.append(p)
    if stale:
        print(
            f"  WARN: found {len(stale)} stale cache entries from a prior run "
            f"with more chunks; run `rm -rf {cache_dir}` to clean up if desired.\n"
        )

    chunks: list[tuple[Path, float]] = []
    chunk_sha256s: list[str] = []
    for entry in plan:
        chunk_path = cache_dir / f"chunk-{entry.idx:03d}.mp3"
        side = read_sidecar(chunk_path)
        cache_ok = (
            chunk_path.is_file()
            and side is not None
            and side.get("audio_sha256") == audio_sha256
            and floats_close(side.get("offset_sec", -1.0), entry.offset_sec)
            and floats_close(side.get("duration_sec", -1.0), entry.duration_sec)
            and side.get("max_chunk_seconds") == MAX_CHUNK_SECONDS
            and side.get("chunk_byte_limit") == chunk_limit
        )
        if cache_ok:
            chunk_sha = side["chunk_sha256"]
            print(
                f"=== Chunk {entry.idx+1}/{chunk_count} (cached, "
                f"{chunk_path.stat().st_size / 1024 / 1024:.2f} MB, "
                f"offset {entry.offset_sec:.1f}s) ==="
            )
        else:
            extract_one_chunk(audio, entry.offset_sec, entry.duration_sec, chunk_path)
            chunk_sha = sha256_of_file(chunk_path)
            write_sidecar(chunk_path, {
                "audio_sha256": audio_sha256,
                "offset_sec": entry.offset_sec,
                "duration_sec": entry.duration_sec,
                "max_chunk_seconds": MAX_CHUNK_SECONDS,
                "chunk_byte_limit": chunk_limit,
                "chunk_sha256": chunk_sha,
            })
        chunks.append((chunk_path, entry.offset_sec))
        chunk_sha256s.append(chunk_sha)

    # 1. Per-chunk raw Whisper SRT (timestamps relative to chunk start).
    per_chunk_raw: list[str] = []
    whisper_sha256s: list[str] = []
    for i, (chunk_path, offset) in enumerate(chunks):
        whisper_path = cache_dir / f"whisper-{i:03d}.srt"
        side = read_sidecar(whisper_path)
        srt = ""
        whisper_sha = ""
        if (
            whisper_path.is_file()
            and side is not None
            and side.get("chunk_sha256") == chunk_sha256s[i]
            and side.get("model") == OPENAI_WHISPER_MODEL
            and language_matches(side, args.language)
            and side.get("whisper_sha256")
        ):
            try:
                candidate = whisper_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                candidate = ""
            ok, _ = validate_srt(candidate)
            if ok and count_srt_segments(candidate) > 0:
                srt = candidate
                whisper_sha = side["whisper_sha256"]
        if srt:
            print(
                f"=== OpenAI Whisper chunk {i+1}/{len(chunks)} "
                f"(cached, {count_srt_segments(srt)} segments) ==="
            )
        else:
            print(
                f"=== OpenAI Whisper chunk {i+1}/{len(chunks)} "
                f"({chunk_path.stat().st_size / 1024 / 1024:.2f} MB, "
                f"offset {offset:.1f}s) ==="
            )
            srt = openai_whisper_srt_one(chunk_path, openai_key, args.language)
            atomic_write_text(whisper_path, srt)
            whisper_sha = sha256_of_file(whisper_path)
            write_sidecar(whisper_path, {
                "chunk_sha256": chunk_sha256s[i],
                "model": OPENAI_WHISPER_MODEL,
                "language": args.language,
                "whisper_sha256": whisper_sha,
            })
            print(f"  {count_srt_segments(srt)} segments")
        per_chunk_raw.append(srt)
        whisper_sha256s.append(whisper_sha)

    # 2. Per-chunk Gemini transcribe + realign. Split into two cache checkpoints
    # inside the same chunk-pinned worker so each step can hit/miss independently.
    failed_realigns: list[int] = []

    def _process_chunk(i: int) -> tuple[int, str]:
        chunk_path, _offset = chunks[i]
        tag = f"chunk {i+1}/{len(chunks)}"
        transcribe_path = cache_dir / f"gemini-transcribe-{i:03d}.txt"
        realign_path = cache_dir / f"gemini-realign-{i:03d}.srt"

        # (a) Transcribe step.
        t_side = read_sidecar(transcribe_path)
        accurate = ""
        transcribe_sha = ""
        if (
            transcribe_path.is_file()
            and t_side is not None
            and t_side.get("chunk_sha256") == chunk_sha256s[i]
            and t_side.get("model") == args.gemini_model
            and language_matches(t_side, args.language)
            and t_side.get("transcribe_sha256")
        ):
            try:
                candidate = transcribe_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                candidate = ""
            if candidate.strip():
                accurate = candidate
                transcribe_sha = t_side["transcribe_sha256"]
        if accurate:
            print(
                f"=== Gemini transcribe {tag} (cached, {len(accurate)} chars) ===",
                flush=True,
            )
        else:
            print(f"=== Gemini transcribe {tag} ({args.gemini_model}) ===", flush=True)
            chunk_duration = ffprobe_duration_seconds(chunk_path)
            accurate = gemini_transcribe_one(
                chunk_path, gemini_auth, args.gemini_model, args.language, chunk_duration,
            )
            atomic_write_text(transcribe_path, accurate)
            transcribe_sha = sha256_of_file(transcribe_path)
            write_sidecar(transcribe_path, {
                "chunk_sha256": chunk_sha256s[i],
                "model": args.gemini_model,
                "language": args.language,
                "transcribe_sha256": transcribe_sha,
            })
            print(f"  {tag}: {len(accurate)} chars", flush=True)

        # (b) Realign step.
        r_side = read_sidecar(realign_path)
        if (
            realign_path.is_file()
            and r_side is not None
            and r_side.get("whisper_sha256") == whisper_sha256s[i]
            and r_side.get("transcribe_sha256") == transcribe_sha
            and r_side.get("model") == args.gemini_model
        ):
            try:
                candidate = realign_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                candidate = ""
            ok, _ = validate_srt(candidate)
            if ok and count_srt_segments(candidate) > 0:
                print(
                    f"=== Gemini realign {tag} "
                    f"(cached, {count_srt_segments(candidate)} segments) ===",
                    flush=True,
                )
                return i, candidate

        print(f"=== Gemini realign {tag} ({args.gemini_model}) ===", flush=True)
        raw_n = count_srt_segments(per_chunk_raw[i])
        if raw_n == 0:
            # Fallback: do NOT write realign artifact — a subsequent resume retries.
            print(f"  {tag}: no segments in raw SRT, skipping realign", flush=True)
            return i, per_chunk_raw[i]

        realigned = ""
        new_n = 0
        last_failure = ""
        for attempt in range(1, 4):
            try:
                candidate = gemini_call(
                    [{"text": REALIGN_PROMPT.format(
                        raw_srt=per_chunk_raw[i], accurate_text=accurate,
                    )}],
                    gemini_auth, args.gemini_model, disable_thinking=True,
                )
            except GeminiTruncatedError as truncated:
                print(f"  {tag}: realign {truncated}", flush=True)
                candidate = ""
            candidate = strip_code_fence(candidate)
            ok, reason = validate_srt(candidate)
            cand_n = count_srt_segments(candidate)
            if not ok:
                last_failure = f"validation: {reason}"
            elif cand_n < int(raw_n * 0.7):
                last_failure = f"only {cand_n}/{raw_n} segments emitted"
            else:
                realigned, new_n = candidate, cand_n
                patched, ts_changed = transplant_timestamps(per_chunk_raw[i], candidate)
                if patched is not None and ts_changed:
                    print(f"  WARN: {tag} Gemini fabricated timestamps; "
                          "restored from raw Whisper SRT.", flush=True)
                    realigned = patched
                break
            if attempt < 3:
                print(f"  {tag} retry {attempt}/2: {last_failure}", flush=True)
                time.sleep(2 * attempt)

        if not realigned:
            # Do NOT write the realign artifact: caching a failure would prevent
            # retry. The other chunks finish, so a re-run redoes only this one.
            print(f"  WARN: {tag} realign failed after 3 attempts ({last_failure}).", flush=True)
            failed_realigns.append(i)
            return i, ""

        atomic_write_text(realign_path, realigned)
        write_sidecar(realign_path, {
            "whisper_sha256": whisper_sha256s[i],
            "transcribe_sha256": transcribe_sha,
            "model": args.gemini_model,
        })
        if new_n != raw_n:
            print(f"  WARN: {tag} segment count changed ({raw_n} → {new_n}) — "
                  "Gemini merged/split segments.", flush=True)
        print(f"  {tag}: {new_n} segments", flush=True)
        return i, realigned

    per_chunk_final: list[str] = [""] * len(chunks)
    workers = max(1, args.workers)
    if workers == 1 or len(chunks) == 1:
        for i in range(len(chunks)):
            idx, body = _process_chunk(i)
            per_chunk_final[idx] = body
    else:
        print(f"=== Gemini phase: {workers} parallel workers across "
              f"{len(chunks)} chunks ===", flush=True)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_process_chunk, i) for i in range(len(chunks))]
            for fut in as_completed(futures):
                idx, body = fut.result()
                per_chunk_final[idx] = body

    stop_on_failed_realign(failed_realigns, len(chunks))

    # 3. Shift timestamps by chunk offset, renumber, and write outputs.
    raw_idx = 1
    final_idx = 1
    raw_parts: list[str] = []
    final_parts: list[str] = []
    for (raw_body, final_body), (_, offset) in zip(
        zip(per_chunk_raw, per_chunk_final), chunks,
    ):
        shifted_raw, raw_idx = shift_and_renumber_srt(raw_body, offset, raw_idx)
        shifted_final, final_idx = shift_and_renumber_srt(final_body, offset, final_idx)
        if shifted_raw:
            raw_parts.append(shifted_raw)
        if shifted_final:
            final_parts.append(shifted_final)

    raw_text = "\n\n".join(p.rstrip("\n") for p in raw_parts) + "\n" if raw_parts else ""
    final_text = "\n\n".join(p.rstrip("\n") for p in final_parts) + "\n" if final_parts else ""
    # Atomic: the pool treats an existing <base>.srt as finished work.
    atomic_write_text(raw_srt, raw_text)
    atomic_write_text(final_srt, final_text)

    print(f"\nRaw SRT:   {raw_srt}  ({count_srt_segments(raw_text)} segments)")
    print(f"Final SRT: {final_srt}  ({count_srt_segments(final_text)} segments)")


if __name__ == "__main__":
    main()
