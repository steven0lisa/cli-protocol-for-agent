# Changelog

All notable changes to the HTTP CLI Protocol specification are documented here.

The project follows [Semantic Versioning](https://semver.org/) for the
specification itself. Version numbers apply to the protocol document and its
machine-readable schemas as one unit.

**Version bump rules:**

| Change | Bump |
|--------|------|
| Editorial fixes, clarifications, examples | PATCH |
| New OPTIONAL fields, new reserved parameters, new standard error codes | MINOR |
| New REQUIRED fields, changed meanings, removed elements | MAJOR |

Clients MUST ignore unknown response fields; therefore MINOR additions are
non-breaking by construction.

## [Unreleased]

### Added

- `INSTALL.md`: an agent-facing implementation guide — reading order for the
  specification, incremental user information-gathering script, implementation
  and conformance-verification steps, and the required AGENTS.md/CLAUDE.md
  sync-maintenance template. Linked from both READMEs with a copy-ready
  instruction.
- Standard version surface (RECOMMENDED): `version/current` for protocol and
  implementation versions with release timestamp, and `version/releases` for
  release notes (newest first) with `since=` increment filtering and bounded
  `limit`, so agents can detect new releases and read what changed without
  downloading full history. Exact standard names mandated when provided;
  agreement with root help required. Schema: `version.schema.json`.
- Recommended auth pattern in the specification: user-issued console tokens
  delivered as a copy-ready CLI snippet for the agent, so every call carries
  the creating user's identity; with rules (header-only carriage, one-time
  redemption links instead of credential URLs, revocation controls).
- Contribution guide (`CONTRIBUTING.md`): change process, versioning and
  deprecation policy, editorial style, conformance-suite etiquette.
- Reference implementation (`reference/`): dependency-free Python engine
  (registry → tree, progressive help, validation, envelopes, projection,
  errors) with a demo notes-service command tree and a stdlib HTTP server.
- Black-box conformance suite (`conformance/run.py`): checks any live
  deployment against the specification's conformance checklist over plain HTTP.
- Unit tests (`tests/`) and `make selftest` (23 unit checks + 212 black-box
  checks passing against the reference implementation).
- README: spec status badges.

### Changed

- Clarified that a bare `?help` parameter requests help; other non-boolean
  values are rejected with `400` / `invalid_param`.
- Clarified that the root node's `path` in help documents is `/` (paths are
  relative to the Base URL). Schemas updated accordingly (`pathPattern`).

## [1.0.0] — 2026-10-14

First release.

### Added

- Command-tree model: URL path = command path, group nodes vs. command nodes,
  naming rules, HTTP method semantics, reserved parameter names (`help`,
  `fields`).
- Progressive help: `?help=1` self-description at every node; group help lists
  direct children only (depth limiting); command help carries a typed parameter
  schema; normative **single source of truth** rule (help generated from the
  dispatch registry, no drift).
- Uniform output contract: success envelope (`data`, `meta`) and error envelope
  (`error.code`, `error.message`, `error.hint`, `error.details`); standard error
  code table with HTTP status mapping; naming and encoding conventions.
- Field projection via `fields=` for token economy; pagination conventions
  (offset form / page form) with bounded `limit`.
- Pluggable authentication: header-only credential carriage, HTTPS requirement,
  `authentication` discovery object in root help, 401/403 failure semantics,
  and an eight-item **implementation duty-of-care** guide every deployment must
  document (credential type, issuance, scope, lifetime, transport, failures,
  audit, agent handoff).
- Discovery & versioning: `/.well-known/http-cli`, `X-HTTP-CLI-Version`
  header, `protocol_version` in root help, forward-compatibility rules.
- Informative sections: token economy guidance, security considerations,
  conformance checklist, end-to-end walkthrough.
- Machine-readable schemas: `envelope.schema.json`, `help.schema.json`,
  `parameter.schema.json` (JSON Schema draft 2020-12).
