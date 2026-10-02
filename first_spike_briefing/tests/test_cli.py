import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from first_spike_briefing.cli import main


class CliTests(unittest.TestCase):
    def test_cli_reads_local_json_and_emits_deterministic_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calendar = root / "calendar.json"
            calendar.write_text(json.dumps({"events": [{"id": "event-1", "title": "Intro", "start": "2026-10-03T09:00:00Z", "attendees": []}]}), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--calendar", str(calendar), "--format", "json"])
            document = json.loads(output.getvalue())

        self.assertEqual(code, 0)
        self.assertEqual(document["upcoming_meetings"][0]["title"]["value"], "Intro")
        self.assertFalse(document["coverage"]["gmail"]["available"])

    def test_cli_writes_only_to_explicit_output_path(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "briefing.md"
            code = main(["--format", "markdown", "--output", str(output_path)])
            rendered = output_path.read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertIn("# First Spike Shadow Briefing", rendered)


if __name__ == "__main__":
    unittest.main()
