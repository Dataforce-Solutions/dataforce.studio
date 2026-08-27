# Proposals

## Problem

How monitoring works today. A model is packaged by the SDK into a `.luml` artifact and
uploaded to the platform. A satellite is a separate service that hosts deployments of such
artifacts. At startup it registers with the platform ("pairs") and tells it what it can do.
The platform never calls the satellite; users, the UI and the SDK call it directly. When a
deployment has live monitoring on, the satellite serves a monitoring API and a dashboard for
it. Drift metrics need a reference profile, a summary of the training data that the SDK can
embed into the artifact.

The PoC works end to end, but four things around it are missing or hard-wired.

**The satellite guesses what kind of model it hosts.** It infers "tabular model" or "LLM app"
from the artifact's format and framework name. The guess is wrong for XGBoost, LightGBM and
CatBoost models, which get treated as LLM apps and lose every drift view. There is also no
tag saying "this artifact has a reference profile", so nothing can rely on it, and there is
no way to add a profile after packaging.

**The platform hard-codes what a satellite may say about itself.** Capabilities are a fixed
list of two names. A satellite that reports a name outside that list cannot pair at all. The
version number it reports is ignored. Nothing stops an API call from turning monitoring on
for a satellite that cannot monitor. And a satellite claims monitoring even when its
monitoring is switched off in configuration.

**Nobody can tell what monitoring a deployment will actually get.** The platform only knows
"on" or "off". Which metrics exist is decided on the satellite from the artifact's contents,
and never reported back. The create form therefore shows the same "Live monitoring" toggle
for a model with full drift monitoring and for one that will only get request logs.

**The SDK only works with our satellite, and only today's version.** Each monitoring method
builds the URL from a hard-coded path. It cannot call an endpoint the satellite adds, and it
has no way to know which version of the satellite it is talking to. This blocks two goals:
anything the UI can do, the SDK (and so an agent) must be able to do; and satellites are
meant to be plugins, so other versions and third-party satellites with their own endpoints
will exist.

## Solution

Instead of guessing, each party states the facts about itself once, and the platform keeps
those statements. The UI and the SDK read them from the platform, never from the satellite.

| Who | States what | When |
| --- | --- | --- |
| The artifact | its model kind, and whether it carries a reference profile | at packaging, as tags in the manifest |
| The satellite | which capabilities it has, at which versions, and a description of its endpoints | at pair |
| The deployment | where its monitoring API lives, if it is running | reported by the satellite when it starts the deployment |

The platform validates these statements, refuses deployments that ask for something the
satellite did not state, and shows the UI what a deployment will get. The SDK gets two
things: a generic way to call any endpoint a satellite describes, and monitoring methods that
adapt to the satellite's version.

## Why this approach

**The platform is the single source of truth.** The platform cannot reach satellites, so it
cannot ask them questions; only clients can. If a client asked the satellite directly, it
could get an answer that differs from what the UI shows, and the user would not know which
to believe. A satellite's capabilities do not change while it runs, and every restart pairs
again, so the platform's copy is always current.

**Facts about the artifact go into manifest tags.** The manifest format belongs to an
external library (fnnx), and the platform drops fields it does not know. Tags are the
manifest's extension point. They are already stored on the platform and already read by the
create form and by the satellite.

**Endpoints are described with OpenAPI.** The satellite already generates an OpenAPI
document for its routes. Sending that document to the platform gives agents endpoint
descriptions and request shapes without inventing a format.

**Each capability has two version numbers.** One for the shape of its declaration, one for
the endpoints behind it. They change for different reasons; a single number would force the
SDK to break every time the declaration gained a field.

**Nothing beyond that.** No endpoint to re-announce capabilities (a restart does it). No
version number on the whole pair message (the `/satellites/v1` URL is the last-resort break).
No per-vendor namespaces (one `custom.` prefix). No live endpoint description (routes are
static; per-deployment state goes on the deployment record).

# Design

## Artifact tags

An artifact's manifest carries a list of producer tags, strings such as
`luml.ai::sklearn:v1` that the SDK stamps at packaging. Two new facts are added as tags: the
model kind, and whether a reference profile is embedded.

| Tag | Who stamps it | Meaning |
| --- | --- | --- |
| `luml.ai::kind_tabular:v1` | sklearn, xgboost, lightgbm, catboost packagers, always | classic tabular model |
| `luml.ai::kind_llm:v1` | langgraph packager, always | LLM application |
| `luml.ai::tabular_monitoring:v1` | a tabular packager, only when it embedded a reference profile | drift and data-quality monitoring are possible; `v1` is the version of the profile format |
| `luml.ai::llm_monitoring:v1` | nobody yet; reserved | LLM observability, once packaging-time instrumentation exists |

Tags are always written in full with the `luml.ai::` prefix (`FNNX_PRODUCER_NAME + "::"`).
The monitoring tag replaces today's `reference_profile:v1` tag. Nothing has shipped, so the
old tag needs no support.

The monitoring tag means "monitoring is possible", not "every metric is on". As today, the
satellite still looks into the profile to see which metrics it can compute. A kind tag alone
enables no drift metric.

A profile can also be added after packaging. `ModelReference` gains a public operation that
builds a profile from reference data and embeds it into a local `.luml` file, adding the
monitoring tag (and the tabular kind tag if the artifact has no kind tag). It refuses LLM
artifacts. Uploaded artifacts cannot be modified, so for an uploaded model the flow is
download, embed, upload as a new artifact.

