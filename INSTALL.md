# INSTALL — Implementation Guide for AI Agents

This guide is written for AI agents. You are here because a developer asked you
to **implement a CLI Protocol Family spec for their system**. The five-step
walkthrough below details **HTTP CLI**; Web, Android, and Electron CLI share
the same machinery (see *Choosing your protocol*). Follow the steps in
order. Do not skip Step 1, and do not start coding before Step 2's questions
have been answered by the user.

```
Step 1  Read the specification and understand the background
Step 2  Gather the project's information from the user (incrementally)
Step 3  Implement the command tree
Step 4  Verify with the conformance suite
Step 5  Write the sync-maintenance contract into AGENTS.md / CLAUDE.md  (required)
```

---

## Choosing your protocol

The CLI Protocol Family covers four runtimes. Pick by where the target system
lives; all four share one machinery — self-describing command tree,
progressive help, one envelope, descriptor-based semantics, auto-increment
ids, and a bounded async model (see
[cli-family.md](docs/specification/v1.0.0/cli-family.md) for the shared
nomenclature and recommended architecture).

| Your system is a… | Protocol | Specification | Implementation guide |
|-------------------|----------|---------------|----------------------|
| Network service (HTTP API) | **HTTP CLI** | [v1.0.0](docs/specification/v1.0.0/http-cli.md) | **This document (Steps 1–5 below)** |
| Web page / SPA | **Web CLI** | [v1.0.0](docs/specification/v1.0.0/web-cli.md) | Spec § Integration guide |
| Android app | **Android CLI** | [v1.0.0](docs/specification/v1.0.0/android-cli.md) | Spec § Integration guide |
| Electron desktop app | **Electron CLI** | [v1.0.0](docs/specification/v1.0.0/electron-cli.md) | Spec § Integration guide |

The five steps below walk through **HTTP CLI** in detail. The sibling
protocols apply the same steps with a different transport and adapters — see
the *Implementing the sibling protocols* section at the end.

## Step 1 — Read the specification and understand the background

Read these files in this order and keep them open while you work:

| # | File | Why |
|---|------|-----|
| 1 | [README.md](README.md) | Background and motivation: why a help-driven command tree over HTTP exists. |
| 2 | [docs/specification/v1.0.0/http-cli.md](docs/specification/v1.0.0/http-cli.md) | **The normative specification.** Everything you build must conform to it. |
| 3 | [docs/specification/v1.0.0/schemas/](docs/specification/v1.0.0/schemas/) | Machine-readable JSON Schemas for envelopes, help documents, parameters, version surface. |
| 4 | [CHANGELOG.md](CHANGELOG.md) | Spec version history and bump rules. |
| 5 | [reference/](reference/) | A working, dependency-free reference implementation to learn the mechanics from. |
| 6 | [conformance/run.py](conformance/run.py) | The black-box suite that will judge your implementation in Step 4. |

**Background in one paragraph.** The protocol maps a traditional CLI's
experience — a command tree with progressive `--help` — onto plain HTTP, so
that AI agents can explore and operate an unfamiliar system with minimal token
consumption. Its three design pillars: (1) progressive, help-driven discovery
(one level per request, never a full schema dump), (2) one uniform output
envelope for data and errors, (3) pluggable authentication with a normative
duty-of-care checklist.

**Invariants you must internalize before writing any code:**

- **Single source of truth**: help is *generated from the same registry that
  dispatches*. Never maintain a hand-written help artifact that can drift.
- **Envelope**: success is `{"data": …, "meta": …}`; failure is
  `{"error": {"code", "message", "hint"?, "details"?}}` — never both.
- **Reserved parameters**: `help` and `fields` belong to the protocol; command
  schemas must not declare them.
- **HTTP semantics**: `GET` must be side-effect-free; the method declared in a
  command's help is the method clients must use.
- **Depth limiting**: group help lists direct children only, one-line
  summaries — that is where the token economy comes from.
