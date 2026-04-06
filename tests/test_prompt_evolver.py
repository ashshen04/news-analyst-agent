"""Tests for prompt_evolver.py — synthesis gating and file writing."""

from unittest.mock import MagicMock, patch


class TestShouldEvolvePrompt:
    def test_returns_false_below_threshold(self, tmp_db):
        from db import save_feedback
        save_feedback("2026-04-04", "AI", 4, "Good")
        save_feedback("2026-04-04", "AI", 3, "Okay")
        from prompt_evolver import should_evolve_prompt
        assert should_evolve_prompt() is False

    def test_returns_true_at_threshold(self, tmp_db):
        from db import save_feedback
        for i in range(3):
            save_feedback("2026-04-04", "AI", 4, f"Comment {i}")
        from prompt_evolver import should_evolve_prompt
        assert should_evolve_prompt() is True

    def test_returns_false_after_synthesis(self, tmp_db):
        from db import save_feedback, save_synthesis_log
        for i in range(3):
            save_feedback("2026-04-04", "AI", 4, f"Comment {i}")
        save_synthesis_log(3, "- Be concise")
        from prompt_evolver import should_evolve_prompt
        assert should_evolve_prompt() is False


class TestEvolvePrompt:
    @patch("prompt_evolver.ChatGroq")
    def test_writes_preferences_file(self, mock_groq_cls, tmp_db, tmp_path, monkeypatch):
        from db import save_feedback
        for i in range(3):
            save_feedback("2026-04-04", "AI", 5, f"Be more concise {i}")

        fake_resp = MagicMock()
        fake_resp.content = "- Be concise\n- Use bullet points"
        mock_groq_cls.return_value.invoke.return_value = fake_resp

        prefs_path = tmp_path / "user_preferences.md"
        monkeypatch.setattr("prompt_evolver.PREFS_PATH", prefs_path)

        from prompt_evolver import evolve_prompt
        result = evolve_prompt()
        assert result is True
        assert prefs_path.read_text() == "- Be concise\n- Use bullet points"

    @patch("prompt_evolver.ChatGroq")
    def test_llm_failure_returns_false(self, mock_groq_cls, tmp_db):
        from db import save_feedback
        for i in range(3):
            save_feedback("2026-04-04", "AI", 5, f"Comment {i}")
        mock_groq_cls.return_value.invoke.side_effect = Exception("LLM error")
        from prompt_evolver import evolve_prompt
        result = evolve_prompt()
        assert result is False

    def test_skipped_when_below_threshold(self, tmp_db):
        from db import save_feedback
        save_feedback("2026-04-04", "AI", 4, "One comment")
        from prompt_evolver import evolve_prompt
        result = evolve_prompt()
        assert result is False