*Note: only the sklearn packager can build a profile today. Giving the other tabular packagers
a `reference_data` argument is wanted but out of scope here; they stamp the kind tag only.*

## Satellite capability document

When a satellite pairs (`POST /satellites/v1/pair`) it sends a `capabilities` object: one
entry per thing it can do. Today there are two, `deploy` and `monitoring`. This is what
today's satellite would send after this change:

```json
{
  "deploy": {
    "version": 1,
    "api_versions": [1],
    "facets": ["satellite", "deployment"],
    "supported_variants": ["..."],
    "supported_tags_combinations": [["..."]],
    "extra_fields_form_spec": []
  },
  "monitoring": {
    "version": 1,
    "api_versions": [1],
    "facets": ["deployment:monitoring"],
    "features": ["runtime", "traces", "alerts", "data_quality", "feature_drift", "output_drift", "multivariate_drift"]
  }
}
```

The fields specific to `deploy` are unchanged. `features` on `monitoring` is new: it lists
the monitoring sections this satellite can serve. `runtime`, `traces` and `alerts` are always
there; the drift and data-quality sections appear only if the satellite has those metrics.

Three fields are common to every capability:

`version` is the version of the declaration's shape. The platform uses it to pick the
validation model. Adding an optional field does not bump it.

`api_versions` lists the versions of the endpoint contract behind the capability: which paths
exist, what they accept, what they return. It is a list so a satellite can keep serving an
old contract while introducing a new one. The SDK uses it to pick how to talk to the
satellite.

`facets` lists the endpoint groups this capability owns. Facets are explained in the next
section.

Only `version` must be sent. For `deploy` and `monitoring`, the platform fills in the rest at
pair (`api_versions` to `[1]`, `facets` to the lists shown above, `features` to all sections)
and stores the filled-in document. So `{"version": 1}` is a complete declaration, and the UI
and the SDK never have to know the defaults.

The satellite builds this document from what it actually runs. If monitoring is switched off
in its configuration, `monitoring` is simply not in the document. The document can only
change by restarting the satellite, which pairs again and replaces the stored document.

### Capability names

`deploy` and `monitoring` are reserved names. Declaring one is a promise to implement our
contract at the declared versions.

Any other capability must be named `custom.<name>`, with `<name>` matching `[a-z0-9_]+`, for
example `custom.gpu_monitoring`. The platform checks only the three common fields on a custom
capability and stores it as sent. It is never dropped, because the SDK's generic layer lets
agents use it.

A name that is neither reserved nor `custom.`-prefixed is treated as a typo. The pairing is
rejected with 422 naming it.

### When a capability counts as present

The platform can only work with versions it knows. It keeps, per reserved capability, the
declaration versions it can validate and the API versions it can use; today `{1}` and `{1}`
for both. A reserved capability counts as present only if its `version` is known and at least
one of its `api_versions` is known.

If a satellite declares `monitoring` at a version the platform does not know, the pairing
still succeeds and the document is stored, but `monitoring` counts as absent. The monitoring
page then shows the reason `capability_version_unsupported` rather than
`capability_missing`.

To save every reader from redoing this check, the satellite read and list responses include
a computed `present_capabilities` list. The UI and the SDK use that list only.

### Rejected pairings

The pairing is rejected with 422, naming the offending capability or facet, when:

- a capability name is neither reserved nor `custom.`-prefixed
- a reserved declaration does not match its typed model
- a facet id uses an unknown level, or a custom capability claims a reserved facet
- the `openapi` document (next section) is not a JSON object, or is larger than 2 MB

Not rejected: a reserved declaration at a version newer than the platform knows (stored,
counts as absent), and unknown fields inside a known declaration (ignored). The existing
database rule that a paired satellite has non-empty capabilities stays. The `/satellites/v1`
prefix stays and is reserved for changes that break the whole pairing protocol.

### Monitoring mode

A deployment's `monitoring_mode` is the platform's request, not a description of what runs.
Today it has two values. `off` means the satellite does no monitoring for this deployment.
`full` means "everything available": every section in the satellite's `features` that the
artifact's tags and profile allow. What a `full` deployment actually gets can therefore differ
between satellites and artifacts, and that is by design. Any future mode is a narrower request
than `full`. Every rule below that says "monitoring is requested" means `monitoring_mode` is
not `off`, so a new mode inherits the rules unless it says otherwise.

### Enforcement on deployment create and update

Today only the browser form checks the satellite's capabilities. The platform handlers now
check them too, so the API cannot bypass them:

- create: the satellite has `deploy`; the artifact's variant is in `supported_variants`; if
  `supported_tags_combinations` is declared, the artifact's tags contain one of them
- create with monitoring requested: the satellite has `monitoring`
- update that changes `monitoring_mode` to a value other than `off`: the deployment's current
  satellite has `monitoring` (a deployment never moves between satellites)

Every refusal answers 409 naming the reason, like the existing "monitoring not enabled"
refusal.

## Facets

