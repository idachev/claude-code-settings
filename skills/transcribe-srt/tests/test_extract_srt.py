"""Offline tests for extract-srt.py: no network, no gcloud, no API keys.

Run: python3 -m unittest discover -s tests -v
"""

import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "extract-srt.py"
_spec = importlib.util.spec_from_file_location("extract_srt", SCRIPT)
srt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(srt)

EXPECTED_BULGARIAN_PROMPT = """You will receive a Bulgarian-language audio recording.

Produce an accurate Bulgarian transcript. Rules:
- Apply correct Bulgarian spelling, capitalization, and punctuation.
- Preserve the speaker's exact wording and tone — do not paraphrase, summarize, or omit content.
- If a word is unintelligible, leave it out rather than guess.
- Return ONLY the Bulgarian transcript — no preamble, no commentary, no quotes, no English."""


def env(**values):
    cleared = {k: v for k, v in os.environ.items() if not k.startswith(("GEMINI_", "GOOGLE_", "GCLOUD_"))}
    return mock.patch.dict(os.environ, {**cleared, **values}, clear=True)


def vertex_available():
    return mock.patch.multiple(
        srt,
        _vertex_token=mock.Mock(return_value="vertex-token"),
        _gcloud_project=mock.Mock(return_value="some-project"),
    )


def vertex_missing():
    return mock.patch.object(
        srt, "_vertex_token", mock.Mock(side_effect=RuntimeError("Vertex login is missing")),
    )


class TranscribePromptTest(unittest.TestCase):
    def test_bulgarian_prompt_has_the_exact_expected_text(self):
        self.assertEqual(srt.transcribe_prompt("bg"), EXPECTED_BULGARIAN_PROMPT)

    def test_other_language_names_the_language_everywhere(self):
        prompt = srt.transcribe_prompt("de")
        self.assertIn("German-language audio", prompt)
        self.assertNotIn("Bulgarian", prompt)

    def test_english_prompt_does_not_forbid_english(self):
        self.assertNotIn("no English", srt.transcribe_prompt("en"))


class LanguageChoicesTest(unittest.TestCase):
    def test_codes_outside_europe_are_accepted(self):
        self.assertIn("Arabic-language audio", srt.transcribe_prompt("ar"))
        self.assertIn("Hindi-language audio", srt.transcribe_prompt("hi"))


class FormatTimestampTest(unittest.TestCase):
    def test_keeps_milliseconds(self):
        self.assertEqual(srt.format_srt_ts(1.5), "00:00:01,500")

    def test_rounding_up_carries_into_the_minute(self):
        self.assertEqual(srt.format_srt_ts(59.9996), "00:01:00,000")

    def test_rounding_up_carries_into_the_hour(self):
        self.assertEqual(srt.format_srt_ts(3599.9996), "01:00:00,000")

    def test_negative_is_clamped_to_zero(self):
        self.assertEqual(srt.format_srt_ts(-1.0), "00:00:00,000")


class LanguageCacheTest(unittest.TestCase):
    def test_sidecar_without_language_counts_as_the_default_language(self):
        self.assertTrue(srt.language_matches({}, "bg"))
        self.assertFalse(srt.language_matches({}, "de"))

    def test_sidecar_with_language_must_match(self):
        self.assertTrue(srt.language_matches({"language": "de"}, "de"))
        self.assertFalse(srt.language_matches({"language": "de"}, "bg"))


class ResolveGeminiAuthTest(unittest.TestCase):
    def test_auto_prefers_vertex_even_when_an_api_key_is_set(self):
        with env(GEMINI_API_KEY="key-1"), vertex_available():
            auth = srt.resolve_gemini_auth("auto")
        self.assertEqual(auth, srt.GeminiAuth(project="some-project"))

    def test_auto_falls_back_to_api_key_without_vertex(self):
        with env(GEMINI_API_KEY="key-1"), vertex_missing():
            auth = srt.resolve_gemini_auth("auto")
        self.assertEqual(auth, srt.GeminiAuth(api_key="key-1"))

    def test_auto_without_credentials_names_both_ways(self):
        with env(), vertex_missing():
            with self.assertRaises(RuntimeError) as caught:
                srt.resolve_gemini_auth("auto")
        self.assertIn("GEMINI_API_KEY", str(caught.exception))
        self.assertIn("gcloud auth login", str(caught.exception))

    def test_api_key_mode_ignores_vertex_and_requires_the_key(self):
        with env(), vertex_available():
            with self.assertRaises(RuntimeError) as caught:
                srt.resolve_gemini_auth("api-key")
        self.assertIn("GEMINI_API_KEY", str(caught.exception))

    def test_vertex_mode_does_not_fall_back_to_the_key(self):
        with env(GEMINI_API_KEY="key-1"), vertex_missing():
            with self.assertRaises(RuntimeError):
                srt.resolve_gemini_auth("vertex")


