"""The agent guide served without writing into the workspace."""

from pathlib import Path

from lumlflow.flow.daemon import docs
from lumlflow.flow.store.flowstore import store_dir

from tests.daemon.helpers import (
    REPORT_CELL,
    SCORE_CELL,
    daemon_api,
    make_workspace,
    no_git_words,
    write_cell,
)

USER_GUIDE = Path(__file__).resolve().parents[2] / "docs" / "user-guide.md"


def test_the_served_guide_names_the_current_agent_surface() -> None:
    guide = docs.CHEATSHEET

    assert "Experiments tracker" in guide
    assert "returns a reference" in guide
    assert "lumlflow cells move" in guide
    assert "lumlflow agents list" in guide
    assert "lumlflow guide" in guide
    assert "lumlflow mcp" in guide
    assert "--workspace" not in guide
    assert "lane" in guide


def test_the_user_guide_does_not_describe_the_removed_file_lock() -> None:
    guide = USER_GUIDE.read_text("utf-8")

    assert '"The agent is working in the files."' not in guide
    assert "saved · not yet written to files" not in guide


async def test_flow_operations_write_no_agent_guide_into_the_workspace(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project", flows=("churn", "sales"))
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        assert "agent.connect" not in api.methods
        await api.status({})
        await api.flow_open({"flow": "churn"})
        await api.run({"flow": "churn", "target": "score"})

    assert not (root / "AGENTS.md").exists()


async def test_a_teams_own_instructions_are_never_rewritten(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project")
    path = root / "AGENTS.md"
    original = "# Our house rules\n\nRun the linter before you finish.\n"
    path.write_text(original, encoding="utf-8")

    async with daemon_api(root) as api:
        await api.status({})
        await api.flow_open({"flow": "churn"})

    assert path.read_text("utf-8") == original


async def test_flow_operations_do_not_write_a_checkout_sidecar(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"flow": "churn", "target": "report"})

    assert not (store_dir(flow) / "CHECKOUT.md").exists()


def test_the_served_guide_never_speaks_the_vocabulary_git_owns() -> None:
    no_git_words(docs.CHEATSHEET, "the cheatsheet")