A satellite exposes endpoints at two levels: some are about the satellite itself (health),
others are about one deployment it hosts (compute, that deployment's monitoring). The level
is decided by what the endpoint is about, not by whether the deployment id appears in the
path. A facet is a named group of endpoints at one level. Today there are three:

| Facet | Level | Endpoints |
| --- | --- | --- |
| `satellite` | satellite | health, the unauthenticated inference-access check |
| `deployment` | deployment | list, compute |
| `deployment:monitoring` | deployment | the monitoring API for one deployment |

Facets describe the machine surface only. The browser dashboard (launch, session, the
cookie-authenticated `/monitoring/api/*`) is opened by the platform and has no facet; agents
use the monitoring API for the same data.

`deploy` owns the first two facets, `monitoring` the third. The id is `<level>` or
`<level>:<name>`; a bare level id is that level's base group. The levels are `satellite` and
`deployment`; a new resource type would add a level. Nothing at the satellite level exists
beyond the base group today; a cross-deployment monitoring view would be `satellite:monitoring`.

A custom capability names its facets `<level>:custom.<name>`, for example
`deployment:custom.gpu`. Its routes should live under `/<resource>/{id}/custom/<name>/…` (or
`/custom/<name>/…` at satellite level) so they cannot collide with ours. Nobody derives a
path from a facet name; paths come from the OpenAPI document.

Facets matter in two places: each operation in the OpenAPI document is tagged with its facet,
and the SDK lists operations by facet.

## OpenAPI pushed at pair

Besides `capabilities`, the pair message gains an optional `openapi` field: the satellite's
OpenAPI document. This is how the platform, and through it agents, learn which endpoints a
satellite has and what they accept.

The document is the static one: the routes the build serves, with path templates such as
`/deployments/{deployment_id}/monitoring/overview`. It does not contain the per-deployment
input and output schemas that the satellite's live `/openapi.json` merges in; those already
reach the platform on the deployment record.

The satellite prepares the document so that:

- every machine operation has exactly one facet tag, a summary and a description; the
  dashboard routes have no facet tag and are not pushed
- each operation states its real authentication: bearer key everywhere except the
  inference-access check, which has none (today every path is marked bearer)
- only operations of capabilities in the document are included; with monitoring switched
  off, no `deployment:monitoring` operation appears even if the route exists in the process

The platform stores the document as-is on the satellite record and checks only that it is a
JSON object of at most 2 MB. A dedicated endpoint on the orbit satellites API returns it; it
is not included in the satellite list or read responses. An older satellite that sends no
`openapi` stores none. A re-pair without it clears the previously stored one, and the SDK
then reports that no description is available.

The satellite's own `/openapi.json`, `/docs` and `/redoc` start requiring the bearer key.
They are for debugging only. Today they are public and list every hosted deployment id with
its schemas.

## `monitoring_url` on the deployment record

Today the satellite reports `inference_url` on the deployment record once the deployment is
up. It now also reports `monitoring_url`: the root of that deployment's monitoring API, or
null if there is none. The URL is relative to the satellite's `base_url` (absolute is
allowed).

The satellite sets it whenever it brings a deployment up with monitoring running: after a
deploy, after a reconcile, and when it re-attaches active deployments at startup. It sets it
back to null on reconcile when monitoring is turned off. It is only ever set when the
satellite declares `monitoring` and monitoring is requested for the deployment; otherwise,
including monitoring switched off in the satellite's configuration, it stays null. The field
appears on the platform deployment schemas and on the SDK `Deployment` type.

For this to work, the satellite's deployment update call becomes a partial update: fields
that are not sent stay as they are, an explicit null clears. A restarted satellite can then
report `monitoring_url` without touching `inference_url` or `status`.

The SDK calls the URL the record reports instead of building one from `base_url` and a
hard-coded path. If a deployment's monitoring is ever served from somewhere other than the
satellite, only the reported URL changes.

## Model kind and metric gating on the satellite

The satellite reads the model kind from the kind tag in the artifact's manifest:
`tabular`, `llm`, or `unknown` when there is no kind tag. The current guessing code is
removed. Where the dashboard header or the stored descriptor defaults to `ml` today, the
default becomes `unknown`, and `ml` is renamed to `tabular`.

Drift and data-quality metrics (data quality, feature drift, multivariate drift, output
drift, the reference-profile view) are computed only when the manifest carries a
`luml.ai::tabular_monitoring:v<N>` tag whose version the satellite can read, and the loaded
profile contains what each metric needs (the existing per-metric conditions). Runtime
health, traces and alerts are always available.

The satellite reports the profile's state as `profile_status` with one set of values
everywhere (worker results, header, section responses): `ready`, `placeholder`, `absent` (no
profile, or a profile file without the tag), `unsupported` (a tag version the satellite
cannot read). Today the query schemas know only the first two.

The dashboard shows all tabs for `tabular` and only the universal tabs (Overview, Runtime,
Traces, Alerts) for `llm` and `unknown`. The wording for `unknown` must not call the
deployment an LLM.

## Platform UI

The deployment create and edit forms use `present_capabilities`. Satellites without `deploy`
are filtered out or disabled. The monitoring toggle is enabled only when `monitoring` is
present; the existing behavior for a saved deployment whose satellite lost the capability
(keep it on, show a warning) stays.

Next to the toggle, an informational hint lists the monitoring sections the deployment will
get: `runtime`, `traces` and `alerts` always, plus the drift and data-quality sections from
the satellite's `features` when the artifact carries a supported
`luml.ai::tabular_monitoring` tag. A tabular artifact without that tag gets a pointer to
repack with reference data.

