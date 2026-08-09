# Lattice — Product Proposal

*Working title. An agent-controllable, non-linear workspace for data science and ML in the agentic era.*

## The one-liner

The workbench that **any coding agent drives**. Cells produce rich, typed artifacts on a **forkable provenance graph**, so you and your CLI agent of choice can fan out many attempts, compare their outputs side by side, and rewind — with no stale state and no vendor lock-in.

*Lattice is open source. The goal is visibility and adoption, not monetization — success is measured in usage and community, not revenue.*

---

## Thesis: why now

Three shifts have happened at once, and no tool sits at their intersection:

1. **Agents made code cheap to write.** The bottleneck moved from *producing* an attempt to *navigating, comparing, and trusting* the many attempts an agent can now generate in minutes.
2. **DS/ML work is exploratory, visual, and non-linear.** You try twenty things, most die, you keep two. Today that's forced into a linear document (Jupyter, Hex, Deepnote) or a git/PR flow built for software — neither fits exploration.
3. **Coding CLIs are where iteration now lives** and they improve monthly (Claude Code, Codex, Gemini CLI, opencode, and so on). The winning move is to be the *environment they operate in*, not to ship a weaker embedded agent that's always a step behind the frontier.

Lattice is the environment for that intersection: purpose-built for DS/ML, output-first, non-linear, and driven by whatever agent you already use.

---

## The problem with today's tools

| Tool | What it nails | Why it falls short in the agentic era |
|---|---|---|
| **Jupyter** | Ubiquity, interactivity | Hidden state, order-dependent, no provenance, silently stale outputs — fragile the moment an agent iterates fast. |
| **marimo** | Reactivity + reproducibility, git-friendly, and it already lets CLI agents drive it (marimo pair) | It's a *general* Jupyter replacement: linear, code-first, no non-linear exploration graph, no typed artifacts, no notion of experiments as first-class objects. |
| **Hex / Deepnote** | Collaborative, agentic, good viz | Linear documents with an agent *bolted on* — and the agent is embedded and vendor-locked. You can't branch, fan out, and compare. |
| **Cursor / agentic coding CLIs** | Strong autonomous code generation | SWE-shaped: code is the artifact of record, the unit is a multi-file edit or PR, output is terminal text. They don't render dataframes, plots, or experiment runs, and don't model the exploratory, visual DS loop. |

The gap none of them fill: a **non-linear, artifact-first workspace for DS/ML that any external agent can drive.**

---

## What we're building

A workspace for data scientists and ML engineers where:

- **every cell emits a typed artifact** — output-first, code on demand;
- the workspace is a **non-linear provenance graph** you can fork, compare, and rewind;
- state is **reactive and reproducible**, computed lazily so artifacts are never silently stale;
- **experiments are just the richest artifact type**, not a separate module; and
- the tool ships **no agent of its own** — it is controlled by whatever coding CLI you already use, through an open interface.

---

## Design pillars

**1. Artifact-first, not code-first.**
Cells produce typed artifacts (dataframe, plot, model, metric-series, experiment, table, text), each with a rich renderer and diff. Code stays fully inspectable and editable but is collapsed by default. This isn't just a UI preference: in DS/ML the artifact of record is the *finding or the model*, and the code is scaffolding — the opposite of software engineering, where the code ships. Output-first matches what the user actually delivers.

**2. Non-linear and forkable — this is the product.**
The provenance graph is the core, not a feature. Fork from any node, explore a branch, compare artifacts across branches side by side, and rewind to any prior state. When agents make attempts cheap, the "hawk view" over everything that was tried — and the ability to cheaply try more — is the entire reason the tool exists.

**3. Reactive and reproducible, computed lazily.**
Change an upstream cell and everything downstream is marked stale and recomputed on demand — so you get a guarantee that artifacts are never out of sync, without auto-running an expensive training cell you didn't mean to. An explicit pure/impure cell model, input-keyed memoization, and seed pinning handle expensive and non-deterministic steps.

**4. Experiments as a first-class artifact type.**
A training run emits an *experiment artifact*: config, metric curves, checkpoints, and full lineage. The "experiment tracker" is then just the graph view over that one artifact type — no bolt-on W&B-style module, and strictly richer because it carries the exact code and data that produced it.

