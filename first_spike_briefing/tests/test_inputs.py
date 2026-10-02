import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from first_spike_briefing.inputs import parse_calendar, parse_gmail, parse_xlsx


def synthetic_workbook() -> bytes:
    files = {
        "xl/workbook.xml": """<?xml version='1.0' encoding='UTF-8'?><workbook xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main' xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships'><sheets><sheet name='Fundraise' sheetId='1' r:id='rId1'/><sheet name='Unrelated' sheetId='2' r:id='rId2'/></sheets></workbook>""",
        "xl/_rels/workbook.xml.rels": """<?xml version='1.0' encoding='UTF-8'?><Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'><Relationship Id='rId1' Target='worksheets/sheet1.xml'/><Relationship Id='rId2' Target='worksheets/sheet2.xml'/></Relationships>""",
        "xl/sharedStrings.xml": """<?xml version='1.0' encoding='UTF-8'?><sst xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'><si><t>Name</t></si><si><t>Email</t></si><si><t>Status</t></si><si><t>Ada Example</t></si><si><t>ada@example.test</t></si><si><t>Uncontacted</t></si><si><t>Should Not Appear</t></si></sst>""",
        "xl/worksheets/sheet1.xml": """<?xml version='1.0' encoding='UTF-8'?><worksheet xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'><sheetData><row r='1'><c r='A1' t='s'><v>0</v></c><c r='B1' t='s'><v>1</v></c><c r='C1' t='s'><v>2</v></c></row><row r='2'><c r='A2' t='s'><v>3</v></c><c r='B2' t='s'><v>4</v></c><c r='C2' t='s'><v>5</v></c></row></sheetData></worksheet>""",
        "xl/worksheets/sheet2.xml": """<?xml version='1.0' encoding='UTF-8'?><worksheet xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'><sheetData><row r='1'><c r='A1' t='s'><v>6</v></c></row></sheetData></worksheet>""",
    }
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, value in files.items():
            archive.writestr(name, value)
    return stream.getvalue()


class InputAdapterTests(unittest.TestCase):
    def test_xlsx_extracts_only_configured_tabs_with_cell_provenance(self):
        result = parse_xlsx(synthetic_workbook(), ["Fundraise"], source_id="fundraise.xlsx")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"]["value"], "Ada Example")
        self.assertEqual(result[0]["status"]["value"], "Uncontacted")
        self.assertEqual(result[0]["status"]["provenance"]["source_id"], "fundraise.xlsx#Fundraise!C2")
        self.assertNotIn("Should Not Appear", repr(result))

    def test_xlsx_accepts_a_path_without_writing_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.xlsx"
            path.write_bytes(synthetic_workbook())
            before = path.read_bytes()
            result = parse_xlsx(path, ["Fundraise"])
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(result[0]["email"]["value"], "ada@example.test")

    def test_gmail_and_calendar_normalize_evidence_without_authentication(self):
        gmail = parse_gmail({"threads": [{"id": "thread-1", "subject": "Intro", "participants": ["ada@example.test"], "messages": [{"id": "msg-1", "timestamp": "2026-10-01T10:00:00Z", "snippet": "I will share the memo next week."}]}]})
        calendar = parse_calendar({"events": [{"id": "event-1", "title": "Investor intro", "start": "2026-10-03T09:00:00Z", "attendees": ["ada@example.test"]}]})

        self.assertEqual(gmail[0]["commitments"][0]["text"], "I will share the memo next week.")
        self.assertIsNone(gmail[0]["commitments"][0]["deadline"])
        self.assertEqual(gmail[0]["provenance"]["source_id"], "thread-1")
        self.assertEqual(calendar[0]["provenance"]["source_id"], "event-1")
        self.assertEqual(calendar[0]["attendees"], ["ada@example.test"])

    def test_json_fixture_paths_are_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gmail.json"
            path.write_text(json.dumps({"threads": []}), encoding="utf-8")
            self.assertEqual(parse_gmail(path), [])


if __name__ == "__main__":
    unittest.main()
