# Contributing to the HTTP CLI Protocol

Thank you for helping evolve this specification. This project's deliverable is
the **specification itself** (plus its machine-readable schemas and the
conformance tooling); it deliberately contains no product-specific content.

## Ground rules

1. **Vendor neutrality is absolute.** Documents MUST NOT contain company names,
   product names, internal hostnames, real credentials, ticket identifiers, or
   any proprietary or sensitive information. Examples use fictional services
   (e.g. a "notes" service on `api.example.com`).
2. **English, normative tone.** Specification text uses RFC 2119 keywords
   (MUST, SHOULD, MAY, …) precisely. Informative sections are marked
   *(informative)*.
3. **Spec and schemas never drift.** Any normative change updates
   `docs/specification/<version>/http-cli.md` **and** the affected files in
   `docs/specification/<version>/schemas/` in the same change.
4. **Implementations illustrate, they do not define.** The reference
   implementation and conformance suite must follow the specification; if you
   find yourself changing code to match code, stop — the specification is the
   source of truth.

## Change process

1. Open an issue describing the motivation and the proposed normative change
   (what MUST/SHOULD/MAY changes).
2. Discuss alternatives; note rejected options in the issue for posterity.
3. Submit a change that includes:
   - the specification edit,
   - schema edits (if any),
   - a `CHANGELOG.md` entry under `[Unreleased]`,
   - conformance-suite coverage for new normative behavior,
   - reference-implementation support when the change is testable there.
4. A maintainer reviews for: conformance language precision, vendor neutrality,
   backward compatibility, and schema/spec agreement.

## Versioning policy

The specification follows [Semantic Versioning](https://semver.org/). The
specification document and its schemas version as one unit.

| Change | Bump | Examples |
|--------|------|----------|
| Editorial | PATCH | Wording, typos, examples, informative sections |
| Compatible addition | MINOR | New OPTIONAL field, new standard error code, new reserved parameter |
| Breaking | MAJOR | New REQUIRED field, changed meaning, removed element |

Release steps (maintainers):

1. Move `[Unreleased]` entries in `CHANGELOG.md` under the new version heading
   with the release date.
2. Copy `docs/specification/` to `docs/specification/<new-version>/` and update
   the version metadata at the top of `http-cli.md` and the `$id` URIs in the
   schemas. Older version directories are frozen.
3. Update the badge version in `README.md` and the "Documentation" links.
4. Tag the release (`v<new-version>`).

Clients MUST ignore unknown response fields, which is what makes MINOR
additions non-breaking. Deprecations (see below) are preferred over removals.

## Deprecation policy

- Mark a node or field `deprecated` in its Help document
  (`{"use_instead": "/new/path", "note": "…"}`) for at least one MINOR release
  before a MAJOR removal.
- Deprecated elements continue to work until the announced removal.
- The conformance suite treats a missing `deprecated` marker on a documented
  deprecation as a failure.

## Editorial style

- Tables for enumerable facts; prose for rationale. Keep paragraphs short.
- JSON examples use 2-space indentation and `snake_case` keys.
- Parameter descriptors use the exact field set defined in
  `parameter.schema.json`; do not invent fields in examples.
- Do not use em-dash-heavy or marketing language; write like a protocol.
- Spell out acronyms on first use in a section.

## Conformance suite etiquette

- Every normative MUST in the specification should be checkable; when adding
  one, add a check to `conformance/run.py` (or explain in the PR why it is not
  machine-checkable).
- Checks are black-box HTTP only — no imports from `reference/`.
- The suite must pass against the reference implementation
  (`make selftest`) before a PR is merged.

## Reporting security issues

Do not file public issues for security problems in the conformance tooling or
the reference implementation. Describe the issue privately to the maintainers;
specification ambiguity that creates a security hazard is a normal issue, since
the specification itself is public and normative.

## License

By contributing, you agree that your contributions are licensed under the
[Apache License 2.0](LICENSE).
