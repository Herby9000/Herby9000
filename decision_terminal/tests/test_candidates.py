import unittest
from pathlib import Path

import decision_terminal

from decision_terminal.candidates import extract_candidates
from decision_terminal.inputs import normalize_business_notes, normalize_calendar, normalize_gmail


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.gmail_payload = {
            "threads": [
                {
                    "id": "thread-decide",
                    "subject": "Choose launch date",
                    "web_url": "https://mail.example.test/thread/thread-decide",
                    "messages": [
                        {
                            "id": "message-decide",
                            "timestamp": "2026-10-01T10:00:00Z",
                            "candidate": {
                                "key": "launch-date",
                                "kind": "decision",
                                "summary": "Choose the launch date",
                                "why_it_matters": "The synthetic team needs a date.",
                                "proposed_next_action": "Reply with option A or B.",
                                "confidence": "high",
                                "owner": {"value": "Alex Example", "evidence": "Alex owns the launch decision."},
                                "due_date": {"value": "2026-10-05", "evidence": "Please decide by 5 October."},
                            },
                        },
                        {
                            "id": "message-approve",
                            "timestamp": "2026-10-01T11:00:00Z",
                            "candidate": {
                                "key": "budget",
                                "kind": "approval",
                                "summary": "Approve the sample budget",
                                "why_it_matters": "Purchasing is paused.",
                                "proposed_next_action": "Reply approve or reject.",
                                "confidence": "medium",
                            },
                        },
                    ],
                },
                {
                    "id": "thread-operations",
                    "subject": "Synthetic operations",
                    "messages": [
                        {"id": "message-delegate", "candidate": {"key": "research", "kind": "delegation", "summary": "Assign sample research", "why_it_matters": "Research has no assignee.", "proposed_next_action": "Name a delegate.", "confidence": "high"}},
                        {"id": "message-wait", "candidate": {"key": "contract", "kind": "waiting", "summary": "Chase sample contract", "why_it_matters": "A reply is overdue.", "proposed_next_action": "Ask for a status update.", "confidence": "medium"}},
                        {"id": "message-stale", "candidate": {"key": "old-choice", "kind": "stale", "summary": "Review old sample decision", "why_it_matters": "The evidence is old.", "proposed_next_action": "Confirm whether it remains relevant.", "confidence": "low"}},
                    ],
                },
            ]
        }

    def test_normalizes_three_read_only_sources_and_retains_provenance(self):
        gmail = normalize_gmail(self.gmail_payload)
        calendar = normalize_calendar({"events": [{"id": "event-prepare", "title": "Sample review", "start": "2026-10-06T09:00:00Z", "html_link": "https://calendar.example.test/event/event-prepare", "candidate": {"key": "prep", "kind": "preparation", "summary": "Prepare sample review", "why_it_matters": "The review needs an agenda.", "proposed_next_action": "Draft three agenda bullets.", "confidence": "high", "review_date": {"value": "2026-10-05", "evidence": "Prepare the day before."}}}]})
        notes = normalize_business_notes({"notes": [{"id": "note-1", "excerpt": "A decision is requested.", "allowlisted": True, "candidate": {"key": "note-choice", "kind": "decision", "summary": "Choose sample note option", "why_it_matters": "The note records an open choice.", "proposed_next_action": "Select one documented option.", "confidence": "medium"}}, {"id": "note-secret", "excerpt": "Excluded", "allowlisted": False, "candidate": {"kind": "decision"}}]})

        self.assertEqual(gmail[0]["source_type"], "gmail_thread")
        self.assertEqual(gmail[0]["candidates"][0]["provenance"]["source_id"], "thread-decide/message-decide")
        self.assertEqual(calendar[0]["provenance"]["source_url"], "https://calendar.example.test/event/event-prepare")
        self.assertEqual([note["source_id"] for note in notes], ["note-1"])

    def test_extracts_all_six_queues_with_stable_ids_and_no_invented_fields(self):
        normalized = normalize_gmail(self.gmail_payload) + normalize_calendar({"events": [{"id": "event-prepare", "title": "Sample review", "candidate": {"key": "prep", "kind": "preparation", "summary": "Prepare sample review", "why_it_matters": "An agenda is needed.", "proposed_next_action": "Draft the agenda.", "confidence": "high"}}]})
        first = extract_candidates(normalized)
        changed_copy = normalize_gmail(self.gmail_payload)
        changed_copy[0]["candidates"][0]["summary"] = "Edited wording does not change identity"
        second = extract_candidates(changed_copy)

        self.assertEqual({item["queue"] for item in first}, {"Decide", "Approve", "Delegate", "Chase/Waiting", "Prepare", "Stale"})
        decide = next(item for item in first if item["queue"] == "Decide")
        changed_decide = next(item for item in second if item["queue"] == "Decide")
        approve = next(item for item in first if item["queue"] == "Approve")
        self.assertEqual(decide["id"], changed_decide["id"])
        self.assertEqual(decide["owner"], "Alex Example")
        self.assertEqual(decide["due_date"], "2026-10-05")
        self.assertNotIn("owner", approve)
        self.assertNotIn("due_date", approve)
        self.assertNotIn("review_date", approve)
        self.assertEqual(approve["provenance"]["source_id"], "thread-decide/message-approve")

    def test_rejects_blank_required_text_and_blank_optional_field_evidence(self):
        normalized = normalize_gmail(self.gmail_payload)
        normalized[0]["candidates"][0]["proposed_next_action"] = "   "
        with self.assertRaisesRegex(ValueError, "proposed_next_action"):
            extract_candidates(normalized)

        normalized = normalize_gmail(self.gmail_payload)
        normalized[0]["candidates"][0]["owner"]["evidence"] = "   "
        with self.assertRaisesRegex(ValueError, "owner"):
            extract_candidates(normalized)

    def test_first_spike_tag_is_accepted_only_for_private_decisions_or_commitments(self):
        valid = normalize_business_notes({"notes": [{"id": "note-valid", "allowlisted": True, "tags": ["first_spike_private_action"], "candidate": {"key": "choice", "kind": "decision", "summary": "Choose sample option", "why_it_matters": "A private decision is open.", "proposed_next_action": "Choose A or B.", "confidence": "high"}}]})
        self.assertEqual(len(valid), 1)
        with self.assertRaisesRegex(ValueError, "first_spike_private_action"):
            normalize_business_notes({"notes": [{"id": "note-invalid", "allowlisted": True, "tags": ["first_spike_private_action"], "candidate": {"key": "pipeline", "kind": "approval", "summary": "Analyze prospects", "why_it_matters": "Pipeline analysis.", "proposed_next_action": "Rank prospects.", "confidence": "high"}}]})

    def test_production_package_is_separate_from_first_spike_modules(self):
        package = Path(decision_terminal.__file__).parent
        production = "\n".join(path.read_text(encoding="utf-8") for path in package.glob("*.py"))
        self.assertNotIn("first_spike_briefing", production)


if __name__ == "__main__":
    unittest.main()
