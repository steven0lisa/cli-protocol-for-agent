# AGENTS.md — instructions for AI agents working in this repository

This repository hosts the CLI Protocol Family specifications (HTTP CLI,
Web CLI, Android CLI, Electron CLI) and the shared family document. The
specs are the product; keep them coherent.

## Protocol change discipline — version bump & document sync

Any change to protocol content — specification documents, JSON Schemas, the
shared nomenclature in `cli-family.md`, command surfaces, error codes,
reserved names, descriptor fields — MUST land as a **versioned change with
every associated document updated in the same change**. An agent that edits
a spec and stops there has delivered half a change.

1. **Bump the version number.** Follow the Semantic Versioning policy in
   [CONTRIBUTING.md](CONTRIBUTING.md): PATCH for editorial fixes, MINOR for
   compatible additions (new OPTIONAL fields, commands, error codes,
   reserved names), MAJOR for breaking changes. Update the version metadata
   at the top of every touched spec and the schema `$id` URIs, and follow
   the release steps there (new `docs/specification/<version>/` directory;
   older version directories are frozen).

2. **Update `CHANGELOG.md`.** Move `[Unreleased]` entries under the new
   version heading with the release date. Every protocol-visible change
   gets an entry — fields, commands, semantics, renames.

3. **Propagate to every associated document — including the Chinese
   documents.** If a document names the changed field, command, version, or
   link, it is associated and must be updated in the same change:
   - `README.md` **and** `README.zh-CN.md` — badges, version lines,
     documentation links, feature and family tables. **Never update only the
     English README; the Chinese documents must stay in sync.**
   - `docs/specification/*/cli-family.md` — shared nomenclature tables,
     standard command-path tables, name index, family profile matrix.
   - Sibling protocol specs that restate or reference the changed names.
   - `INSTALL.md` and any other guide that embeds version numbers, paths,
     or command examples.
   - Appendices and quick-reference cards that quote the changed surface.

4. **One change = one coherent deliverable.** A spec edit without its
   version bump and document sync is incomplete. Do the whole set together,
   run the sensitive-content scan on everything touched, and only then
   commit — one commit per coherent protocol change.

### Checklist (run before calling a protocol change done)

- [ ] Version bumped in every touched spec header and schema `$id`.
- [ ] `CHANGELOG.md` entry written under the new version.
- [ ] `README.md` and `README.zh-CN.md` both updated.
- [ ] `cli-family.md` tables/index updated if shared names are affected.
- [ ] Cross-links and embedded examples updated everywhere the old name or
      version appears.
- [ ] Sensitive-content and CJK-residue scans clean.
