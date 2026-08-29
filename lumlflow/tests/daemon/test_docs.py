"""The generated workspace guide.

The quickstart's length is a contract, not a preference — Tier-0 says an agent
learns the whole loop from it, and a cheatsheet nobody finishes reading teaches
nothing.
"""

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

QUICKSTART_LINES = 22
USER_GUIDE = Path(__file__).resolve().parents[2] / "docs" / "user-guide.md"


def test_the_quickstart_fits_in_about_twenty_lines_and_names_the_three_gestures():
    lines = docs.QUICKSTART.strip().splitlines()

    assert len(lines) <= QUICKSTART_LINES
    assert "lumlflow run <cell>" in docs.QUICKSTART
    assert "lumlflow status" in docs.QUICKSTART
    assert "lumlflow context" in docs.QUICKSTART


def test_the_user_guide_does_not_describe_the_removed_file_lock() -> None:
    guide = USER_GUIDE.read_text("utf-8")

    assert '"The agent is working in the files."' not in guide
    assert "saved · not yet written to files" not in guide


async def test_agents_md_lands_at_the_workspace_root_and_names_every_flow(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project", flows=("churn", "sales"))
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.status({})

    generated = (root / docs.AGENTS_NAME).read_text("utf-8")
    assert "`churn`" in generated and "`sales`" in generated
    assert docs.QUICKSTART in generated
    # The authoring defaults an agent has to know before it writes a cell.
    assert "The four words are `model`" in generated
    assert "Promote later" not in generated
    assert "Always name a cell" in generated
    assert "immutable" in generated


async def test_a_teams_own_instructions_survive_the_generated_block(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    (root / docs.AGENTS_NAME).write_text(
        "# Our house rules\n\nRun the linter before you finish.\n", encoding="utf-8"
    )

    async with daemon_api(root) as api:
        await api.status({})
        first = (root / docs.AGENTS_NAME).read_text("utf-8")
        await api.status({})
        again = (root / docs.AGENTS_NAME).read_text("utf-8")

    assert first.startswith("# Our house rules")
    assert "Run the linter before you finish." in first
    assert docs.BEGIN_MARKER in first and docs.END_MARKER in first
    # Regenerating is idempotent, or every verb would rewrite a watched file.
    assert again == first


async def test_flow_operations_do_not_write_a_checkout_sidecar(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"flow": "churn", "target": "report"})

    assert not (store_dir(flow) / "CHECKOUT.md").exists()


async def test_the_generated_block_never_speaks_the_vocabulary_git_owns(
    tmp_path: Path,
):
    """`AGENTS.md` sits at the root of a git repository. It teaches our words."""
    root = make_workspace(tmp_path / "project", flows=("churn",))

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})

    no_git_words((root / docs.AGENTS_NAME).read_text("utf-8"), "AGENTS.md")
    no_git_words(docs.QUICKSTART, "the quickstart")
    no_git_words(docs.CHEATSHEET, "the cheatsheet")
