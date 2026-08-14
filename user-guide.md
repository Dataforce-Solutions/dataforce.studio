# lumlflow flow runtime — manual test guide

This branch implements the flow runtime from `SPEC.md`: a per-flow daemon with a
content-addressed store and journal, a sandboxed kernel that runs cells inside the
flow's own venv, a `lumlflow` CLI, an MCP server, and a live browser UI wired into
the existing flow concept shell.

## Prerequisites

- `uv` on PATH (the daemon uses it to create each flow's `.venv`).
- Node + npm for the UI.
- Install the CLI so it works from any directory (run from the repo root):

```bash
uv tool install --editable lumlflow/
```

(Alternative without installing: `uv run --project <repo>/lumlflow lumlflow …` from
inside the flow directory.)

## Part 1 — CLI loop on the demo flow

The CLI locates the flow by walking up from the cwd to a `flow.yaml`, so `cd` into
the flow first. Every command accepts `--json`; every mutating command accepts
`--intent/-m "why"` (this shows up in the journal and the UI catch-up panel).

Keep the flow path short — the daemon listens on `<flow>/.lumlflow/daemon.sock`, and
deeply nested paths exceed the ~108-char Unix socket limit, which surfaces as
`Error: daemon did not become ready`.

```bash
lumlflow init ~/flows/demo.flow --demo
cd ~/flows/demo.flow
lumlflow status          # 6 cells (data → features → train → evaluate → plot, + note), all unmaterialized
lumlflow run plot        # first run: executes 5 cells; `note` stays unmaterialized
lumlflow status
lumlflow tree            # journal history
lumlflow graph --around train
```

Things to verify:

- **Partial recompute** — `lumlflow cells params train --set learning_rate=0.1 -m "tune lr"`,
  then `lumlflow run plot`: exactly 3 cells recompute (train, evaluate, plot).
- **Memoization** — set `learning_rate` back to `0.2` and run again: 3 memo hits, 0 executions.
- **Edit/run/fix loop** — break `cells/train.py` (raise an exception), `lumlflow run train`
  fails with the error visible in `lumlflow status`; fix it and run again.
  Scripted version: `python dev/tier0_gate/run.py ~/flows/demo.flow`.
- **Branching** — `lumlflow fork try-lr`, `lumlflow switch try-lr`, change a param, run,
  then `lumlflow diff main try-lr` and `lumlflow adopt train --from try-lr`.
- **Sweep** — `lumlflow sweep train --params '{"learning_rate": 0.05}' --params '{"learning_rate": 0.3}'`
  creates one branch per variant (visible in the UI as a sweep comparison table).
- **Rewind** — `lumlflow preflight --to <step>` shows what a rewind would recompute;
  `lumlflow rewind --to <step>` does it.
- **Assets** — `lumlflow asset preview train.curve`, `lumlflow asset page features.frame --limit 5`.
  (Demo outputs: `data.frame`, `features.frame`, `train.curve`, `evaluate.report`, `plot.chart`.)
- **Scratch eval** — `lumlflow eval "max(curve.values())"` (bare names resolve to branch
  assets; ambiguous names like `frame` list their candidates).
- **Environment** — `lumlflow env add polars`, `lumlflow env status` (note the kernel
  restart banner logic), `lumlflow env remove polars`.

Generated files worth a look: `AGENTS.md` (agent quickstart) and
`.lumlflow/CHECKOUT.md` (branch + staleness summary) in the flow dir — both are kept
current by the daemon.

## Part 2 — Live UI

One-time frontend setup (repo root):

```bash
npm install
npm run build --workspace=extras/js/packages/experiments
npm run build --workspace=extras/js/packages/attachments
```

Then:

```bash
npm run dev --workspace=lumlflow/frontend        # Vite on http://localhost:5173
cd ~/flows/demo.flow && lumlflow daemon start    # prints HTTP URL, token, and a UI deep link
```

Open the printed `UI:` link — it lands on `/flow/railroad?live=…&token=…` and
auto-connects. The link assumes Vite is on port 5173; if that port was taken and Vite
started elsewhere (check its startup output), pass the real URL via
`lumlflow daemon start --ui-url http://localhost:<port>/flow/railroad` (or set
`LUMLFLOW_UI_URL`) — connecting to a different server that happens to sit on 5173
fails with "Cannot reach the daemon". Without the link, open `http://localhost:5173/flow/railroad`, switch the
header select from **Fixtures** to **Live daemon**, and paste the URL + token from
`lumlflow daemon start` (also re-printable via `lumlflow daemon status`). Recent
connections are remembered in a dropdown.

What to test in the live session:

- **Canvas cards** (one per cell): staleness chip with plain-English causes, Run /
  Force run / Cancel, "Running" badge, cache-hit banner on memo hits.
- **Tabs per card**: output previews (tables, metrics, plot images; "Expand rows" pages
  frames from the store), `code` (edit + Save; concurrent-edit conflicts offer "Reload
  latest code"), `logs` (persisted), `console` (live streaming while running).
- **Parameter inspector**: edit `train`'s params as JSON, Save — watch downstream cells
  flip to stale.
- **Sweep…** on a card: pick a param, enter a JSON array like `[0.05, 0.1, 0.3]` —
  variants run serially and a sweep comparison table appears with an "Adopt winner"
  action.
- **Rail (left)**: the journal as a railroad. Click a stop for its transaction detail
  with **Fork from here** and **Rewind here…** (shows a preflight cost estimate before
  confirming). Click another branch's lane head to switch branches. Inline branch rename.
- **Compare branches** (visible with 2+ branches): pick baseline/comparison, see
  per-cell param/definition/output differences, adopt individual cells.
- **Environment panel**: add/remove packages, restart-kernel banner when loaded
  packages changed.
- **Scratch console**: evaluate expressions against the branch (`max(curve.values())`),
  results render as previews.
- **Promote output**: on an output tab, queues publication (upload state chips cycle
  queued → uploading → done).
- **Catch-up panel**: run a few CLI commands with `-m "…"` while the UI is open —
  transactions group by intent/actor and the canvas updates live (SSE; survives daemon
  restarts via cursor resume).

`lumlflow daemon stop` shuts the daemon down.

## Part 3 — Agent surfaces

- `lumlflow agent exec --label agent:test -- lumlflow run train` attributes the child's
  transactions to that agent (check the catch-up panel / `lumlflow tree`).
- `init` wrote `.mcp.json` into the flow dir registering `lumlflow mcp` — open the flow
  dir in Claude Code and the MCP server exposes 11 tools (new-cell, edit-cell, run,
  status, fork, …) plus `flow://manifest` and per-cell resources.

## Automated checks

```bash
cd lumlflow && uv run pytest tests/flow tests/kernel     # backend (daemon, store, kernel)
cd lumlflow/frontend && npm test                          # 50 live-UI tests (vitest)
python dev/tier0_gate/run.py ~/flows/demo.flow            # scripted edit/run/inspect/fix gate
```