- **Auth duty of care**: the scheme is yours to choose, but eight items must
  be documented and discoverable (see Step 2.4 and the spec's
  *Authentication & Authorization* chapter).
- The specification is the source of truth. Where this guide and the spec
  disagree, follow the spec.

---

## Step 2 — Gather the project's information from the user (incrementally)

Ask the user **in small batches** — one topic per turn, at most 2–3 questions
at a time. Never dump the whole list at once; adapt your next question to the
answers you already have. After each batch, restate what you understood before
moving on.

### 2.1 Mount and discovery (ask first)

1. Where should the command tree be mounted? (e.g. `/api/cli`, `/cli`)
2. Is there a public base URL for it, or is it only reachable inside the
   service?

### 2.2 Capability scope

3. Which resources/capabilities should become commands? Sketch the top-level
   groups with the user (e.g. `note`, `user`, `version`).
4. Which domains must be **excluded** (billing, admin, secrets, destructive
   operations)? Exclusion is the default for anything the caller shouldn't
   touch.

### 2.3 Read/write policy

5. Which commands are reads (`GET`), which are writes (`POST`/`PUT`)?
6. Should destructive operations be omitted entirely, or gated behind an
   explicit confirmation parameter? (The spec recommends omission for
   non-human callers.)

### 2.4 Authentication (the eight duty-of-care items)

Walk the user through the spec's checklist; do not accept "we already have
auth" as an answer. Collect a concrete answer for each:

7. **Credential type** — token / signed JWT / API key / short-lived task
   credential? What identity does it carry?
8. **Issuance & distribution** — how do legitimate callers get one? Prefer the
   spec's recommended pattern: the user creates a personal token in their
   account console and hands a copy-ready CLI snippet (credential in a header,
   never in the URL) to their agent.
9. **Scope & least privilege** — which command classes may each credential
   class call? Read vs. write separation? Tenancy boundaries?
10. **Lifetime & revocation** — expiry, rotation, immediate revocation.
11. **Transport** — HTTPS enforced? Header-only carriage? Log redaction?
12. **Failure semantics** — 401 vs. 403 per the spec; hints that don't leak
    existence of resources.
13. **Audit** — is every invocation attributable to a credential identity?
14. **Agent handoff** — when a credential is granted to an agent, is scope and
    lifetime stated to it?

### 2.5 Response shaping and version surface

15. Pagination convention (offset form or page form) and default/maximum
    `limit`.
16. Will you provide the standard version surface (`version/current`,
    `version/releases`)? Where do release notes come from?
17. Does the project already have a version number and release process to
    publish through the CLI?

### 2.6 Summarize before building

After the batches, write a short implementation plan — mount path, command
groups, read/write map, auth model summary, pagination, version surface — and
**ask the user to confirm it**. Only then proceed to Step 3.

---

## Step 3 — Implement the command tree

1. **Follow the reference shape.** The engine in
   [reference/httpcli.py](reference/httpcli.py) (registry → tree, help
   generation, validation, envelopes, projection) is a clean, dependency-free
   model. Reuse it directly when the host language allows, or port its
   structure to your stack.
2. **Register commands next to the code they expose.** Where a service/API
   handler is wired up is where its command node gets registered, so that code
   review sees both in one change.
3. **Handlers stay thin**: parse parameters → call the existing service layer
   → serialize. Never bypass business logic with direct DB writes; the CLI is
   just another consumer of the same service.
4. **Generate help from the registry**; implement `?help=1`, `fields=`
   projection, bounded pagination, and every standard error code from the
   spec's table.
5. **Document the auth model** for integrators (the Step 2 answers) and point
   the root help's `authentication` object at it.

---

## Step 4 — Verify with the conformance suite

```bash
make conformance BASE=<your-base-url> TOKEN=<credential>
```

The black-box suite checks your live deployment against the specification's
conformance checklist (envelopes, help shape, naming rules, error codes,
401/403 semantics, projection, version-surface consistency). Iterate until it
reports **0 failed**.

