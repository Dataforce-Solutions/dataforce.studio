---
sidebar_label: Monitoring API Access Spec
title: Satellite Monitoring API Access Spec
---

# Satellite Monitoring API Access Spec

Status: draft, for review
Scope: programmatic (non-browser) access to the Satellite Monitoring Query API
Extends: Live Monitoring Unified Architecture Spec (`spec_full.md`)
Primary consumer: scripts, CI jobs, external tools acting with a user's LUML API key

## Purpose

The Monitoring Query API already serves every view the dashboard renders: deployment
header, overview, runtime health, data quality, feature drift, reference profile, alerts,
traces, and worker health. What it lacks is a door for machines.

Today the only way in is the browser flow: the Platform mints a single-use launch token
for one user and one deployment, the Satellite exchanges it for a short-lived cookie
session, and every API call rides that cookie. A script that wants the same data has to
impersonate a browser — request a launch token, follow the redirect, capture the cookie,
and repeat all of it per deployment and again after every session expiry or Satellite
restart. Our own traffic generators do exactly this dance, which is the clearest sign the
door is missing, not the data.

This spec defines how a machine client reaches the same data with a credential it already
has, without weakening the dashboard flow or moving any monitoring data off the Satellite.

## Goals

- Let a client with a LUML API key read every monitoring view for deployments it is
  entitled to, directly from the Satellite.
- Keep the browser dashboard flow exactly as it is.
- Introduce no new credential type and no new permission grant: an API key gets monitoring
  read access exactly where its owner could already open the dashboard.
- Keep all monitoring data local to the Satellite; the Platform stays out of the data path.

## Non-goals

- No monitoring data proxied through or stored on the Platform.
- No machine write access in the first version: acknowledging alerts stays a human,
  session-authenticated action.
- No replacement of the launch-token flow; the iframe keeps working unchanged.
- No new key management UI; keys are the existing LUML API keys.

## Credential Model

Two credentials open the Monitoring Query API. They differ in who holds them, how long
they live, and how they are checked — but once past the door, they see the same data.

### Dashboard session (existing, unchanged)

- Obtained by exchanging a single-use launch token minted by the Platform.
- Lives about 30 minutes, held in a cookie, scoped to exactly one deployment.
- Ends on expiry or Satellite restart; the Platform offers a re-launch.
- May acknowledge alerts.

### LUML API key (new for monitoring)

- The user's existing long-lived API key, presented as a bearer credential on each request.
- Verified by the Satellite against the Platform on first use and then from a short-lived
  cache (about a minute), so steady polling does not hammer the Platform and a revoked key
  stops working within that cache window.
- The question asked of the Platform is the same one already asked for inference access:
  does this key's owner hold deployment-read permission in the orbit this Satellite serves?
  That is deliberately the exact permission that gates minting a dashboard launch token —
  so a key can read monitoring precisely where its owner could already open the dashboard,
  and nowhere else. No new permission surface is created.
- Read-only: it cannot acknowledge alerts or perform any other write.
- Never appears in URLs; it travels only in a request header.

## Addressing Model

Every deployment-scoped resource is addressed by the deployment it belongs to, in the
path. This is the structural change that makes key access possible at all: the session
flow could leave the deployment implicit (the session carries it), but a key is valid for
a whole orbit, so the request itself must say which deployment it is about.

The Satellite already has a machine-facing resource tree rooted at the deployment: the
deployment listing and the inference call live there, both authenticated with the same
bearer key this spec adopts. Monitoring joins that tree as another facet of the
deployment, rather than opening a second machine entrance under the dashboard's paths:

```text
GET  /deployments                                       existing: what runs here
POST /deployments/{deployment_id}/compute               existing: inference
GET  /deployments/{deployment_id}/monitoring/overview   new: monitoring, per section
GET  /deployments/{deployment_id}/monitoring/alerts     ...
```

This yields a clean split between the two worlds, each with exactly one credential:

- `/deployments/**` — the machine surface; bearer key on every call, no sessions.
- `/monitoring/**` — the browser surface (launch, the served app, the session API);
  cookie sessions only, untouched by this spec.

