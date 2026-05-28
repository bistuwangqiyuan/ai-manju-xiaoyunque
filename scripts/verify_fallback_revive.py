"""Unit-level verification of the Manju→HappyHorse fallback + revive logic.

Stubs out external calls (Manju + HappyHorse) so we can exercise:
  1. step() catches Manju 50500 → switches to HappyHorse.
  2. failed state with [50500] in error → step() auto-revives to HappyHorse.
  3. failed state with non-retryable error → stays failed.
  4. circuit breaker trips and reroutes new jobs to HappyHorse.

Run locally; no external network.
"""
from __future__ import annotations

import os
import sys
import types
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "deploy", "cloudfn-slim"))
sys.path.insert(0, ROOT)
os.environ.setdefault("HAPPYHORSE_API_KEY", "sk-stub")
os.environ.setdefault("COS_BUCKET", "stub-bucket")
os.environ.setdefault("COS_REGION", "ap-shanghai")
os.environ.setdefault("VOLC_ACCESS_KEY", "x")
os.environ.setdefault("VOLC_SECRET_KEY", "y")

import real_jobs as rj  # noqa: E402
import manju_client  # noqa: E402
import happyhorse_client as hh  # noqa: E402


class StubCOS:
    def __init__(self):
        self.store: dict[str, dict] = {}

    def get_json(self, key):
        return self.store.get(key)

    def put_json(self, key, data, **kw):  # noqa: ARG002
        self.store[key] = data
        return "stub://" + key

    def put_text_public(self, key, text, **kw):  # noqa: ARG002
        self.store[key] = {"text": text}
        return "https://example.com/" + key

    def presigned_get_url(self, key, **kw):  # noqa: ARG002
        return "https://example.com/" + key

    def list_keys_under(self, prefix, **kw):  # noqa: ARG002
        return [k for k in self.store if k.startswith(prefix)]

    @staticmethod
    def is_configured():
        return True


class HHSubmitTracker:
    def __init__(self, fail_with=None):
        self.calls = []
        self.fail_with = fail_with

    def submit(self, first_frame, prompt, **kw):
        self.calls.append({"first_frame": first_frame, "prompt": prompt, "kw": kw})
        if self.fail_with:
            raise hh.HappyHorseError(*self.fail_with)
        return f"hh-task-{len(self.calls)}"


class TestFallback(unittest.TestCase):
    def setUp(self):
        self.stub_cos = StubCOS()
        rj.cos_kv = self.stub_cos
        self.hh_tracker = HHSubmitTracker()
        hh.submit_i2v = self.hh_tracker.submit
        hh.is_configured = lambda: True

    def _base_failed_state(self, error_text):
        return {
            "schema": 1,
            "job_id": 9999,
            "user_id": 1,
            "user_email": "test@example.com",
            "title": "测试任务",
            "novel_excerpt": "兰若寺夜雨初停，宁采臣独宿西厢。",
            "style": "ancient_3d_guoman",
            "visual_style": "古风3D",
            "video_ratio": "9:16",
            "genre": "ancient",
            "language": "Chinese",
            "episodes_requested": 1,
            "max_episodes_to_render": 1,
            "mode": "excerpt",
            "stage": rj.STAGE_FAILED,
            "status": "failed",
            "progress": 27,
            "error": error_text,
            "current_ep_idx": 0,
            "ep_state": [],
            "created_at_ts": 100,
            "updated_at_ts": 100,
            "logs": [],
        }

    def test_revive_on_50500(self):
        st = self._base_failed_state("[50500] Internal Error request_id=xxx")
        rj.step(st)
        self.assertEqual(st["status"], "running", "should be revived to running")
        self.assertEqual(st["stage"], rj.STAGE_VIDEO_GEN)
        self.assertEqual(len(self.hh_tracker.calls), 1, "HappyHorse should be submitted")
        self.assertEqual(st["ep_state"][0]["provider"], rj.PROVIDER_HAPPYHORSE)
        self.assertEqual(st["revive_count"], 1)

    def test_revive_on_50430(self):
        st = self._base_failed_state("[50430] Request Has Reached API Concurrent Limit")
        rj.step(st)
        self.assertEqual(st["status"], "running")
        self.assertEqual(len(self.hh_tracker.calls), 1)

    def test_no_revive_on_permanent_error(self):
        st = self._base_failed_state("[10000] permanent invalid argument")
        rj.step(st)
        self.assertEqual(st["status"], "failed", "permanent errors should stay failed")
        self.assertEqual(len(self.hh_tracker.calls), 0)

    def test_no_double_revive(self):
        st = self._base_failed_state("[50500] Internal Error")
        st["revive_count"] = 1
        st["status"] = "failed"
        rj.step(st)
        self.assertEqual(st["status"], "failed", "should not revive twice")
        self.assertEqual(len(self.hh_tracker.calls), 0)

    def test_inline_switch_when_50500_during_step(self):
        # 状态：进入 script_analysis 阶段，已用完 _MAX_AUTO_RETRY
        st = self._base_failed_state("")
        st["status"] = "running"
        st["stage"] = rj.STAGE_SCRIPT
        st["script_task_id"] = "manju-task-script"
        st["auto_retry_count"] = rj._MAX_AUTO_RETRY  # 重试用尽
        # Stub manju query → raise 50500
        def boom(*args, **kw):  # noqa: ARG001
            raise manju_client.ManjuError(50500, "Internal Error")
        manju_client.query = boom
        rj.step(st)
        # 应当切换到 HappyHorse，不应该 mark failed
        self.assertEqual(st["status"], "running")
        self.assertEqual(st["stage"], rj.STAGE_VIDEO_GEN)
        self.assertEqual(len(self.hh_tracker.calls), 1)
        self.assertEqual(st["ep_state"][0]["provider"], rj.PROVIDER_HAPPYHORSE)

    def test_circuit_breaker_trip_on_50500(self):
        rj._circuit_breaker_trip(50500, "Internal Error")
        tripped, cb = rj._circuit_breaker_tripped()
        self.assertTrue(tripped)
        self.assertEqual(cb["consecutive_failures"], 1)
        rj._circuit_breaker_trip(50500, "Internal Error")
        rj._circuit_breaker_trip(50500, "Internal Error")
        _, cb2 = rj._circuit_breaker_tripped()
        self.assertEqual(cb2["consecutive_failures"], 3)
        # 第 3 次冷却时间应当 ≥ 3 × 默认（即 15 分钟）
        self.assertGreaterEqual(cb2["tripped_until_ts"] - cb2["last_tripped_at_ts"],
                                 rj._CB_COOLDOWN_S * 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