class GeminiTargetTest(unittest.TestCase):
    def test_api_key_goes_in_a_header_and_never_in_the_url(self):
        url, headers = srt.gemini_target(srt.GeminiAuth(api_key="key-1"), "gemini-x")
        self.assertEqual(
            url,
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-x:generateContent",
        )
        self.assertEqual(headers["x-goog-api-key"], "key-1")
        self.assertNotIn("key-1", url)
        self.assertNotIn("Authorization", headers)

    def test_api_key_requests_carry_no_vertex_headers(self):
        with env(GEMINI_SERVICE_TIER="flex"):
            _, headers = srt.gemini_target(srt.GeminiAuth(api_key="key-1"), "gemini-x")
        self.assertFalse([h for h in headers if h.startswith("X-Vertex")])

    def test_vertex_defaults_to_flex_on_the_global_endpoint(self):
        with env(), vertex_available():
            url, headers = srt.gemini_target(srt.GeminiAuth(project="p1"), "gemini-x")
        self.assertEqual(
            url,
            "https://aiplatform.googleapis.com/v1/projects/p1/locations/global/"
            "publishers/google/models/gemini-x:generateContent",
        )
        self.assertEqual(headers["Authorization"], "Bearer vertex-token")
        self.assertEqual(headers["X-Vertex-AI-LLM-Shared-Request-Type"], "flex")

    def test_vertex_standard_tier_sends_no_flex_headers(self):
        with env(GEMINI_SERVICE_TIER="standard"), vertex_available():
            _, headers = srt.gemini_target(srt.GeminiAuth(project="p1"), "gemini-x")
        self.assertFalse([h for h in headers if h.startswith("X-Vertex")])


class SafetySettingsTest(unittest.TestCase):
    CIVIC = "HARM_CATEGORY_CIVIC_INTEGRITY"

    @staticmethod
    def categories(auth):
        return [s["category"] for s in srt.gemini_safety_settings(auth)]

    def test_vertex_keeps_the_civic_integrity_category(self):
        self.assertIn(self.CIVIC, self.categories(srt.GeminiAuth(project="p1")))

    def test_developer_api_omits_the_category_it_does_not_list(self):
        self.assertNotIn(self.CIVIC, self.categories(srt.GeminiAuth(api_key="key-1")))

    def test_every_category_is_unblocked(self):
        settings = srt.gemini_safety_settings(srt.GeminiAuth(api_key="key-1"))
        self.assertEqual({s["threshold"] for s in settings}, {"BLOCK_NONE"})


def gemini_response(text, finish_reason="STOP"):
    return {"candidates": [{"finishReason": finish_reason, "content": {"parts": [{"text": text}]}}]}


class TruncatedOutputTest(unittest.TestCase):
    AUTH = srt.GeminiAuth(project="p1")

    def setUp(self):
        sleep = mock.patch.object(srt.time, "sleep")
        sleep.start()
        self.addCleanup(sleep.stop)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as chunk:
            chunk.write(b"audio")
        self.chunk = Path(chunk.name)
        self.addCleanup(self.chunk.unlink)

    def transcribe(self, *responses):
        with mock.patch.object(srt, "_gemini_request", side_effect=list(responses)) as request:
            result = srt.gemini_transcribe_one(self.chunk, self.AUTH, "gemini-x", "bg", 600.0)
        return result, request.call_count

    def test_gemini_call_reports_truncation_instead_of_returning_text(self):
        truncated = gemini_response("half", "MAX_TOKENS")
        with mock.patch.object(srt, "_gemini_request", return_value=truncated):
            with self.assertRaises(srt.GeminiTruncatedError):
                srt.gemini_call([{"text": "x"}], self.AUTH, "gemini-x")

    def test_truncated_with_no_text_is_also_reported_as_truncation(self):
        empty = gemini_response("", "MAX_TOKENS")
        with mock.patch.object(srt, "_gemini_request", return_value=empty):
            with self.assertRaises(srt.GeminiTruncatedError):
                srt.gemini_call([{"text": "x"}], self.AUTH, "gemini-x")

    def test_transcribe_retries_a_truncated_response(self):
        result, calls = self.transcribe(
            gemini_response("half", "MAX_TOKENS"), gemini_response("the whole text"),
        )
        self.assertEqual((result, calls), ("the whole text", 2))

    def test_transcribe_stops_rather_than_keep_truncated_text(self):
        truncated = gemini_response("half", "MAX_TOKENS")
        with self.assertRaises(SystemExit):
            self.transcribe(truncated, truncated, truncated)


