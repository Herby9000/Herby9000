import unittest

from first_spike_briefing.attio import provenance
from first_spike_briefing.reconcile import reconcile


def cell(value, source_id):
    return {"value": value, "provenance": provenance("google_sheet", source_id)}


class ReconciliationTests(unittest.TestCase):
    def test_sheet_status_wins_and_disagreement_is_surfaced(self):
        sheet = [{
            "name": cell("Ada Example", "book.xlsx#Fundraise!A2"),
            "email": cell("ada@example.test", "book.xlsx#Fundraise!B2"),
            "status": cell("Uncontacted", "book.xlsx#Fundraise!C2"),
            "approach": cell("Warm introduction", "book.xlsx#Fundraise!D2"),
        }]
        attio = {
            "pipeline": [{
                "record_id": "person-1", "name": "Ada Example", "email": "ADA@example.test",
                "stage": {"value": "Contacted", "provenance": provenance("attio_list_entry", "entry-1")},
            }],
            "potential_prospects": [], "tasks": [], "notes": [], "meetings": [],
        }

        result = reconcile(attio=attio, sheet=sheet, gmail=[], calendar=[])

        self.assertEqual(result["untapped_prospects"][0]["status"]["value"], "Uncontacted")
        self.assertEqual(result["untapped_prospects"][0]["suggested_approach_input"]["value"], "Warm introduction")
        self.assertEqual(result["conflicts"][0]["kind"], "pipeline_status")
        self.assertEqual(result["conflicts"][0]["authoritative_source"], "google_sheet")
        self.assertEqual(result["conflicts"][0]["values"]["attio"]["value"], "Contacted")

    def test_ambiguous_identity_is_flagged_and_not_silently_merged(self):
        sheet = [
            {"name": cell("Alex Example", "sheet!A2"), "email": cell("alex@example.test", "sheet!B2"), "status": cell("Uncontacted", "sheet!C2")},
            {"name": cell("Alex Other", "sheet!A3"), "email": cell("alex@example.test", "sheet!B3"), "status": cell("Contacted", "sheet!C3")},
        ]
        attio = {"pipeline": [{"record_id": "person-1", "name": "Alex Example", "email": "alex@example.test", "stage": {"value": "Contacted", "provenance": provenance("attio_list_entry", "entry-1")}}], "potential_prospects": [], "tasks": [], "notes": [], "meetings": []}

        result = reconcile(attio=attio, sheet=sheet, gmail=[], calendar=[])

        ambiguity = next(item for item in result["conflicts"] if item["kind"] == "ambiguous_identity")
        self.assertEqual(ambiguity["candidate_source_ids"], ["sheet!B2", "sheet!B3"])
        self.assertNotIn("pipeline_status", [item["kind"] for item in result["conflicts"]])

    def test_upcoming_followups_candidates_and_ideas_retain_provenance(self):
        attio = {
            "pipeline": [],
            "potential_prospects": [{"record_id": "candidate-1", "name": "Casey Example", "email": None, "candidate_only": True, "provenance": provenance("attio_record", "candidate-1", confidence="medium")}],
            "tasks": [{"id": "task-1", "content": "Review memo", "due_at": None}],
            "notes": [{"id": "note-1", "content": "Interested in climate", "created_at": "2026-09-30T00:00:00Z"}],
            "meetings": [{"id": "meeting-1", "title": "CRM intro", "start_at": "2026-10-04T09:00:00Z"}],
        }
        gmail = [{"thread_id": "thread-1", "subject": "Memo", "participants": [], "commitments": [{"text": "I will share it.", "deadline": None, "provenance": provenance("gmail_message", "message-1")}], "provenance": provenance("gmail_thread", "thread-1")}]
        calendar = [{"event_id": "event-1", "title": "Intro", "start": "2026-10-03T09:00:00Z", "end": None, "attendees": [], "provenance": provenance("calendar_event", "event-1")}]

        result = reconcile(attio=attio, sheet=[], gmail=gmail, calendar=calendar)

        self.assertEqual(result["upcoming_meetings"][0]["title"]["provenance"]["source_id"], "event-1")
        self.assertEqual(result["upcoming_meetings"][1]["title"]["provenance"]["source_id"], "meeting-1")
        self.assertIsNone(result["follow_ups"][0]["deadline"]["value"])
        self.assertTrue(result["untapped_prospects"][0]["candidate_only"]["value"])
        self.assertEqual(result["fundraising_ideas_inputs"][0]["input"]["value"], "Interested in climate")

    def test_attio_pipeline_is_fallback_when_sheet_is_missing(self):
        stage_evidence = provenance("attio_list_entry", "entry-1")
        attio = {
            "pipeline": [{"record_id": "person-1", "name": "Ada Example", "email": "ada@example.test", "stage": {"value": "Uncontacted", "provenance": stage_evidence}}],
            "potential_prospects": [], "tasks": [], "notes": [], "meetings": [],
        }

        result = reconcile(attio=attio)

        self.assertEqual(result["untapped_prospects"][0]["status"]["value"], "Uncontacted")
        self.assertEqual(result["untapped_prospects"][0]["status"]["provenance"]["source_id"], "entry-1")
        self.assertFalse(result["untapped_prospects"][0]["candidate_only"]["value"])
        self.assertFalse(result["coverage"]["google_sheet"]["available"])

    def test_missing_sources_degrade_explicitly_to_empty_sections(self):
        result = reconcile()

        self.assertEqual(list(result), ["upcoming_meetings", "follow_ups", "untapped_prospects", "fundraising_ideas_inputs", "conflicts", "coverage"])
        self.assertEqual(result["upcoming_meetings"], [])
        self.assertEqual(result["follow_ups"], [])
        self.assertFalse(result["coverage"]["google_sheet"]["available"])
        self.assertEqual(result["coverage"]["google_sheet"]["provenance"]["source_type"], "collector_configuration")


if __name__ == "__main__":
    unittest.main()