The monitoring page shows the new `capability_version_unsupported` reason. The frontend's
TypeScript interfaces for capabilities are updated by hand to match the backend models.

## SDK

The SDK follows one rule: decide from the platform, execute against the satellite. It never
asks a satellite what it can do.

### Generic layer: call any endpoint of any satellite

`client.satellites` reads the satellite record from the platform (`base_url`,
`capabilities`, `present_capabilities`) and fetches the stored OpenAPI document when asked.

```python
sat = client.satellites.get(satellite_id)
sat.operations(facet="deployment:monitoring")   # method, path template, summary, params, security
sat.request("GET", f"/deployments/{dep_id}/custom/gpu/usage")
```

`operations()` is what an agent reads to decide what to call. `request()` makes one call with
the user's bearer key and returns the parsed JSON as-is. It accepts a relative path, or an
absolute URL on the same origin as `base_url`; any other origin raises before anything is
sent, so the key cannot leak to a foreign host. HTTP errors map to the SDK's existing
status-error classes.

### Native layer: the monitoring methods

`client.deployments.monitoring(...)` and its async twin keep working. Internally there is one
implementation per monitoring API version. The SDK picks the highest version that both it
and the satellite's `api_versions` support. Today only version 1 exists; adding a version
must not modify existing implementations.

Requests go to the deployment's `monitoring_url` plus the section path. The SDK no longer
validates query dimensions such as `window` or `sort` itself; it forwards every keyword
argument and lets the satellite validate. A newer satellite that accepts more values is
usable without an SDK release.

Before sending, the SDK checks the platform records it already has:

| Condition | Error |
| --- | --- |
| `monitoring` not in the satellite's `present_capabilities` | `CapabilityNotSupportedError` |
| no API version in common | `UnsupportedCapabilityVersionError`, naming both sides |
| the deployment's `monitoring_url` is null | `CapabilityNotSupportedError`, saying monitoring is off or not yet reported |
| the method does not exist in the selected version | `NotAvailableInVersionError`, naming the version that has it |

After receiving, each method checks that the response has the top-level structure its
version requires (extra fields pass through). A mismatch raises `ContractViolationError`
naming the satellite and operation. Two 404 codes from the satellite are interpreted:
`unknown_route` on a native path raises `SatelliteOutOfSyncError` ("restart or re-pair the
satellite"), and `deployment_not_hosted` keeps its current meaning. A 404 without a known
code, such as a trace missing from the window, stays `NotFoundError`. All new errors derive
from the SDK's base error.

### Contract test

One snapshot of the satellite's full static OpenAPI document (monitoring on, before facet
filtering) is committed. An SDK test asserts that every native method's path and query
parameters exist in it. A satellite test asserts that the generated document equals it. If
either side drifts, CI fails.

## Satellite API hygiene