Also do one manual agent-style walkthrough: root help → drill down one level →
command help → execute with `fields=` → trigger an error and confirm the
`hint` teaches the next request.

---

## Step 5 — Write the sync-maintenance contract (required)

After the implementation ships, add a section to the project's `AGENTS.md`
and/or `CLAUDE.md` **in the same change as the implementation**. These files
are loaded into every future agent session — this is what keeps the CLI from
silently drifting out of date when the code evolves.

Paste-ready template (fill in the angle-bracket placeholders):

```markdown
## HTTP CLI maintenance

- Protocol: HTTP CLI Protocol v1.0.0 — spec at
  `<path>/docs/specification/v1.0.0/http-cli.md` (source of truth).
- Command tree registry: `<path to the single registration site>`
- Help is generated from the dispatch registry — never hand-edit help text.
- **When adding or changing an API endpoint or service method, register the
  corresponding command node in the same change.** A PR that adds an endpoint
  without its command node (or an explicit exclusion note) is incomplete.
- Auth model: `<credential type / issuance / scope / lifetime / revocation>`
- Conformance gate: `make conformance BASE=<base> TOKEN=<token>` must pass
  before release; wire it into CI if possible.
- Version surface: `version/current` + `version/releases` are fed from
  `<version source>`; keep them in sync with root help.
```

Why this works: the contract turns "code changed, CLI didn't" into something
the next reviewing agent sees immediately in its context, instead of a bug
users discover later. If your CI can run the conformance suite, add that as a
gate too — process beats memory.

---

## Implementing the sibling protocols (Web / Android / Electron CLI)

The same five steps apply; here is how each maps onto an in-app protocol:

| Step | HTTP CLI (steps above) | Web / Android / Electron CLI |
|------|------------------------|------------------------------|
| 1 Read | `http-cli.md` | The sibling spec + [cli-family.md](docs/specification/v1.0.0/cli-family.md) nomenclature |
| 2 Inventory | API surface → modules → operations | UI surface: screens/windows/components + exposed actions. The descriptor set *is* the inventory — confirm it with the user the same way |
| 3 Implement | Command tree over HTTP | Install the runtime; register descriptors + function bindings; wire the adapter (React/Vue, View/Compose, web/shell) |
| 4 Verify | `conformance/run.py` | The spec's conformance checklist probes (`/version/current`, `help /`, `/comp/get` round-trip, write gating) |
| 5 Sync contract | `AGENTS.md` / `CLAUDE.md` template above | The same contract: record the registry/descriptor location and the "update descriptors in the same change as the code" rule |

Per-protocol notes:

- **Web CLI** — the kernel installs `globalThis.__WEB_CLI__` in the page's
  **main world** (bundle it with renderer code; an isolated preload is not
  enough for framework introspection). Descriptors are JSON data and MUST
  survive minification. Production profile read-only.
- **Android CLI** — runtime module plus a bridge (abstract local socket,
  reached via `adb forward`); View/Compose adapters; ids scoped to the app
  process; release profile read-only.
- **Electron CLI** — main-process runtime plus a loopback bridge and
  discovery file; the renderer surface is Web CLI scoped per window (`win`
  parameter); dispatch MUST be allowlisted to the command tree — no raw IPC
  passthrough.

Across all four protocols: help is generated from the dispatch registry
(never hand-written), writes require `confirm: true`, and every call is
bounded by `timeout`. The sync contract applies to descriptors exactly as it
applies to the HTTP command tree.

---

## Acceptance checklist

- [ ] Spec read; invariants internalized (Step 1).
- [ ] User's answers collected in batches; implementation plan confirmed
      (Step 2).
- [ ] Command tree implemented with registry-driven help (Step 3).
- [ ] Conformance suite: **0 failed** against the live deployment (Step 4).
- [ ] Auth duty-of-care guide written; root help carries the
      `authentication` object (Step 4).
- [ ] `AGENTS.md` / `CLAUDE.md` updated with the sync-maintenance template
      (Step 5).
