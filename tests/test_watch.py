import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from watch import render


def w(**k):
    base = {"schema": "agent-pr-ledger/watch-v1", "definition_version": "1.0", "repo": "o/r",
            "number": 7, "agent": None, "detected_by": "none", "identity_type": None,
            "merged_at": None, "outcome": None}
    base.update(k); return base


class WatchRender(unittest.TestCase):
    def test_human_pr_is_out_of_scope(self):
        out = render(w())
        self.assertIn("out of scope", out); self.assertNotIn("review record", out)

    def test_trace_is_excluded(self):
        self.assertIn("excluded", render(w(detected_by="trace")))

    def test_unrecorded_merge(self):
        out = render(w(agent="Copilot", detected_by="author", identity_type="bot",
                       merged_at="2026-01-01T00:00:00Z", outcome="unrecorded"))
        self.assertIn("WITHOUT a review record", out); self.assertIn("certain", out)

    def test_recorded_merge_ja(self):
        out = render(w(agent="OpenAI_Codex", detected_by="branch", identity_type="self",
                       merged_at="2026-01-01T00:00:00Z", outcome="recorded"), "ja")
        self.assertIn("審査記録あり", out); self.assertIn("推定", out)


if __name__ == "__main__":
    unittest.main()
