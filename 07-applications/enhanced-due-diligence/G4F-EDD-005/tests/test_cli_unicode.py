import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from entity_resolution import Record, record_decision, resolve

ROOT = Path(__file__).resolve().parent.parent
TEXT_FIELDS = (
    "record_id",
    "name",
    "source",
    "registration_id",
    "jurisdiction",
    "city",
    "id_scheme",
    "aliases",
)


def rows_with(field, value):
    rows = [
        {
            "record_id": record_id,
            "name": "Kestrel Paper",
            "registration_id": "SYN-1",
            "jurisdiction": "GB",
            "city": "York",
        }
        for record_id in ("A", "B")
    ]
    rows[0][field] = [value] if field == "aliases" else value
    return rows


def run_cli(tmp_path, rows, *args, config=None, filename="records.json"):
    path = tmp_path / filename
    # Escaped JSON can carry a lone surrogate even in a valid UTF-8 file.
    path.write_text(json.dumps({"records": rows}), encoding="utf-8")
    command = [sys.executable, "-X", "utf8", "-m", "entity_resolution", str(path)]
    if config is not None:
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        command.extend(("--config", str(config_path)))
    return subprocess.run(
        [*command, *args],
        cwd=ROOT,
        env={**os.environ, "PYTHONIOENCODING": "utf-8:strict"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
    )


@pytest.mark.parametrize("field", TEXT_FIELDS)
@pytest.mark.parametrize("codepoint", [0xD800, 0xDFFF])
def test_record_rejects_lone_surrogates_without_echoing_them(field, codepoint):
    surrogate = chr(codepoint)
    with pytest.raises(ValueError, match="valid Unicode") as caught:
        Record(**rows_with(field, "A" + surrogate)[0])

    assert surrogate not in str(caught.value)
    str(caught.value).encode("utf-8", errors="strict")


@pytest.mark.parametrize("field", TEXT_FIELDS)
@pytest.mark.parametrize("codepoint", [0xD800, 0xDFFF])
@pytest.mark.parametrize("args", [(), ("--json",)])
def test_cli_rejects_lone_surrogates_cleanly(tmp_path, field, codepoint, args):
    surrogate = chr(codepoint)
    done = run_cli(tmp_path, rows_with(field, "A" + surrogate), *args)

    assert done.returncode == 2
    assert done.stdout == ""
    assert "error:" in done.stderr
    assert "valid Unicode" in done.stderr
    assert "Traceback" not in done.stderr
    assert surrogate not in done.stderr


@pytest.mark.parametrize("field", ["reviewer", "note"])
@pytest.mark.parametrize("codepoint", [0xD800, 0xDFFF])
def test_review_rejects_lone_surrogates_without_echoing_them(field, codepoint):
    surrogate = chr(codepoint)
    result = resolve([Record("A", "Kestrel"), Record("B", "Kestrel")]).matches[0]
    kwargs = {"reviewer": "analyst", "accepted": True, field: "A" + surrogate}

    with pytest.raises(ValueError, match="valid Unicode") as caught:
        record_decision(result, **kwargs)

    assert surrogate not in str(caught.value)
    str(caught.value).encode("utf-8", errors="strict")


@pytest.mark.parametrize(
    ("control", "escaped"),
    [
        ("\n", r"\n"),
        ("\r", r"\r"),
        ("\t", r"\t"),
        ("\x1b", r"\x1b"),
        ("\x9b", r"\x9b"),
        ("\u2028", r"\u2028"),
        ("\u2029", r"\u2029"),
    ],
)
def test_cli_escapes_controls_in_ids_and_preserves_json(tmp_path, control, escaped):
    record_id = "A" + control + "FAKE[31m"
    rows = rows_with("record_id", record_id)

    text = run_cli(tmp_path, rows)
    assert text.returncode == 0, text.stderr
    assert text.stderr == ""
    assert f"A{escaped}FAKE[31m <> B  score=100.0" in text.stdout
    assert len(text.stdout.splitlines()) == 8
    assert control not in text.stdout.replace("\n", "")

    structured = run_cli(tmp_path, rows, "--json")
    assert structured.returncode == 0, structured.stderr
    assert structured.stderr == ""
    assert json.loads(structured.stdout)["matches"][0]["left_id"] == record_id


@pytest.mark.parametrize(
    "field", ["registration_id", "jurisdiction", "city", "id_scheme"]
)
def test_cli_escapes_controls_in_evidence_notes(tmp_path, field):
    rows = rows_with(field, "SYN\nFAKE\x1b[31m\r\t")
    rows[1][field] = rows[0][field]
    if field == "id_scheme":
        rows[1][field] = "other scheme"

    text = run_cli(tmp_path, rows)
    assert text.returncode == 0, text.stderr
    assert text.stderr == ""
    expected = (
        "SYN\\nFAKE\\x1b[31M"
        if field == "jurisdiction"
        else "SYN\\nFAKE\\x1b[31m\\r\\t"
    )
    assert expected in text.stdout
    assert "\x1b" not in text.stdout
    assert "\t" not in text.stdout

    structured = run_cli(tmp_path, rows, "--json")
    assert structured.returncode == 0, structured.stderr
    notes = json.loads(structured.stdout)["matches"][0]["evidence"]["notes"]
    assert any("\n" in note and "\x1b" in note for note in notes)


def test_cli_escapes_controls_in_input_errors(tmp_path):
    # Unicode line separators are valid filenames on Windows and Unix.
    done = run_cli(
        tmp_path,
        [{"record_id": "A", "name": None}],
        filename="bad\u2028records.json",
    )

    assert done.returncode == 2
    assert done.stdout == ""
    assert "error:" in done.stderr
    assert "bad\\u2028records.json" in done.stderr
    assert "\u2028" not in done.stderr
    assert "Traceback" not in done.stderr


def test_cli_escapes_controls_in_argument_errors(tmp_path):
    done = run_cli(tmp_path, rows_with("record_id", "A"), "--unknown\nFAKE\x1b[31m\r\t")

    assert done.returncode == 2
    assert done.stdout == ""
    assert "--unknown\\nFAKE\\x1b[31m\\r\\t" in done.stderr
    assert "\x1b" not in done.stderr
    assert "\r" not in done.stderr
    assert "\t" not in done.stderr
    assert "Traceback" not in done.stderr


def test_cli_keeps_skipped_block_warnings_safe_and_json_unchanged(tmp_path):
    jurisdiction = "GB\nFAKE\x1b[31m\r\t"
    rows = rows_with("jurisdiction", jurisdiction)
    rows[1]["jurisdiction"] = jurisdiction
    rows.append({**rows[0], "record_id": "C"})
    config = {"max_block_size": 2, "max_id_block_size": 2}

    text = run_cli(tmp_path, rows, config=config)
    assert text.returncode == 0, text.stderr
    assert "warning:" in text.stdout
    assert "GB\\nFAKE\\x1b[31M" in text.stdout
    assert "\x1b" not in text.stdout
    assert "\r" not in text.stdout
    assert "\t" not in text.stdout

    structured = run_cli(tmp_path, rows, "--json", config=config)
    assert structured.returncode == 0, structured.stderr
    blocks = json.loads(structured.stdout)["skipped_blocks"]
    assert any(jurisdiction.upper().strip() in block["key"] for block in blocks)


def test_cli_preserves_valid_unicode_and_json_surrogate_pairs(tmp_path):
    record_id = "Société-नमस्ते-東芝-😀"
    rows = rows_with("record_id", record_id)
    rows[0]["name"] = rows[1]["name"] = "Северный Ветер"
    rows[0]["city"] = rows[1]["city"] = "Łódź"

    text = run_cli(tmp_path, rows)
    assert text.returncode == 0, text.stderr
    assert record_id in text.stdout
    assert "'северный ветер'" in text.stdout
    assert "Łódź" in text.stdout

    structured = run_cli(tmp_path, rows, "--json")
    assert structured.returncode == 0, structured.stderr
    match = json.loads(structured.stdout)["matches"][0]
    assert match["left_id"] == record_id
    assert match["evidence"]["name"]["left"] == "Северный Ветер"
