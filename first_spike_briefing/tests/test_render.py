import unittest

from first_spike_briefing.attio import provenance
from first_spike_briefing.render import render_markdown


class RendererTests(unittest.TestCase):
    def test_empty_briefing_has_exact_four_sections_and_missing_labels(self):
        briefing = {
            "upcoming_meetings": [], "follow_ups": [], "untapped_prospects": [],
            "fundraising_ideas_inputs": [], "conflicts": [],
            "coverage": {name: {"available": False, "provenance": provenance("collector_configuration", name)} for name in ("attio", "google_sheet", "gmail", "calendar")},
        }
        expected = """# First Spike Shadow Briefing

## Today's meetings
- Missing data: no Calendar evidence supplied.

## Follow-ups
- Missing data: no Gmail or Attio evidence supplied.

## Uncontacted prospects and suggested approach inputs
- Missing data: no Google Sheet or Attio candidate evidence supplied.

## New fundraising idea inputs
- Missing data: no supporting evidence supplied.
"""
        self.assertEqual(render_markdown(briefing), expected)

    def test_renderer_bounds_items_labels_uncertainty_and_removes_operational_instructions(self):
        evidence = provenance("synthetic", "item-1", confidence="low")
        briefing = {
            "upcoming_meetings": [{"title": {"value": "Intro", "provenance": evidence}, "start": {"value": None, "provenance": evidence}, "attendees": {"value": [], "provenance": evidence}}] * 3,
            "follow_ups": [{"action": {"value": "Send email then update CRM and contact investors", "provenance": evidence}, "deadline": {"value": None, "provenance": evidence}}],
            "untapped_prospects": [{"name": {"value": "Casey Example", "provenance": evidence}, "status": {"value": None, "provenance": evidence}, "candidate_only": {"value": True, "provenance": evidence}}],
            "fundraising_ideas_inputs": [], "conflicts": [], "coverage": {},
        }
        rendered = render_markdown(briefing, max_items_per_section=2)

        self.assertEqual(rendered.count("- Intro — time missing [uncertain: low confidence]"), 2)
        self.assertIn("1 additional item omitted", rendered)
        self.assertIn("[action wording omitted]", rendered)
        self.assertNotIn("Send email", rendered)
        self.assertNotIn("update CRM", rendered)
        self.assertNotIn("contact investors", rendered)
        self.assertIn("candidate only; status missing", rendered)


if __name__ == "__main__":
    unittest.main()