**5. Bring-your-own-agent.**
No embedded chatbot. Any coding CLI drives the workspace through an open control interface, generalizing the marimo-pair idea into the whole product. The moat is the *environment* — reactive kernel, provenance graph, typed artifacts — not the model.

---

## Key features

- **Typed artifact system** — dataframe, plot/figure, model, metric-series, experiment/run, table, text; each with its own renderer and diff view. Extensible via a plugin model.
- **Provenance graph UI** — every cell, artifact, and run is a node with full lineage; fork from any node, compare artifacts across branches, time-travel to any prior state.
- **2D checkpointing (code + data)** — forks capture kernel/data state, not just code, so a branch is actually runnable from where it split. Content-addressed / copy-on-write storage keeps forking cheap.
- **Lazy reactive kernel** — upstream change marks downstream stale; recompute on demand. No stale artifacts, no accidental execution of expensive cells.
- **Experiment view** — sweeps and runs as sortable, comparable artifacts, each traceable back to the exact code and data that produced it.
- **Open agent-control interface** — an MCP/skills/ACP-style protocol so any CLI can read the graph, inspect live variables and dataframes, add/edit/run cells, create branches, and compare artifacts. Harness- and model-agnostic.
- **Shared human + agent canvas** — the graph is the shared context: you steer, the agent executes, and every agent action is a node you can inspect, diff, and undo.

---

## How it's different — at a glance

| Capability | Jupyter | marimo | Hex / Deepnote | Cursor / coding CLIs | **Lattice** |
|---|:---:|:---:|:---:|:---:|:---:|
| No stale state (reactive) | ❌ | ✅ | ⚠️ | n/a | ✅ |
| Reproducible | ❌ | ✅ | ⚠️ | via code | ✅ |
| Non-linear branch / compare / rewind | ❌ | ❌ | ❌ | code-only (git) | ✅ |
| Rich typed artifacts (df / plot / model) | ⚠️ untyped | ⚠️ untyped | ✅ viz | ❌ text | ✅ |
| Experiments as first-class objects | ❌ | ❌ | ⚠️ | ❌ | ✅ |
| Output-first (code de-emphasized) | ❌ | ❌ | ⚠️ | ❌ | ✅ |
| Purpose-built for DS/ML exploration | ⚠️ | general | ✅ | ❌ SWE | ✅ |
| Driven by any external coding CLI | ❌ | ✅ | ❌ | *is* the CLI | ✅ |
| No embedded / vendor-locked agent | ✅ | optional | ❌ | ❌ | ✅ *(by design)* |

The defensible position is the bottom half of the table read together: **non-linear + typed artifacts + experiments + BYO-agent, shaped for DS/ML.** Any single row can be copied; the combination is the product.

---

## Relationship to marimo

marimo is the closest thing to a substrate for what we're building, and we should be upfront that there is real overlap. marimo already delivers reactive execution with no stale state, reproducibility, git-friendly pure-Python notebooks, and — via marimo pair — the ability for an external coding CLI to drive a live session. We embrace those ideas rather than compete with them; some may even be reused under the hood.

But those overlapping capabilities are **table stakes, not our wedge.** "Reactive, reproducible notebook" is a race marimo already leads, and re-running it would be wasted effort. Our differentiation is everything marimo does *not* have:

- **A non-linear provenance graph.** marimo is linear. It has no branch / fan-out / compare / rewind over a tree of attempts — the single capability that matters most once an agent makes attempts cheap.
- **Typed, first-class artifacts with rich renderers.** marimo is code-first and its outputs are untyped cell outputs. We make the *output* the object: dataframe, plot, model, metric-series, experiment — each rendered, diffable, and addressable.
- **Experiments as first-class objects.** marimo has no native notion of an experiment or run carrying config, curves, checkpoints, and lineage. For us that's the richest artifact type and the built-in tracker.
- **A workflow shaped for DS/ML exploration.** marimo is a general Jupyter replacement; we are purpose-built around the fan-out-and-compare loop of ML experimentation and evaluation.
- **Agent-driven and graph-centric by design.** marimo pair is a feature on a notebook; for us, an external agent operating over a non-linear graph *is* the entire product.

