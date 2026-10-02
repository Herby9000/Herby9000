import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from decision_terminal.cli import main


GMAIL = {
    "threads": [{
        "id": "thread-cli",
        "subject": "Synthetic choice",
        "messages": [{
            "id": "message-cli",
            "timestamp": "2026-10-02T10:00:00Z",
            "candidate": {
                "key": "choice",
                "kind": "decision",
                "summary": "Choose a synthetic CLI option",
                "why_it_matters": "The fixture needs a choice.",
                "proposed_next_action": "Choose A or B.",
                "confidence": "high",
            },
        }],
    }]
}


class CliTests(unittest.TestCase):
    def test_build_reads_local_json_updates_state_and_writes_json_to_stdout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gmail = root / "gmail.json"
            state = root / "state.json"
            gmail.write_text(json.dumps(GMAIL), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["build", "--gmail", str(gmail), "--state", str(state), "--format", "json"])
            document = json.loads(output.getvalue())
            persisted = json.loads(state.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(document["items"][0]["queue"], "Decide")
        self.assertEqual(len(persisted["items"]), 1)

    def test_build_writes_html_and_threaded_rfc822_only_to_explicit_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gmail = root / "gmail.json"
            state = root / "state.json"
            html_path = root / "edition.html"
            mail_path = root / "edition.eml"
            gmail.write_text(json.dumps(GMAIL), encoding="utf-8")

            html_code = main(["build", "--gmail", str(gmail), "--state", str(state), "--format", "html", "--edition-label", "Synthetic edition", "--output", str(html_path)])
            mail_code = main([
                "build", "--gmail", str(gmail), "--state", str(state), "--format", "rfc822", "--output", str(mail_path),
                "--edition-id", "fixture-edition-2", "--sent-at", "2026-10-02T12:00:00+00:00", "--from", "terminal@example.test",
                "--to", "reader@example.test", "--message-id-domain", "example.test", "--in-reply-to", "<first@example.test>",
                "--reference", "<root@example.test>", "--reference", "<first@example.test>",
            ])

            self.assertEqual(html_code, 0)
            self.assertEqual(mail_code, 0)
            self.assertIn("Synthetic edition", html_path.read_text(encoding="utf-8"))
            mail = mail_path.read_bytes()
            self.assertIn(b"Subject: Decision Terminal", mail)
            self.assertIn(b"In-Reply-To: <first@example.test>", mail)

    def test_commands_require_sender_and_update_only_supplied_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gmail = root / "gmail.json"
            state = root / "state.json"
            reply = root / "reply.txt"
            gmail.write_text(json.dumps(GMAIL), encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                main(["build", "--gmail", str(gmail), "--state", str(state), "--format", "json"])
            item_id = next(iter(json.loads(state.read_text(encoding="utf-8"))["items"]))
            reply.write_text(f"done {item_id}\n", encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["commands", "--reply", str(reply), "--sender", "chtmorris@icloud.com", "--state", str(state)])

            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())["results"][0]["status"], "completed")
            self.assertEqual(json.loads(state.read_text(encoding="utf-8"))["items"][item_id]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
