"""Quality gates for the requirements baseline: what a BA checks before sign-off."""

import re
from collections import Counter

import pytest

from rtm.matrix import build, orphans

STORY = re.compile(r"^As an? [^,]+, I want .+, so that .+$")
GHERKIN = re.compile(r"^Given .+ When .+ Then .+$")


@pytest.mark.category("Structure")
@pytest.mark.severity("critical")
def test_ids_are_unique(model, stories):
    """Objective, business requirement, requirement and story ids are unique"""
    ids = [o["id"] for o in model["objectives"]] + [b["id"] for b in model["business_requirements"]] + [r["id"] for r in model["requirements"]] + [s["id"] for s in stories]
    assert max(Counter(ids).values()) == 1


@pytest.mark.category("Structure")
@pytest.mark.severity("critical")
def test_every_requirement_traces_up_to_an_objective(model):
    """Each requirement belongs to a business requirement, and each of those to an objective"""
    objectives = {o["id"] for o in model["objectives"]}
    brs = {b["id"]: b for b in model["business_requirements"]}
    for req in model["requirements"]:
        assert req["br"] in brs, req["id"]
        assert brs[req["br"]]["objective"] in objectives


@pytest.mark.category("Structure")
@pytest.mark.severity("high")
def test_every_business_requirement_is_decomposed(model):
    """No business requirement is left without detailed requirements"""
    used = {r["br"] for r in model["requirements"]}
    assert all(b["id"] in used for b in model["business_requirements"])


@pytest.mark.category("Structure")
@pytest.mark.severity("medium")
def test_priorities_use_moscow(model):
    """Priorities are MoSCoW values"""
    assert {r["priority"] for r in model["requirements"]} <= {"Must", "Should", "Could", "Won't"}


@pytest.mark.category("Story quality")
@pytest.mark.severity("high")
def test_stories_follow_the_template(stories):
    """Stories read 'As a <role>, I want <goal>, so that <benefit>'"""
    bad = [s["id"] for s in stories if not STORY.match(s["story"])]
    assert not bad, bad


@pytest.mark.category("Story quality")
@pytest.mark.severity("high")
def test_acceptance_criteria_are_gherkin(stories):
    """Every story has testable Given / When / Then acceptance criteria"""
    for s in stories:
        assert s["acceptance"], s["id"]
        assert all(GHERKIN.match(ac) for ac in s["acceptance"]), s["id"]


@pytest.mark.category("Story quality")
@pytest.mark.severity("medium")
def test_story_points_are_fibonacci(stories):
    """Estimates use the Fibonacci scale"""
    assert all(s["points"] in (1, 2, 3, 5, 8, 13) for s in stories)


@pytest.mark.category("Coverage")
@pytest.mark.severity("critical")
def test_every_must_requirement_has_a_story_and_tests(results, model, stories):
    """Every Must requirement is covered by a story and at least one automated test"""
    for trace in build(results, model, stories):
        if trace.req["priority"] == "Must":
            assert trace.stories and trace.tests, trace.req["id"]


@pytest.mark.category("Coverage")
@pytest.mark.severity("high")
def test_no_orphan_references(results, model, stories):
    """No story or test points at a requirement that does not exist"""
    assert orphans(results, model, stories) == {"stories": [], "tests": []}


@pytest.mark.category("Coverage")
@pytest.mark.severity("high")
def test_failing_requirements_have_a_logged_defect(results, model, stories):
    """Any requirement whose tests fail is linked to a logged defect"""
    for trace in build(results, model, stories):
        if trace.status == "Failing":
            assert trace.defects, f"{trace.req['id']} fails without a defect"


@pytest.mark.category("Matrix logic")
@pytest.mark.severity("medium")
@pytest.mark.parametrize("statuses, has_story, expected", [
    (["passed", "passed"], True, "Verified"),
    (["passed", "known defect"], True, "Failing"),
    (["passed", "skipped"], True, "Partial"),
    ([], True, "Untested"),
    (["passed"], False, "Not covered"),
])
def test_trace_status_rules(model, statuses, has_story, expected):
    """Status rules: verified, failing, partial, untested and not covered"""
    req = model["requirements"][0]
    results = {"tests": [{"requirements": [req["id"]], "status": s} for s in statuses]}
    stories = [{"id": "US-X", "requirements": [req["id"]]}] if has_story else []
    trace = next(t for t in build(results, model, stories, []) if t.req["id"] == req["id"])
    assert trace.status == expected
