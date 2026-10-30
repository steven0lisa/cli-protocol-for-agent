# CLI Protocol Family

[![Spec version](https://img.shields.io/badge/spec-v1.1.0-blue)](docs/specification/v1.1.0/http-cli.md)
[![Status](https://img.shields.io/badge/status-draft-orange)](docs/specification/v1.1.0/http-cli.md)
[![Schema](https://img.shields.io/badge/json--schema-draft--2020--12-informational)](docs/specification/v1.1.0/schemas/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

> **CLI Protocol Family** — self-describing, help-driven command trees that
> let AI agents explore and operate unfamiliar systems: **HTTP CLI** over
> plain HTTP, **Web CLI** in web pages, **Android CLI** in Android apps, and
> **Electron CLI** in desktop apps.

**Status:** Draft · **Version:** 1.0.0 (all specifications)

English | **[简体中文](README.zh-CN.md)**

Think of a traditional CLI: a tree of commands, each with `--help`, each level
documenting the next. This protocol maps that experience onto HTTP — so that
AI agents (and humans) can explore and operate an unfamiliar system with
nothing more than an HTTP client and a credential, while spending as little
context window as possible.

## Protocol family

HTTP CLI is one member of a sibling family sharing one machinery — a
self-describing command tree, progressive help, one envelope, one error
model, an auto-increment id identity model, and a bounded, settle-aware
async model:

| Protocol | Runtime target | Transport | Call surface | Spec |
|----------|----------------|-----------|--------------|------|
| **HTTP CLI** | Network service | HTTP | URL-path command tree, `?help` | [v1.1.0](docs/specification/v1.1.0/http-cli.md) |
| **Web CLI** | Web page runtime | In-page JavaScript | `exec()` / `help()` methods | [v1.1.0](docs/specification/v1.1.0/web-cli.md) |
| **Android CLI** | Android app runtime | ADB-forwarded bridge | Call objects (`exec` / `help` / `cancel`) | [v1.1.0](docs/specification/v1.1.0/android-cli.md) |
| **Electron CLI** | Electron app runtime | Loopback HTTP bridge | Call objects (`exec` / `help` / `cancel`) | [v1.1.0](docs/specification/v1.1.0/electron-cli.md) |
| **CLI Family** | — | — | Shared standard nomenclature & recommended architecture | [v1.1.0](docs/specification/v1.1.0/cli-family.md) |

## Why

| Problem | This protocol's answer |
|---------|------------------------|
| Agents can't install every CLI binary; HTTP is the common denominator. | A CLI-shaped command tree addressed purely by URL paths. |
| Dumping a whole API schema blows the context window. | **Progressive help**: one level per request; each node explains only itself and its direct children. |
| Ad-hoc response shapes force bespoke parsing. | **One envelope** for data and errors, one error model, stable codes. |
| Auth schemes differ per organization. | **Pluggable credentials** with a normative duty of care: document and publish your authorization model (8 required items). |

## The shape of it

```
GET {base}?help=1                  → root help: top-level groups
GET {base}/note?help=1             → group help: commands under note
GET {base}/note/list?help=1        → command help: parameter schema
GET {base}/note/list?status=active&fields=id,title   → execute
GET {base}/version/current         → current version + release timestamp
GET {base}/version/releases?since=0.1.0 → release notes since a version
```

Every response — help or data — is the same envelope:

```json
{ "data": [ {"id": "n_01", "title": "…"} ],
  "meta": { "request_id": "…", "limit": 5, "has_more": true } }
```

Errors teach the next move:

```json
{ "error": { "code": "invalid_param",
             "message": "parameter \"status\" has invalid value \"open\"",
             "hint": "allowed: active | archived" } }
```

## Implement HTTP CLI in your project

To implement this protocol for your own system, give your agent this
instruction:

> Follow https://github.com/steven0lisa/http-cli-for-agent/blob/main/INSTALL.md
> to implement HTTP CLI for this project.

[INSTALL.md](INSTALL.md) walks the agent through reading the spec, gathering
your project's required information step by step, verifying with the
conformance suite, and writing the sync-maintenance contract into
`AGENTS.md`/`CLAUDE.md`.

## Documentation

| Document | Description |
|----------|-------------|
| [**HTTP CLI Specification v1.1.0**](docs/specification/v1.1.0/http-cli.md) | The normative protocol: command tree, help, envelopes, auth, versioning, conformance. |
| [Web / Android / Electron CLI v1.1.0](docs/specification/v1.1.0/) | Sibling specs for web page, Android app, and Electron app runtimes (see the protocol family table above). |
| [CLI Family v1.1.0](docs/specification/v1.1.0/cli-family.md) | Shared standard nomenclature and recommended implementation architecture. |
| [Schemas](docs/specification/v1.1.0/schemas/) | Machine-readable JSON Schemas: envelopes, help documents, parameter and component descriptors. |
| [Changelog](CHANGELOG.md) | Version history and bump rules. |
| [Contributing](CONTRIBUTING.md) | Change process, versioning policy, style rules. |

## Reference implementation & conformance suite

A dependency-free Python reference implementation and a black-box conformance
suite live in this repository:

```bash
make selftest    # run the conformance suite against the reference implementation
make serve       # start the demo tree (notes service) at http://127.0.0.1:8080/cli
make conformance BASE=http://127.0.0.1:8080/cli TOKEN=demo-token   # any deployment
```

- `reference/` — the engine (registry → tree, help generation, validation,
  envelopes, projection, errors) plus a demo command tree. Python 3 standard
  library only.
- `conformance/run.py` — black-box suite that checks a live deployment against
  the specification's conformance checklist. Works against *any* implementation,
  not just the reference one.

## Design pillars

1. **Help-driven discovery (token economy).** `?help=1` works at every node;
   group listings are depth-limited; `fields=` projection and bounded
   pagination keep responses small. Context cost scales with the task, not the
   system.
2. **Uniform output contract.** `data`/`meta` on success, `error`
   (`code`/`message`/`hint`/`details`) on failure, standard code table, stable
   naming rules. One parser, everywhere.
3. **Pluggable auth with documented responsibility.** The protocol fixes *how*
   credentials travel (headers, HTTPS) and *how* failures look (401 vs 403);
   the scheme itself is yours. Every implementation must publish an
   authorization guide covering credential type, issuance, scope, lifetime,
   transport, failure semantics, audit, and agent handoff.

## Versioning

The specification uses semantic versioning. Servers SHOULD declare
`protocol_version` in root help and the `X-HTTP-CLI-Version` header. Clients
MUST ignore unknown response fields, making MINOR additions non-breaking. See
[CHANGELOG.md](CHANGELOG.md).

## Contributing

Issues and proposals are welcome. Any change to normative behavior MUST update
the specification document and, where applicable, the JSON Schemas in the same
change — the schemas are derived from the specification and must never drift.

## License

[Apache License 2.0](LICENSE)