No route accepts both credentials, so neither flow inherits the other's failure modes.
The dashboard keeps its implicit-deployment paths, serving identical data.

## API Surface

### Discovery

The Satellite's existing deployment listing gains monitoring fields, additively: alongside
each deployment's id, a caller sees its name, monitoring mode, current status, and when it
was last monitored — enough to iterate without first consulting the Platform. No separate
discovery endpoint is introduced; the listing that already answers "what runs here" now
also answers "what is monitored here".

### Sections

Every section the dashboard renders is available per deployment, with the same query
dimensions (time window, comparison mode, severity filter, feature) and the same response
shapes. A machine client and the dashboard looking at the same deployment and window see
the same numbers.

Raw request payloads (the traces drilldown) are part of this surface. They remain exactly
as local and exactly as protected as before: the data never leaves the Satellite except to
a caller who could already see it in the dashboard.

### Writes

Alert acknowledgement stays session-only in this version. The split is deliberate:
machines watch, humans decide. If machine acknowledgement is ever wanted, it becomes a
separate decision with its own audit story.

## Access Flows

### Machine client

1. The client holds a LUML API key and the Satellite's base URL — the same pair it would
   use to call inference.
2. It lists deployments, or addresses one it already knows.
3. It requests any monitoring section for that deployment, presenting the key on each
   request.
4. The Satellite checks the key against the Platform (or its recent cache) and answers
   from local data.
5. The client repeats at will; no session state exists to expire or lose.

### Dashboard (unchanged)

The launch-token exchange, the cookie session, its lifetime, the re-launch on expiry, and
alert acknowledgement all behave exactly as they do today.

## Failure Behavior

Monitoring access must degrade without ever failing open, and without touching inference.

| Situation | Behavior |
| --- | --- |
| Key invalid, revoked, or its owner lacks permission in this orbit | Refused as unauthenticated — the Platform's answer is a single yes/no, so these are indistinguishable to the Satellite; a revoked key may keep working up to the cache window, then stops |
| Deployment not hosted by this Satellite | Answered as not found; nothing about other Satellites is revealed |
| Deployment hosted, monitoring off or no data | Sections answer with their empty/disabled states, as the dashboard does |
| Platform unreachable, decision still cached | Requests keep working until the cache expires |
| Platform unreachable, no cached decision | Refused as a gateway failure; nothing is served on an unverifiable credential |
| Satellite restarted | Key access unaffected; only dashboard sessions are lost |

## Compatibility

- The dashboard and its session flow are untouched; the session-only paths keep working.
- The demo traffic generators migrate from the launch-token dance to plain key access, and
  serve as the live proof of the new path.
- Deployment-addressed paths are additive; nothing existing is renamed or removed.

## Security Considerations

- The permission model is not widened: key access to monitoring is implied by the same
  permission that already implies dashboard access and inference access.
- The verification cache bounds both Platform load and revocation latency to about a
  minute; both bounds are configurable.
- Keys travel in headers only, are never logged, and never appear in redirects or URLs.
- Failure is closed: an unverifiable credential is refused, never trusted.
- Raw payload visibility is unchanged: the same people (now also their keys) see the same
  data, on the same machine it already lived on.

## Delivery Plan

1. **Monitoring under the deployment tree.** Every section becomes addressable as a
   monitoring facet of the deployment, guarded by the bearer authentication that tree
   already uses. Read-only. Dashboard unaffected. Shippable on its own.
2. **Discovery.** The deployment listing gains its monitoring fields.
3. **Consumers.** Traffic generators switch to key access; the Satellite README documents
   the machine flow.

## Open Questions

1. Should the Platform grow a monitoring-only key scope (a key that can read monitoring
   but not call inference)? The current model treats deployment-read as sufficient for
   both; a narrower scope would need Platform-side work and is deferred until someone
   needs it.
2. Should machine clients ever acknowledge alerts, and with what audit trail?
3. Is rate limiting needed on the monitoring API once keys can poll it, or is the
   verification cache enough?
4. Should the discovery listing include deployments with monitoring off (so a client can
   tell "off" from "unknown"), or only monitored ones?
