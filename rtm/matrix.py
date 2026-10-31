"""Builds the requirements traceability matrix: objective -> business requirement -> requirement
-> user story -> automated tests -> defects, using the live results of the HSM security suite."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
LIVE_RESULTS = "https://artysficial.github.io/hsm-api-security-lab/results.json"


def load_json(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def fetch_test_results(url: str = LIVE_RESULTS, timeout: int = 15) -> tuple[dict, str]:
    """Latest published results of the HSM suite, or the committed snapshot if offline."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read()), "live"
    except Exception:
        return load_json("hsm_results_snapshot.json"), "snapshot"


@dataclass
class Trace:
    req: dict
    br: dict
    stories: list[dict]
    tests: list[dict]
    defects: list[dict]

    @property
    def status(self) -> str:
        if not self.stories:
            return "Not covered"
        if not self.tests:
            return "Untested"
        outcomes = {t["status"] for t in self.tests}
        if outcomes & {"failed", "error", "known defect"}:
            return "Failing"
        if outcomes <= {"passed"}:
            return "Verified"
        return "Partial"


def build(results: dict, model: dict | None = None, stories: list[dict] | None = None, defects: list[dict] | None = None) -> list[Trace]:
    model = model or load_json("requirements.json")
    stories = stories if stories is not None else load_json("stories.json")
    defects = defects if defects is not None else load_json("defects.json")
    brs = {b["id"]: b for b in model["business_requirements"]}
    traces = []
    for req in model["requirements"]:
        traces.append(Trace(
            req=req,
            br=brs[req["br"]],
            stories=[s for s in stories if req["id"] in s["requirements"]],
            tests=[t for t in results["tests"] if req["id"] in t["requirements"]],
            defects=[d for d in defects if d["requirement"] == req["id"]],
        ))
    return traces


def orphans(results: dict, model: dict | None = None, stories: list[dict] | None = None) -> dict:
    """References to requirements that do not exist (stories or tests pointing nowhere)."""
    model = model or load_json("requirements.json")
    stories = stories if stories is not None else load_json("stories.json")
    known = {r["id"] for r in model["requirements"]}
    return {
        "stories": sorted({r for s in stories for r in s["requirements"]} - known),
        "tests": sorted({r for t in results["tests"] for r in t["requirements"]} - known),
    }