404 responses gain a machine-readable `code` next to the message: `deployment_not_hosted`
when the satellite does not serve that deployment, `unknown_route` for any path that matches
nothing (except under the dashboard's static files). Other 404s keep their plain message.
Every operation gets a summary and a description. The OpenAPI and docs routes require the
bearer key.

## Out of scope

- `reference_data` in the xgboost, lightgbm and catboost packagers
- stamping `luml.ai::llm_monitoring:v1` and LLM packaging-time instrumentation
- an endpoint to re-announce capabilities without a restart
- a conformance suite for third-party satellites (the contract test is its seed)
- wiring or deleting the unused `extra_fields_form_spec` generator
- realized performance and targets (deferred 2026-08-25)
- generating frontend types from backend models

## Trade-offs

Storing an OpenAPI document per satellite costs a few hundred kilobytes of JSONB and one
read endpoint. In return agents have a single place to look, and the platform never calls a
satellite.

Rejecting unknown capability names blocks pairing on a typo. That is better than silently
treating a misspelled `monitoring` as a custom capability.

Removing the SDK's own query validation turns some immediate local errors into a round-trip
that ends in a 422. In return the SDK never lags behind the satellite on accepted values.

Without the old "profile present means monitoring" fallback, an artifact packed before this
change with a profile but no tag gets only runtime, traces and alerts until repacked.
Nothing has shipped, so nobody is affected.

# Scenarios

## Scenario: sklearn packaging with reference data stamps both tags
**Given** an sklearn estimator packaged with `reference_data`
**When** the artifact is saved
**Then** its manifest producer tags include `luml.ai::kind_tabular:v1` and
`luml.ai::tabular_monitoring:v1`, and `reference_profile.json` sits at the bundle root

## Scenario: sklearn packaging without reference data stamps the kind only
**Given** an sklearn estimator packaged without `reference_data`
**When** the artifact is saved
**Then** the tags include `luml.ai::kind_tabular:v1` and no `luml.ai::tabular_monitoring` tag, and the
old `reference_profile:v1` tag is absent

## Scenario: other packagers stamp their kind
**Given** a native XGBoost, LightGBM or CatBoost model, and a LangGraph app
**When** each is packaged
**Then** the tabular ones carry `luml.ai::kind_tabular:v1` and the LangGraph one carries
`luml.ai::kind_llm:v1`; none carries a monitoring tag

## Scenario: post-hoc profile embedding on a local artifact
**Given** a saved tabular `.luml` file without a profile
**When** the profile is added through the public `ModelReference` operation with reference data
**Then** the bundle contains `reference_profile.json` at its root, the bundled manifest gains
`luml.ai::tabular_monitoring:v1`, repeating the operation replaces the profile without
duplicating the tag, and the artifact still validates

## Scenario: post-hoc embedding refuses an LLM artifact
**Given** a `.luml` file tagged `luml.ai::kind_llm:v1`
**When** the profile operation is called
**Then** it fails with a clear error and the bundle is unchanged

## Scenario: model kind from tags only
**Given** three deployed artifacts: one tagged `luml.ai::kind_tabular:v1`, one tagged `luml.ai::kind_llm:v1`, one
with no kind tag but a `pyfunc` variant and a usable profile file
**When** the dashboard header is requested for each
**Then** `model_kind` is `tabular`, `llm` and `unknown` respectively

## Scenario: profile without tag enables nothing
**Given** a deployment whose bundle has a usable `reference_profile.json` but no
`luml.ai::tabular_monitoring` tag
**When** the worker computes a window
**Then** only runtime health runs, drift and data-quality sections report their empty state,
and `profile_status` is `absent`

## Scenario: tagged profile enables the profile-dependent metrics
**Given** a deployment tagged `luml.ai::kind_tabular:v1` and `luml.ai::tabular_monitoring:v1` with a ready profile
**When** the worker computes a window
**Then** data quality, feature drift, multivariate drift and output drift apply according to
the profile parts present, exactly as today

## Scenario: unsupported profile tag version
**Given** a deployment tagged `luml.ai::tabular_monitoring:v9` on a satellite that reads `v1` only
**When** the header and sections are requested
**Then** the profile-dependent sections are empty and `profile_status` is `unsupported` on
the header and on every response that carries `profile_status`

## Scenario: dashboard tabs for unknown kind
**Given** a deployment with `model_kind: unknown`
**When** the dashboard loads (including with a restored tab setting pointing at a hidden tab)
**Then** only Overview, Runtime, Traces and Alerts are shown, the active tab collapses to
Overview, and no text calls the deployment an LLM

## Scenario: satellite advertises an honest monitoring capability
**Given** an agent started with monitoring enabled
**When** it pairs
**Then** the stored capability document has `monitoring` with `version 1`, `api_versions
[1]`, the two monitoring facets and a `features` list of the universal sections plus the
registered profile-dependent metrics; and the stored OpenAPI document, read through its
endpoint, has every operation tagged with a facet id

## Scenario: satellite with monitoring disabled does not advertise it
**Given** an agent started with monitoring disabled by configuration
**When** it pairs
**Then** the stored document has `deploy` only, the satellite payload's
`present_capabilities` lacks `monitoring` so the deployment form (which reads that list)
hides the toggle for that satellite, and monitoring eligibility reports `capability_missing`

## Scenario: monitoring disabled: pushed spec has no monitoring facets
**Given** an agent started with monitoring disabled by configuration
**When** it pairs
**Then** the pushed `openapi` document contains no operation tagged `deployment:monitoring`,
while the `satellite` and `deployment` operations are present

## Scenario: bare declaration still validates
**Given** a pair request whose `monitoring` is `{"version": 1}` and whose `deploy` matches
the current shape
**When** it is received
**Then** pairing succeeds, `present_capabilities` includes `monitoring`, and the stored
document read back from the satellite payload carries `monitoring` with `api_versions [1]`,
`facets ["deployment:monitoring"]` and all `features` explicitly

## Scenario: custom capability is stored
**Given** a pair request with `custom.gpu_monitoring` `{version: 1, api_versions: [1],
facets: ["deployment:custom.gpu_monitoring"]}`
**When** it is received
**Then** pairing succeeds, the declaration is stored verbatim, and it is visible on the
satellite read payload

## Scenario: custom capability claiming a reserved facet rejects pairing
**Given** a pair request with `custom.gpu_monitoring` whose `facets` include
`deployment:monitoring`, or a facet id shaped `deployment:gpu` (name not `custom.`-prefixed),
or a facet id at an undefined level such as `cluster:custom.gpu_monitoring`
**When** it is received
**Then** the platform answers 422 naming the offending facet and the satellite record is
unchanged

## Scenario: unknown unprefixed capability rejects pairing
**Given** a pair request containing `monitorng` (typo) or `gpu_monitoring` (unprefixed)
**When** it is received
**Then** the platform answers 422 naming the offending capability and the satellite record
is unchanged

## Scenario: unsupported declaration or API version counts as absent
**Given** a pair request with `monitoring` `{version: 7}` or `{version: 1, api_versions: [3]}`
**When** it is received and a `full`-mode deployment on that satellite asks for eligibility
**Then** pairing succeeds (the `{version: 7}` declaration is checked against the generic
envelope only), the document is stored, `present_capabilities` omits `monitoring` so the
deployment form hides the toggle, eligibility is false with reason
`capability_version_unsupported`, and the monitoring page renders that reason

## Scenario: unknown fields in a known declaration are ignored
**Given** a pair request whose `monitoring` carries an extra field the platform does not know
**When** it is received
**Then** pairing succeeds and the capability counts as present

## Scenario: pair without an OpenAPI document
**Given** an older agent that sends no `openapi`, or a satellite that stored one earlier and
re-pairs without it
**When** it pairs and the SDK later asks for its operations
**Then** pairing succeeds, the read endpoint reports no document (any earlier one is
cleared), and `operations()` raises a clear "no description available" error rather than an
empty list

## Scenario: deployment create enforces the capability
**Given** a satellite without a present `monitoring` capability
**When** a deployment with `monitoring_mode: full` is created on it, or an existing deployment
on it is updated to `full`, via the API
**Then** the request fails with 409 naming the missing capability, and nothing is persisted
or enqueued

## Scenario: deployment create requires the deploy capability
**Given** a satellite whose `deploy` capability is absent or not present (unsupported
declaration or API version)
**When** a deployment is created on it via the API
**Then** the request fails with 409 naming `deploy`, and nothing is persisted or enqueued

## Scenario: deployment create enforces the variant and tag combinations
**Given** a satellite whose `deploy` declaration's `supported_variants` excludes the
artifact's manifest variant, or whose `supported_tags_combinations` has no combination
contained in the artifact's producer tags
**When** a deployment is created on it via the API
**Then** the request fails with 409 naming the failed check

## Scenario: satellite reports monitoring_url
**Given** a deployment created with `monitoring_mode: full` on a monitoring satellite
**When** the deploy task finishes
**Then** the deployment record carries `monitoring_url` pointing at that deployment's
monitoring facet, relative to the satellite `base_url`, alongside `inference_url`

## Scenario: monitoring-disabled agent reports no monitoring_url
**Given** a deployment record with `monitoring_mode: full`, created while its satellite still
advertised `monitoring`, whose agent now runs with monitoring disabled by configuration
**When** the deploy task finishes or the startup sync attaches the deployment
**Then** `inference_url` is reported and `monitoring_url` stays null

## Scenario: turning monitoring off clears monitoring_url
**Given** an active deployment with a `monitoring_url`
**When** `monitoring_mode` is set to `off` and the reconcile task completes
**Then** `monitoring_url` is null; setting it back to `full` and reconciling restores it

## Scenario: satellite restart re-reports monitoring_url for active deployments
**Given** an active deployment with `monitoring_mode: full` whose record lacks
`monitoring_url` (reported by an older agent)
**When** the satellite restarts and its startup sync attaches the deployment
**Then** the record carries `monitoring_url`, and `inference_url` and `status` are unchanged

## Scenario: partial deployment update from the satellite
**Given** an active deployment with an `inference_url` and status `active`
**When** the satellite sends a deployment update carrying only `monitoring_url`
**Then** `monitoring_url` is stored and `inference_url` and `status` are intact

## Scenario: create form hint
**Given** the deployment create form with a monitoring satellite selected
**When** the chosen artifact is tagged `luml.ai::kind_tabular:v1` + `luml.ai::tabular_monitoring:v1`, then
`luml.ai::kind_tabular:v1` only, then `luml.ai::kind_llm:v1`, then untagged
**Then** the hint lists the universal sections plus every profile-dependent section in the
satellite's `features`, runtime/traces/alerts only with a repack pointer,
runtime/traces/alerts, and runtime/traces/alerts only, respectively; the toggle is enabled in
all four cases. With the first artifact and a satellite whose `features` omits
`output_drift`, the hint lists data quality, feature drift and multivariate drift but not
output drift

## Scenario: SDK selects the highest common API version
**Given** an SDK knowing monitoring API versions {1, 2} and a satellite advertising
`api_versions [1, 2, 3]`
**When** a native monitoring method is called
**Then** the version-2 implementation is used

## Scenario: SDK has no common API version
**Given** an SDK knowing {1} and a satellite advertising `[3]`
**When** a native monitoring method is called
**Then** `UnsupportedCapabilityVersionError` is raised naming both sides, and `request()`
against the same satellite still works

## Scenario: SDK pre-flight on a satellite without monitoring
**Given** a deployment on a satellite whose `present_capabilities` lacks `monitoring` — the
declaration is missing, or stored at a version the platform does not support
**When** any native monitoring method is called
**Then** `CapabilityNotSupportedError` is raised before any request to the satellite

## Scenario: SDK pre-flight on a deployment without monitoring_url
**Given** a monitoring satellite and a deployment whose `monitoring_url` is null
**When** a native monitoring method is called
**Then** `CapabilityNotSupportedError` is raised with a deployment-specific message and no
satellite request is made

## Scenario: SDK forwards query dimensions it does not know
**Given** a satellite that accepts `start` and `end` for custom ranges
**When** `overview(start=…, end=…)` is called
**Then** the parameters reach the satellite unchanged and the answer is returned; an invalid
value yields the satellite's 422 as `UnprocessableEntityError`

## Scenario: SDK detects a contract violation
**Given** a satellite claiming `monitoring` v1 whose overview answer lacks the contract's
required top-level structure
**When** `overview()` is called
**Then** `ContractViolationError` is raised naming the satellite and operation

## Scenario: SDK detects an out-of-sync satellite
**Given** a satellite whose stored document claims `monitoring` but which answers a native
path with 404 `unknown_route`
**When** a native method is called
**Then** `SatelliteOutOfSyncError` is raised with a restart/re-pair hint, while 404
`deployment_not_hosted` and a 404 without a recognized code still surface as not-found

## Scenario: agent uses a custom facet through the generic layer
**Given** a satellite with a stored OpenAPI containing operations tagged
`deployment:custom.gpu_monitoring`
**When** `operations(facet="deployment:custom.gpu_monitoring")` is called and one listed
operation is invoked through `request()`
**Then** the listing contains only those operations with their summaries and parameters, and
the request is sent to the satellite with the bearer key and its JSON answer returned

## Scenario: request() never sends the key to another origin
**Given** a satellite handle whose `base_url` is `https://sat.example`
**When** `request()` is called with a relative path, with an absolute URL on
`https://sat.example`, and with an absolute URL on another origin
**Then** the first two reach the satellite with the bearer key, and the third raises before
any request is sent

## Scenario: satellite docs require the key
**Given** a running satellite
**When** `/openapi.json`, `/docs` or `/redoc` is requested without a bearer key
**Then** the answer is 401/403; with a valid key the documents are served

## Scenario: contract snapshot drift
**Given** the committed snapshot of the satellite's full static spec
**When** a native SDK method uses a path template or query parameter absent from the
snapshot, or the satellite's generated static spec differs from the snapshot
**Then** the SDK contract test fails in the first case and the satellite snapshot test fails
in the second

# Tasks

- [x] Stamp model kind and monitoring producer tags at packaging
  - [x] Add `luml.ai::kind_tabular:v1` / `luml.ai::kind_llm:v1` to the default tags of the sklearn,
        xgboost, lightgbm, catboost and langgraph packagers
        (`sdk/python/sdk/luml/integrations/*/packaging/__init__.py`), built from
        `FNNX_PRODUCER_NAME` like the existing framework tags
  - [x] Replace `REFERENCE_PROFILE_TAG` in `sdk/python/sdk/luml/utils/packaging.py` with the
        `luml.ai::tabular_monitoring:v1` tag, stamped by `save_sklearn` only when a profile is
        embedded
  - [x] Tests in `sdk/python/sdk/tests/` for every packager's tags and for the with/without
        reference-data cases

- [x] Expose post-hoc reference profile embedding on ModelReference
  - [x] Public operation on `ModelReference` (`sdk/python/sdk/luml/artifacts/model.py`) that
        builds and embeds the profile into the local bundle and stamps the tags in the bundled
        manifest, refusing `luml.ai::kind_llm:v1`
  - [x] Tests: embed, re-embed idempotency, llm refusal, artifact still validates

- [x] Derive model kind and metric gating from manifest tags on the satellite
  - [x] Replace `detect_model_kind` in `satellite/agent/schemas/deployments.py` with tag-based
        `tabular|llm|unknown`; rename `ml` to `tabular` wherever the header exposes it
  - [x] Gate the profile on the `luml.ai::tabular_monitoring:v<N>` tag and its version in the deployment
        loading path (`satellite/agent/handlers/model_server_handler.py`); one
        `profile_status` enum (`ready | placeholder | absent | unsupported`) in
        `satellite/agent/schemas/monitoring_query.py` used by the worker, header and section
        responses; a missing kind defaults to `unknown` where `ml` is hard-coded today
        (`satellite/agent/monitoring/query_store.py`,
        `satellite/agent/monitoring/greptime_query.py`,
        `satellite/agent/schemas/monitoring_query.py`)
  - [x] Dashboard (`satellite/monitoring-ui`): universal tabs for `llm` and `unknown`, neutral
        wording for `unknown`, tab collapse on restore; regenerate the committed bundle under
        `satellite/agent/monitoring/static/assets`
  - [x] Update `satellite/tests/monitoring/test_model_kind.py`, worker/metric tests and
        dashboard tests

- [x] Type and version satellite capability declarations on the platform
  - [x] Replace the closed enum in `backend/luml/schemas/satellite.py` with reserved names,
        `custom.*` and facet-id validation (levels limited to `satellite` and `deployment`),
        per-version typed models for `deploy` and `monitoring`, normalization of reserved
        declarations at pair (defaults for `api_versions`, `facets` and `monitoring`
        `features` filled before storing; custom declarations stored verbatim), the generic
        envelope, and the computed `present_capabilities` list on the satellite read/list
        schema; the column annotation in `backend/luml/models/satellite.py` references the
        removed enum
  - [x] Supported declaration/API version sets for `deploy` and `monitoring` and the
        `capability_version_unsupported` eligibility reason in
        `backend/luml/handlers/monitoring.py` and `backend/luml/schemas/monitoring.py`
  - [x] Pairing handler (`backend/luml/handlers/satellites.py`) rejects unknown unprefixed
        names, malformed reserved declarations and invalid facet ids with 422 naming the
        offender; a reserved declaration at an unvalidatable `version` passes the generic
        envelope and counts as absent
  - [x] Backend tests for pairing, eligibility, normalization and version handling

- [x] Enforce satellite capabilities on deployment create and update
  - [x] Checks in `backend/luml/handlers/deployments.py`: on create, a present `deploy`
        capability on the target satellite, `monitoring_mode` versus the present `monitoring`
        capability, manifest variant versus the `deploy` declaration's `supported_variants`
        and producer tags versus its `supported_tags_combinations`; on update, a
        `monitoring_mode` change versus the deployment's current satellite; every refusal
        answers 409 naming the reason
  - [x] Backend tests for each refusal and the passing case

- [x] Store and serve the satellite OpenAPI document on the platform
  - [x] Optional `openapi` field on the pair schema (validated only as a JSON object of at
        most 2 MB, stored opaquely, cleared when a re-pair omits it), JSONB column on the
        satellite model with a migration, and a read endpoint in
        `backend/luml/api/orbits/orbit_satellites.py`
  - [x] Tests: pair with and without the document, re-pair clearing it, the size cap, read
        endpoint, list/read payloads unchanged

- [x] Tag, secure and describe the satellite OpenAPI
  - [x] Tag every machine route with its facet id (`satellite/agent/agent_api.py`,
        `satellite/agent/monitoring/api.py`); the inference-access check under `satellite`;
        dashboard routes (`satellite/agent/monitoring/app.py`, the query router) stay untagged
        and are excluded from the pushed document
  - [x] Per-operation security in the schema builder (`satellite/agent/agent_api.py`): bearer,
        or none for the inference-access check
  - [x] Summary and description on every operation
  - [x] Bearer requirement on the satellite's own OpenAPI and docs routes
  - [x] Tests for facet tags, security per operation, descriptions and docs auth

- [x] Advertise honest capabilities and push the static OpenAPI
  - [x] `SatelliteManager.get_capabilities` in `satellite/agent/agent_manager.py` derived from
        configuration and registered metrics, with `api_versions`, `facets` and `features`
  - [x] Static base spec without merged deployment schemas, filtered to operations whose facet
        belongs to an advertised capability, sent in `pair_satellite`
        (`satellite/agent/clients/platform_client.py`)
  - [x] Update `satellite/tests/test_capabilities.py`; tests for the pushed document with
        monitoring enabled and disabled

- [x] Report monitoring_url on the deployment record
  - [x] Nullable `monitoring_url` on the platform deployment model, schemas and migration;
        accepted from the satellite's deployment update call, which becomes a true partial
        update in `backend/luml/handlers/deployments.py` (omitted fields untouched, explicit
        null clears)
  - [x] Add it to the satellite's own `DeploymentUpdate` schema
        (`satellite/agent/schemas/deployments.py`); report it in
        `satellite/agent/tasks/deploy.py`, on reconcile, and from the startup sync in
        `satellite/agent/handlers/model_server_handler.py` only when the agent advertises
        `monitoring` and the deployment's mode is not `off`; clear it on reconcile when
        monitoring is turned off
  - [x] Add it to the SDK `Deployment` type (`sdk/python/api/luml_api/_types.py`)
  - [x] Backend, satellite and SDK type tests

- [x] Return structured 404 codes from the satellite API
  - [x] `deployment_not_hosted` on the machine surface and an app-wide `unknown_route` for any
        unmatched path outside the dashboard's static mount; other 404s unchanged
  - [x] Tests in `satellite/tests/monitoring/test_machine_api.py`

- [x] Gate the deployment forms on present capabilities and show the monitoring hint
  - [x] Mirror the capability interfaces and `present_capabilities` in
        `frontend/src/lib/api/satellites/interfaces.ts` by hand from the backend models
  - [x] In `frontend/src/components/deployments/form/DeploymentsFormSatelliteSettings.vue`
        and `frontend/src/components/deployments/edit/DeploymentsEditor.vue`: offer only
        satellites whose `present_capabilities` includes `deploy`, and gate the monitoring
        toggle on `monitoring` in that list — never on raw `capabilities`
  - [x] Hint next to the toggle in both components, listing the universal sections plus the
        satellite's `features` when the artifact carries a supported `luml.ai::tabular_monitoring`
        tag, derived from artifact producer tags
  - [x] Add `capability_version_unsupported` to `frontend/src/lib/api/monitoring/interfaces.ts`
        and render it in `frontend/src/pages/DeploymentMonitoringPage.vue`
  - [x] Component tests for satellite filtering, toggle gating, the four tag cases plus the
        reduced-`features` case, and the new reason

- [x] Add the SDK satellite handle with the generic operations layer
  - [x] `satellites` resource in `sdk/python/api/luml_api/resources/` (sync and async) reading
        the platform record and the stored OpenAPI, with `operations(facet=…)` and
        `request(...)`; a `Satellite` type in `sdk/python/api/luml_api/_types.py`
  - [x] Unit tests in `sdk/python/api/tests/unit/` for listing by facet, the no-document
        error, relative/absolute URL resolution, the foreign-origin refusal and bearer
        forwarding

- [ ] Dispatch native SDK monitoring methods by API version
  - [ ] Per-version implementations and selection in
        `sdk/python/api/luml_api/resources/monitoring.py`; `monitoring_url` as the request
        base; pre-flight errors; removal of client-side query validation; required-structure
        check with `ContractViolationError`; `SatelliteOutOfSyncError` mapping — new error
        types in `sdk/python/api/luml_api/_exceptions.py`, exported from
        `sdk/python/api/luml_api/__init__.py`; `monitoring()` in
        `sdk/python/api/luml_api/resources/deployments.py` (today built from `base_url`
        only) hands the satellite record and the deployment record to the resource
  - [ ] Update `sdk/python/api/tests/unit/test_deployment_resources.py` and add tests for each
        pre-flight error, pass-through, contract violation and out-of-sync mapping

- [ ] Add the satellite OpenAPI contract snapshot and tests
  - [ ] Commit the snapshot of the full static spec (monitoring enabled, before facet
        filtering); satellite test asserting the generated spec equals it; SDK test asserting
        every native method's path and parameters exist in it