In short: where we overlap with marimo, that's the substrate — and the substrate is not what we're selling. Where we differ is the whole wedge. The overlap is actually reassuring: it validates the substrate, lets us reuse rather than rebuild, and frees our effort for the layer above it.

---

## Why bring-your-own-agent is the right architecture

- **Rides the frontier instead of fighting it.** Coding CLIs improve monthly; bundling your own agent means permanently trailing the best one.
- **Model- and vendor-agnostic.** The user brings the CLI and model they already pay for — no lock-in, no per-seat model markup.
- **Positions Lattice as infrastructure, not another chatbot.** The moat is the environment, which is hard to replicate and improves as agents improve.
- **Sidesteps the losing fight.** You never have to be better at code generation than Cursor or Claude Code. Instead, you make *every* agent better at DS/ML by giving it a real workbench, memory, and map.

---

## Target user and initial wedge

- **Primary user:** ML engineers and data scientists already using a coding CLI, whose core loop is *fan out and compare* — experiment sweeps, eval loops, prompt and feature iteration.
- **Beachhead:** ML experimentation and evaluation, where "run 30 variants, compare the outputs, keep the winner, trace exactly why it won" is the daily loop and current tooling is at its weakest.
- **Expansion:** broader exploratory DS and analytics once the graph + artifact model is proven.

Start narrow. "Better notebook" is a brutal, incumbent-heavy market; "the branch-and-compare workbench for agent-driven ML experiments" is a wedge.

---

## Build vs. reuse: one clean package

Much of what Lattice needs already exists — in research prototypes and open-source projects — just scattered across separate tools that don't talk to each other. Reactive execution, code-plus-data checkpointing, artifact rendering, and experiment tracking have all been built before in some form. Lattice's contribution is **not to reinvent each of these**; it's to bring them together into a single, coherent, easy-to-install package with the exploration graph and bring-your-own-agent model at the center, and a level of polish and day-one usability that the scattered pieces lack on their own.

Concretely:

- **Reuse mature open source under the hood wherever it makes sense.** A reactive kernel, storage and checkpointing, rendering, and tracking components can be adopted or adapted rather than rebuilt — so effort concentrates on the parts that are genuinely new: the provenance graph, the typed-artifact system, and the agent-control interface.
- **The value is integration and experience, not novelty of every component.** "Install once and start" — one package, one workflow, one graph that ties the reused pieces into a single mental model — is itself the product.

**This proposal is deliberately about the *what* and the *why*, not the *how*.** Exact technical implementation — which components to reuse, build, or fork, and how they fit together — is out of scope here and will be worked out separately.

---

## Key technical challenges (stated honestly)

1. **Cheap forking of code *and* data state.** Branching code is trivial; branching multi-GB dataframes, kernel state, or model weights is not. Needs content-addressed / copy-on-write storage and a real story for large artifacts, or the "try many things" promise collapses under memory cost.
2. **Reactivity vs. expensive, non-deterministic cells.** A pure/impure cell model, input-keyed memoization, and seed pinning are required — and "reproducible" has honest limits under LLM sampling and GPU non-determinism that the product must surface, not hide.
3. **Security.** External agent + live code execution + data access is precisely the configuration behind recent real-world agent exploitation. Sandboxing, permissions, and network posture are v1 concerns, not v2.
4. **The typed-artifact + renderer system is real surface area.** It needs an extensible plugin model from the start so the artifact vocabulary can grow without core changes.

---

## What makes this win — or kills it

- **Wins if** the branch → compare → rewind loop is genuinely faster than spinning up N separate notebooks, *and* the CLI-control interface works frictionlessly with the top two or three agents on day one.
- **Dies if** it drifts into being "another notebook" (losing the non-linear thesis), or if forking is too slow or expensive to actually use at the scale the pitch promises.

---

## Summary

Lattice is not a better Jupyter and not another agentic notebook. It is the **non-linear, artifact-first workbench for DS/ML that external coding agents drive** — taking the one thing marimo proved (a reactive substrate an agent can operate in) and building the exploration graph, typed artifacts, and experiment tracking that the exploratory, visual, fast-iterating reality of ML actually needs, without shipping an agent of its own.
