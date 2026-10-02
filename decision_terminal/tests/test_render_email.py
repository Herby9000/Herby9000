import unittest
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser

from decision_terminal.email_message import build_edition_message
from decision_terminal.render import render_html


class RenderTests(unittest.TestCase):
    def test_renders_six_mobile_friendly_queues_with_escaping_and_provenance(self):
        items = [
            {
                "id": "DT-ABC123DEF456",
                "queue": "Decide",
                "summary": "Choose <Option A>",
                "why_it_matters": "A & B are waiting.",
                "proposed_next_action": "Reply with A or B.",
                "confidence": "low",
                "provenance": {"source_type": "gmail_message", "source_id": "thread-1/message-1", "source_url": "https://mail.example.test/thread?a=1&b=2"},
            },
            {"id": "DT-111111111111", "queue": "Approve", "summary": "Approve sample", "why_it_matters": "Sample reason", "proposed_next_action": "Approve or reject.", "confidence": "high", "provenance": {"source_type": "business_note", "source_id": "note-1"}},
        ]
        rendered = render_html(items, edition_label="2 October 2026")

        for queue in ("Decide", "Approve", "Delegate", "Chase/Waiting", "Prepare", "Stale"):
            self.assertIn(f">{queue}<", rendered)
        self.assertIn('<meta name="viewport" content="width=device-width, initial-scale=1">', rendered)
        self.assertIn("max-width:600px", rendered)
        self.assertIn("DT-ABC123DEF456", rendered)
        self.assertIn("Uncertain · low confidence", rendered)
        self.assertIn("gmail_message · thread-1/message-1", rendered)
        self.assertIn('href="https://mail.example.test/thread?a=1&amp;b=2"', rendered)
        self.assertIn("Choose &lt;Option A&gt;", rendered)
        self.assertNotIn("Choose <Option A>", rendered)
        self.assertNotIn("javascript:", render_html([dict(items[0], provenance={"source_type": "gmail_message", "source_id": "id", "source_url": "javascript:alert(1)"})]))


class EmailMessageTests(unittest.TestCase):
    def test_first_message_has_stable_subject_and_unique_deterministic_id(self):
        first = build_edition_message(
            "<html><body>Edition one</body></html>",
            edition_id="edition-1",
            sent_at=datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc),
            sender="terminal@example.test",
            recipient="reader@example.test",
            message_id_domain="example.test",
        )
        repeat = build_edition_message(
            "<html><body>Edition one</body></html>",
            edition_id="edition-1",
            sent_at=datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc),
            sender="terminal@example.test",
            recipient="reader@example.test",
            message_id_domain="example.test",
        )
        second = build_edition_message(
            "<html><body>Edition two</body></html>",
            edition_id="edition-2",
            sent_at=datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc),
            sender="terminal@example.test",
            recipient="reader@example.test",
            message_id_domain="example.test",
        )

        self.assertEqual(first["Subject"], "Decision Terminal")
        self.assertEqual(first["Message-ID"], repeat["Message-ID"])
        self.assertNotEqual(first["Message-ID"], second["Message-ID"])
        self.assertIsNone(first["In-Reply-To"])
        self.assertIsNone(first["References"])
        self.assertEqual(first.get_content_type(), "multipart/alternative")

    def test_later_message_sets_configurable_thread_headers_and_serializes_rfc822(self):
        message = build_edition_message(
            "<html><body>Edition two</body></html>",
            edition_id="edition-2",
            sent_at=datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc),
            sender="terminal@example.test",
            recipient="reader@example.test",
            message_id_domain="example.test",
            in_reply_to="<first@example.test>",
            references=["<root@example.test>", "<first@example.test>"],
        )
        serialized = message.as_bytes(policy=policy.SMTP)
        reparsed = BytesParser(policy=policy.default).parsebytes(serialized)

        self.assertEqual(reparsed["In-Reply-To"], "<first@example.test>")
        self.assertEqual(reparsed["References"], "<root@example.test> <first@example.test>")
        self.assertIn(b"Content-Type: text/html", serialized)
        self.assertTrue(serialized.endswith(b"\r\n"))


if __name__ == "__main__":
    unittest.main()
