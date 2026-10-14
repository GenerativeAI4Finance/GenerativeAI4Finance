"""Run a few allowed and denied calls against policy.json and print the audit log."""

import logging
import sys
from pathlib import Path

from permissions import PermissionDenied, ToolGate, load_policy

logging.basicConfig(
    stream=sys.stdout, level=logging.INFO, format="%(levelname)s %(message)s"
)

tools = {
    "fetch_source": lambda source_id: f"synthetic document {source_id}",
    "list_sources": lambda: ["SYN-SRC-0001", "SYN-SRC-0002"],
    "read_evidence": lambda case_id: {"case_id": case_id, "items": 3},
    "match_entities": lambda case_id, threshold: [],
    "write_note": lambda case_id, note: "saved",
    "set_review_status": lambda case_id, status: status,
}

gate = ToolGate(load_policy(Path(__file__).parent / "policy.json"), tools)
analyst = gate.for_agent("analyst-01")

analyst.call("read_evidence", case_id="SYN-CASE-0007")
analyst.call(
    "write_note",
    case_id="SYN-CASE-0007",
    note="Registry date differs between two sources.",
)

attempts = [
    ("set_review_status", {"case_id": "SYN-CASE-0007", "status": "closed_no_finding"}),
    ("fetch_source", {"source_id": "SYN-SRC-0001"}),
    (
        "read_evidence",
        {"case_id": "SYN-CASE-0007", "api_key": "sk-test0000000000000000000000"},
    ),
]
for tool, args in attempts:
    try:
        analyst.call(tool, **args)
    except PermissionDenied as e:
        print(f"denied: {e}")
