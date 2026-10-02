import unittest

from first_spike_briefing.attio import AttioCollector, ReadOnlyPolicy, ReadOnlyViolation


class ReadOnlyPolicyTests(unittest.TestCase):
    def test_allows_get_and_only_known_query_posts(self):
        policy = ReadOnlyPolicy()
        policy.validate("GET", "/v2/lists")
        policy.validate("POST", "/v2/lists/list-primary/entries/query")
        policy.validate("POST", "/v2/objects/people/records/query")

        for method, path in [
            ("PATCH", "/v2/records/people/1"),
            ("PUT", "/v2/records/people/1"),
            ("DELETE", "/v2/records/people/1"),
            ("POST", "/v2/tasks"),
            ("POST", "/v2/lists/list-primary/entries"),
        ]:
            with self.subTest(method=method, path=path):
                with self.assertRaises(ReadOnlyViolation):
                    policy.validate(method, path)

    def test_primary_list_is_authoritative_and_unrelated_list_data_is_excluded(self):
        payload = {
            "lists": [{"id": "list-primary", "name": "Fundraise"}, {"id": "list-other", "name": "Sales"}],
            "list_attributes": {
                "list-primary": [{"id": "stage", "title": "Stage"}],
                "list-other": [{"id": "private-sales", "title": "Sales notes"}],
            },
            "list_entries": {
                "list-primary": [{"id": "entry-1", "record_id": "person-1", "stage": "Contacted", "updated_at": "2026-09-30T10:00:00Z"}],
                "list-other": [{"id": "entry-secret", "record_id": "person-2", "stage": "Do not leak"}],
            },
            "records": [
                {"id": "person-1", "object": "people", "name": "Ada Example", "email": "ada@example.test"},
                {"id": "person-2", "object": "people", "name": "Bea Example", "email": "bea@example.test"},
            ],
            "tasks": [{"id": "task-1", "record_id": "person-1", "content": "Prepare memo", "due_at": None}],
            "notes": [{"id": "note-1", "record_id": "person-1", "content": "Asked for deck", "created_at": "2026-09-29T10:00:00Z"}],
            "meetings": [{"id": "meeting-1", "record_id": "person-1", "title": "Intro", "start_at": "2026-10-03T09:00:00Z"}],
        }

        result = AttioCollector("list-primary").collect(payload)

        self.assertEqual(result["primary_list"]["id"], "list-primary")
        self.assertEqual(result["list_attributes"], [{"id": "stage", "title": "Stage"}])
        self.assertEqual(result["pipeline"][0]["stage"]["value"], "Contacted")
        self.assertEqual(result["pipeline"][0]["stage"]["provenance"]["source_id"], "entry-1")
        self.assertEqual([candidate["record_id"] for candidate in result["potential_prospects"]], ["person-2"])
        self.assertEqual([item["id"] for item in result["tasks"]], ["task-1"])
        self.assertNotIn("entry-secret", repr(result))
        self.assertNotIn("private-sales", repr(result))
        self.assertNotIn("Do not leak", repr(result))


if __name__ == "__main__":
    unittest.main()
