"""Demo command tree: a fictional notes service.

Illustrates the registry API of the reference engine. All data is in-memory.
"""

from __future__ import annotations

import itertools
import re
import time
from typing import Any, Dict, List, Tuple

from httpcli import Command, Group, HttpCli, Param, CliError

_seq = itertools.count(1)
_notes: List[Dict[str, Any]] = []
_by_id: Dict[str, Dict[str, Any]] = {}


def _new_id() -> str:
    return f"n_{next(_seq):02d}"


def _seed() -> None:
    now = "2026-10-14T08:00:00Z"
    for title, status in (
        ("Weekly plan", "active"),
        ("Shopping list", "active"),
        ("Old ideas", "archived"),
    ):
        note = {"id": _new_id(), "title": title, "status": status, "created_at": now}
        _notes.append(note)
        _by_id[note["id"]] = note


def _cmd_list(params: Dict[str, Any]) -> Any:
    status = params.get("status", "active")
    limit = params.get("limit", 20)
    return [n for n in _notes if n["status"] == status][:limit]


def _cmd_get(params: Dict[str, Any]) -> Any:
    note = _by_id.get(params["id"])
    if note is None:
        raise CliError(
            "not_found",
            f'note "{params["id"]}" does not exist',
            hint="GET {base}/note/list to see existing notes",
        )
    return note


def _cmd_create(params: Dict[str, Any]) -> Any:
    note = {
        "id": _new_id(),
        "title": params["title"],
        "status": params.get("status", "active"),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _notes.append(note)
    _by_id[note["id"]] = note
    return note


def _cmd_update(params: Dict[str, Any]) -> Any:
    note = _by_id.get(params["id"])
    if note is None:
        raise CliError(
            "not_found",
            f'note "{params["id"]}" does not exist',
            hint="GET {base}/note/list to see existing notes",
        )
    if "title" in params:
        note["title"] = params["title"]
    if "status" in params:
        note["status"] = params["status"]
    return note


def _cmd_me(params: Dict[str, Any]) -> Any:
    return {"name": "demo-agent", "role": "service", "scope": "notes.read notes.write"}


# -- standard version surface ---------------------------------------------

_RELEASES: List[Dict[str, Any]] = [
    {
        "version": "0.2.0",
        "released_at": "2026-10-14T08:00:00Z",
        "summary": "Add archived-status filters and field projection.",
        "notes": "- Notes can now be archived and listed by status.\n- Responses support fields= projection.",
    },
    {
        "version": "0.1.0",
        "released_at": "2026-09-30T08:00:00Z",
        "summary": "Initial demo tree: note list/get/create/update, me.",
    },
]

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)")


def _semver_key(version: str) -> Tuple[int, int, int]:
    m = _SEMVER_RE.match(version.strip())
    if not m:
        raise ValueError(f"not a semver: {version!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _cmd_version_current(params: Dict[str, Any]) -> Any:
    return {
        "protocol_version": "1.0.0",
        "server_version": "0.2.0",
        "released_at": "2026-10-14T08:00:00Z",
        "build": "demo",
        "channel": "stable",
    }


def _cmd_version_releases(params: Dict[str, Any]) -> Any:
    releases = [r for r in _RELEASES if not r.get("yanked")]
    since = params.get("since")
    if since:
        try:
            key = _semver_key(since)
        except ValueError:
            # Uncomparable input: return the full list (documented in help).
            key = None
        if key is not None:
            releases = [r for r in releases if _semver_key(r["version"]) > key]
    limit = params.get("limit", 10)
    return releases[:limit]


_seed()

DEMO_ROOT = Group(
    name="notes",
    summary="Notes demo service",
    description="A fictional notes service used to illustrate the protocol.",
    children=[
        Group(
            name="note",
            summary="Notes management",
            children=[
                Command(
                    name="list",
                    method="GET",
                    summary="List notes",
                    description="Returns notes filtered by status, in insertion order.",
                    handler=_cmd_list,
                    params=[
                        Param("status", "enum", "Filter by note status.",
                              enum=("active", "archived"), default="active"),
                        Param("limit", "integer", "Maximum number of items to return (1-100).",
                              default="20"),
                    ],
                    examples=["GET {base}/note/list?status=active&fields=id,title"],
                ),
                Command(
                    name="get",
                    method="GET",
                    summary="Get one note by id",
                    handler=_cmd_get,
                    params=[Param("id", "string", "Note identifier.", required=True)],
                    examples=["GET {base}/note/get?id=n_01"],
                ),
                Command(
                    name="create",
                    method="POST",
                    summary="Create a note",
                    handler=_cmd_create,
                    params=[
                        Param("title", "string", "Note title.", required=True),
                        Param("status", "enum", "Initial status.",
                              enum=("active", "archived"), default="active"),
                    ],
                ),
                Command(
                    name="update",
                    method="POST",
                    summary="Update a note",
                    handler=_cmd_update,
                    params=[
                        Param("id", "string", "Note identifier.", required=True),
                        Param("title", "string", "New title."),
                        Param("status", "enum", "New status.", enum=("active", "archived")),
                    ],
                ),
            ],
        ),
        Group(
            name="version",
            summary="Version and release notes",
            description="Standard version surface: current version metadata and release history.",
            children=[
                Command(
                    name="current",
                    method="GET",
                    summary="Current protocol and implementation version",
                    description="Returns the protocol version, implementation version, and release timestamp.",
                    handler=_cmd_version_current,
                ),
                Command(
                    name="releases",
                    method="GET",
                    summary="Release notes, newest first",
                    description="Returns release objects (version, released_at, summary, notes). "
                                "since filters to releases newer than that version (semver). "
                                "When the since value cannot be compared, the full list is returned.",
                    handler=_cmd_version_releases,
                    params=[
                        Param("since", "string",
                              "Return only releases newer than this version (semver)."),
                        Param("limit", "integer", "Maximum releases to return (1-50).", default="10"),
                    ],
                    examples=["GET {base}/version/releases?since=0.1.0"],
                ),
            ],
        ),
        Command(
            name="me",
            method="GET",
            summary="Current caller identity",
            handler=_cmd_me,
        ),
    ],
)


def build_app() -> HttpCli:
    return HttpCli(
        DEMO_ROOT,
        base_path="/cli",
        root_name="root",
        server_version="0.2.0",
        authentication={
            "scheme": "bearer",
            "header": "Authorization",
            "value_format": "Bearer <token>",
            "description": "Demo authentication: any non-empty bearer token is accepted.",
            "obtain": "This demo accepts the literal token 'demo-token'.",
        },
    )
