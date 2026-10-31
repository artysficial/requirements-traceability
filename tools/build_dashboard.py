"""Builds the traceability dashboard (site/index.html) from the requirements baseline and the
latest published HSM security test results."""

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import report_kit as rk  # noqa: E402
from rtm.matrix import build, fetch_test_results, load_json  # noqa: E402

PROCESS = [  # to-be process for a PIN translation request, swimlanes in order
    ("Card network", "Sends authorisation with PIN block under zone key"),
    ("Payments switch", "Requests token (REQ-01/02) and calls /pin/translate"),
    ("HSM API", "Checks scope (REQ-03), key ownership (REQ-04) and key usage (REQ-06)"),
    ("HSM API", "Validates PIN block format (REQ-07) and translates under destination key"),
    ("HSM API", "Writes audit entry without sensitive data (REQ-10)"),
    ("Issuer host", "Verifies the PIN and approves or declines"),
]


def main() -> None:
    results, source = fetch_test_results()
    model = load_json("requirements.json")
    stories = load_json("stories.json")
    traces = build(results, model, stories)
    status = Counter(t.status for t in traces)
    covered = sum(1 for t in traces if t.stories)
    tested = sum(1 for t in traces if t.tests)
    verified = status["Verified"]
    total = len(traces)
    done_points = sum(s["points"] for s in stories if s["status"] == "Done")
    all_points = sum(s["points"] for s in stories)

    body = rk.kpis([
        ("Requirements", total, f"from {len(model['business_requirements'])} business requirements, {len(model['objectives'])} objectives"),
        ("Story coverage", f"{covered / total:.0%}", f"{len(stories)} user stories"),
        ("Test coverage", f"{tested / total:.0%}", f"{len(results['tests'])} automated tests linked"),
        ("Verified", f"{verified}/{total}", "all linked tests passing", "ok" if verified == total else "warn"),
        ("Delivery", f"{done_points}/{all_points} pts", f"{sum(1 for s in stories if s['status'] == 'Done')} of {len(stories)} stories done"),
    ])
    body += rk.grid(
        rk.section("Traceability funnel", rk.bars([
            ("Business objectives", len(model["objectives"])),
            ("Business requirements", len(model["business_requirements"])),
            ("Requirements", total),
            ("User stories", len(stories)),
            ("Acceptance criteria", sum(len(s["acceptance"]) for s in stories)),
            ("Automated tests", len(results["tests"])),
        ])),
        rk.section("Requirement status", rk.donut([
            ("Verified", verified, "var(--green)"),
            ("Failing (defect logged)", status["Failing"], "var(--red)"),
            ("Partial", status["Partial"], "var(--orange)"),
            ("Untested / not covered", status["Untested"] + status["Not covered"], "var(--line)"),
        ], center=f"{verified / total:.0%}", caption="verified")),
    )
    rows = []
    for t in traces:
        passed = sum(1 for x in t.tests if x["status"] == "passed")
        rows.append([t.br["id"], t.req["id"], t.req["title"], t.req["priority"], ", ".join(s["id"] for s in t.stories) or "—",
                     f"{passed}/{len(t.tests)}", ", ".join(d["id"] for d in t.defects) or "—", rk.pill(t.status)])
    body += rk.section("Requirements traceability matrix", rk.table(["BR", "Requirement", "Description", "Priority", "Stories", "Tests passing", "Defects", "Status"], rows, {7}),
                       f"Test results are pulled from the HSM security suite's latest published run ({source}).")
    br_rows = [[b["id"], b["title"], b["objective"], b["owner"], sum(1 for t in traces if t.br["id"] == b["id"]),
                rk.pill("Verified" if all(t.status == "Verified" for t in traces if t.br["id"] == b["id"]) else "Partial")] for b in model["business_requirements"]]
    body += rk.section("Business requirements", rk.table(["ID", "Business requirement", "Objective", "Owner", "Requirements", "Status"], br_rows, {5}))
    flow = "".join(f'<li><span class="pill neutral">{rk.esc(lane)}</span> {rk.esc(step)}</li>' for lane, step in PROCESS)
    body += rk.section("To-be process: PIN translation", f'<ol style="line-height:2.2;padding-left:20px">{flow}</ol>',
                       "Each step names the requirements that control it; the full BPMN model is in docs/BRD.md.")
    story_rows = [[s["id"], s["story"], s["sprint"], s["points"], "<br>".join(rk.esc(a) for a in s["acceptance"]), rk.pill(s["status"])] for s in stories]
    body += rk.section("User stories and acceptance criteria", rk.table(["Story", "Narrative", "Sprint", "Points", "Acceptance criteria (Gherkin)", "Status"], story_rows, {4, 5}))
    checks = json.loads((ROOT / "reports" / "results.json").read_text(encoding="utf-8"))
    body += rk.section("Baseline quality gates", rk.table(["Check", "Area", "Result"], [[c["title"], c["category"], rk.pill(c["status"])] for c in checks["tests"]], {2}),
                       "Run on every change to the requirements: structure, story quality and coverage.")

    failing = [t.req["id"] for t in traces if t.status == "Failing"]
    verdict = (f"{verified}/{total} requirements verified · {', '.join(failing)} awaiting defect fixes", "warn") if failing else ("All requirements verified", "ok")
    rk.write(str(ROOT / "site" / "index.html"), rk.page(
        title="Requirements Traceability",
        eyebrow="IT Business Analyst · BRD to evidence",
        summary="The programme's Business Requirement Document traced end to end: objectives, business requirements, user stories with Gherkin acceptance criteria, live automated test results and defects.",
        body=body, repo="requirements-traceability", verdict=verdict,
    ))
    print(f"dashboard built ({source} results): {verified}/{total} verified")


if __name__ == "__main__":
    main()