class FailedRealignTest(unittest.TestCase):
    def test_no_failed_chunk_goes_on(self):
        srt.stop_on_failed_realign([], 4)

    def test_a_failed_chunk_stops_and_names_it(self):
        with mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
            with self.assertRaises(SystemExit):
                srt.stop_on_failed_realign([2, 0], 4)
        self.assertIn("1/4, 3/4", stderr.getvalue())


class WhisperKeyTest(unittest.TestCase):
    def test_the_key_goes_through_stdin_and_not_argv(self):
        done = mock.Mock(returncode=0, stdout="1\n\n__HTTP_STATUS__200", stderr="")
        with mock.patch.object(srt.subprocess, "run", return_value=done) as run:
            srt.openai_whisper_srt_one(Path("a.mp3"), "secret-key", "bg")
        self.assertNotIn("secret-key", " ".join(run.call_args.args[0]))
        self.assertEqual(run.call_args.kwargs["input"], "Authorization: Bearer secret-key\n")


RAW_WITH_SILENCE = """1
00:00:00,000 --> 00:00:02,000
Съжалявам, че съжалявам.

2
00:00:31,000 --> 00:00:33,000
Здравей, здравей, Марина.

3
00:02:08,000 --> 00:02:10,000
Благодаря ви, че гледахте това."""

REALIGNED_WITH_EMPTY = """1
00:00:00,000 --> 00:00:02,000

2
00:00:31,000 --> 00:00:33,000
Здравей, здрасти, Марина.

3
00:02:08,000 --> 00:02:10,000"""


class EmptyBlockTest(unittest.TestCase):
    def test_empty_blocks_are_dropped_and_reported_by_position(self):
        text, dropped = srt.drop_empty_srt_blocks(REALIGNED_WITH_EMPTY)
        self.assertEqual(dropped, [0, 2])
        self.assertEqual(srt.validate_srt(text), (True, "ok"))
        self.assertEqual(srt.count_srt_segments(text), 1)
        self.assertIn("Здравей, здрасти, Марина.", text)

    def test_raw_blocks_at_the_same_positions_are_removed_for_the_transplant(self):
        _, dropped = srt.drop_empty_srt_blocks(REALIGNED_WITH_EMPTY)
        raw = srt.remove_srt_blocks_at(RAW_WITH_SILENCE, dropped)
        self.assertEqual(srt.count_srt_segments(raw), 1)
        self.assertIn("Здравей, здравей, Марина.", raw)

    def test_text_without_empty_blocks_is_unchanged(self):
        text, dropped = srt.drop_empty_srt_blocks(RAW_WITH_SILENCE)
        self.assertEqual(dropped, [])
        self.assertEqual(text, RAW_WITH_SILENCE)


class SilentChunkTest(unittest.TestCase):
    def _volume(self, stderr):
        done = mock.Mock(returncode=0, stdout="", stderr=stderr)
        with mock.patch.object(srt.subprocess, "run", return_value=done):
            return srt.chunk_mean_volume_db(Path("chunk.mp3"))

    def test_mean_volume_is_parsed_from_ffmpeg(self):
        self.assertEqual(self._volume("[Parsed_volumedetect_0] mean_volume: -77.5 dB\n"), -77.5)

    def test_minus_infinity_counts_as_silent(self):
        self.assertLess(self._volume("mean_volume: -inf dB\n"), srt.SILENT_CHUNK_MEAN_DB)

    def test_missing_volume_line_gives_none(self):
        self.assertIsNone(self._volume("no audio stream\n"))


if __name__ == "__main__":
    unittest.main()
