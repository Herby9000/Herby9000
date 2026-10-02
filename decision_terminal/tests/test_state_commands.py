import stat
import tempfile
import unittest
from pathlib import Path

from decision_terminal.commands import AuthorizationError, apply_commands, parse_commands
from decision_terminal.state import DecisionState


ITEMS = [
    {
        "id": "DT-ABC123DEF456",
        "queue": "Decide",
        "summary": "Choose a synthetic option",
        "why_it_matters": "The sample project is waiting.",
        "proposed_next_action": "Choose A or B.",
        "confidence": "high",
        "provenance": {"source_type": "gmail_message", "source_id": "thread-1/message-1"},
    },
    {
        "id": "DT-111111111111",
        "queue": "Delegate",
        "summary": "Assign a synthetic task",
        "why_it_matters": "It has no assignee.",
        "proposed_next_action": "Name a delegate.",
        "confidence": "medium",
        "provenance": {"source_type": "business_note", "source_id": "note-1"},
    },
]


class StateTests(unittest.TestCase):
    def test_persists_transitions_and_does_not_complete_disappeared_items(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "decision-state.json"
            state = DecisionState(path)
            state.synchronize(ITEMS)
            state.transition("DT-ABC123DEF456", "confirmed")
            state.transition("DT-ABC123DEF456", "active")
            state.transition("DT-ABC123DEF456", "waiting", metadata={"reason": "sample reply"})

            reloaded = DecisionState(path)
            reloaded.synchronize([])
            record = reloaded.get("DT-ABC123DEF456")

            self.assertEqual(record["status"], "waiting")
            self.assertFalse(record["present_in_latest_snapshot"])
            self.assertEqual(record["history"][-1]["from"], "active")
            self.assertEqual(reloaded.get("DT-111111111111")["status"], "candidate")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_rejects_invalid_state_transition(self):
        with tempfile.TemporaryDirectory() as directory:
            state = DecisionState(Path(directory) / "state.json")
            state.synchronize(ITEMS)
            with self.assertRaisesRegex(ValueError, "invalid transition"):
                state.transition("DT-ABC123DEF456", "completed")


class CommandTests(unittest.TestCase):
    def test_sender_must_be_exact_authorized_address_after_case_normalization(self):
        parsed = parse_commands("done DT-ABC123DEF456", " CHTMORRIS@ICLOUD.COM ")
        self.assertEqual(parsed[0]["command"], "done")
        with self.assertRaises(AuthorizationError):
            parse_commands("done DT-ABC123DEF456", "owner@example.test")
        with self.assertRaises(AuthorizationError):
            parse_commands("done DT-ABC123DEF456", "chtmorris@icloud.com.example.test")

    def test_parses_and_applies_all_reply_commands_to_local_state_only(self):
        body = """done DT-ABC123DEF456
snooze DT-111111111111 until 2026-10-20
delegate DT-222222222222 to Jordan Example
waiting DT-333333333333 for sample response
not actionable DT-444444444444
details DT-555555555555
correct DT-666666666666 summary=Use the corrected synthetic summary
"""
        commands = parse_commands(body, "chtmorris@icloud.com")
        self.assertEqual([item["command"] for item in commands], ["done", "snooze", "delegate", "waiting", "not_actionable", "details", "correct"])
        self.assertEqual(commands[1]["until"], "2026-10-20")
        self.assertEqual(commands[2]["delegate_to"], "Jordan Example")

        all_items = ITEMS + [dict(ITEMS[0], id=f"DT-{number * 12}") for number in "23456"]
        with tempfile.TemporaryDirectory() as directory:
            state = DecisionState(Path(directory) / "state.json")
            state.synchronize(all_items)
            results = apply_commands(state, commands)
            self.assertEqual(state.get("DT-ABC123DEF456")["status"], "completed")
            self.assertEqual(state.get("DT-111111111111")["status"], "snoozed")
            self.assertEqual(state.get("DT-222222222222")["status"], "delegated")
            self.assertEqual(state.get("DT-333333333333")["status"], "waiting")
            self.assertEqual(state.get("DT-444444444444")["status"], "cancelled")
            self.assertTrue(state.get("DT-555555555555")["details_requested"])
            self.assertEqual(state.get("DT-666666666666")["corrections"]["summary"], "Use the corrected synthetic summary")
            self.assertEqual(next(result for result in results if result["command"] == "details")["status"], "details_requested")

    def test_rejects_unknown_or_malformed_commands_without_partial_parse(self):
        with self.assertRaisesRegex(ValueError, "invalid command"):
            parse_commands("archive DT-ABC123DEF456", "chtmorris@icloud.com")
        with self.assertRaisesRegex(ValueError, "invalid command"):
            parse_commands("snooze DT-ABC123DEF456 someday", "chtmorris@icloud.com")

    def test_rejects_snooze_dates_that_are_not_calendar_dates(self):
        with self.assertRaisesRegex(ValueError, "invalid command"):
            parse_commands("snooze DT-ABC123DEF456 until 2026-02-30", "chtmorris@icloud.com")


if __name__ == "__main__":
    unittest.main()
