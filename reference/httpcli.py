"""HTTP CLI Protocol reference engine.

Implements the v1.0.0 specification: command registry -> command tree,
progressive help, parameter validation, uniform envelopes, field projection,
and the standard error model. Python 3 standard library only.

This engine is illustrative; the specification is the source of truth.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

PROTOCOL_VERSION = "1.0.0"

NODE_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
ERROR_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
RESERVED_PARAMS = ("help", "fields")
PARAM_TYPES = ("string", "integer", "number", "boolean", "enum", "array", "object")
HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")

HELP_VALUE_TRUE = ("1", "true")


# --------------------------------------------------------------------------
# Registry types
# --------------------------------------------------------------------------

class Param:
    def __init__(
        self,
        name: str,
        type: str = "string",
        description: str = "",
        required: bool = False,
        default: Optional[str] = None,
        enum: Optional[Sequence[str]] = None,
    ) -> None:
        self.name = name
        self.type = type
        self.description = description
        self.required = required
        self.default = default
        self.enum = list(enum) if enum is not None else None

    def to_help(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "description": self.description,
        }
        if self.default is not None:
            out["default"] = self.default
        if self.enum is not None:
            out["enum"] = self.enum
        return out


class Command:
    def __init__(
        self,
        name: str,
        method: str,
        summary: str,
        handler: Callable[..., Any],
        description: str = "",
        params: Sequence[Param] = (),
        examples: Sequence[str] = (),
    ) -> None:
        self.name = name
        self.method = method
        self.summary = summary
        self.handler = handler
        self.description = description
        self.params = list(params)
        self.examples = list(examples)


class Group:
    def __init__(
        self,
        name: str,
        summary: str,
        description: str = "",
        children: Sequence[Any] = (),
    ) -> None:
        self.name = name
        self.summary = summary
        self.description = description
        self.children = list(children)

    def child(self, name: str) -> Optional[Any]:
        for c in self.children:
            if c.name == name:
                return c
        return None


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------

ERROR_STATUS = {
    "invalid_param": 400,
    "missing_param": 400,
    "bad_body": 400,
    "unauthorized": 401,
    "forbidden": 403,
    "unknown_command": 404,
    "not_found": 404,
    "method_not_allowed": 405,
    "conflict": 409,
    "payload_too_large": 413,
    "unsupported_media_type": 415,
    "rate_limited": 429,
    "internal_error": 500,
}


class CliError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        hint: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.details = details

    @property
    def status(self) -> int:
        return ERROR_STATUS.get(self.code, 500)

    def to_body(self) -> Dict[str, Any]:
        err: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.hint is not None:
            err["hint"] = self.hint
        if self.details is not None:
            err["details"] = self.details
        return {"error": err}


# --------------------------------------------------------------------------
# Registry validation (build-time)
# --------------------------------------------------------------------------

def validate_registry(root: Group) -> None:
    if not NODE_NAME_RE.match(root.name):
        raise ValueError(f"illegal node name: {root.name!r}")
    _validate_children(root, "/")


def _validate_children(node: Group, path: str) -> None:
    seen = set()
    for child in node.children:
        if not NODE_NAME_RE.match(child.name):
            raise ValueError(f"illegal node name: {child.name!r} under {path}")
        if child.name in seen:
            raise ValueError(f"duplicate sibling name {child.name!r} under {path}")
        seen.add(child.name)
        child_path = ("" if path == "/" else path) + "/" + child.name
        if isinstance(child, Group):
            _validate_children(child, child_path)
        elif isinstance(child, Command):
            if child.method not in HTTP_METHODS:
                raise ValueError(f"illegal method {child.method!r} on {child_path}")
            param_names = set()
            for p in child.params:
                if p.name in RESERVED_PARAMS:
                    raise ValueError(f"reserved param name {p.name!r} on {child_path}")
                if not NODE_NAME_RE.match(p.name):
                    raise ValueError(f"illegal param name {p.name!r} on {child_path}")
                if p.name in param_names:
                    raise ValueError(f"duplicate param {p.name!r} on {child_path}")
                param_names.add(p.name)
                if p.type not in PARAM_TYPES:
                    raise ValueError(f"illegal param type {p.type!r} on {child_path}")
                if p.type == "enum" and not p.enum:
                    raise ValueError(f"enum param {p.name!r} on {child_path} needs values")
                if p.type != "enum" and p.enum is not None:
                    raise ValueError(f"non-enum param {p.name!r} on {child_path} must not carry enum")
                if not p.description:
                    raise ValueError(f"param {p.name!r} on {child_path} needs a description")
            if not child.summary:
                raise ValueError(f"command {child_path} needs a summary")
        else:
            raise ValueError(f"unknown node type under {path}")


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------

class HttpCli:
    def __init__(
        self,
        root: Group,
        *,
        base_path: str = "/cli",
        root_name: str = "root",
        server_version: Optional[str] = None,
        authentication: Optional[Dict[str, Any]] = None,
    ) -> None:
        validate_registry(root)
        self.root = root
        self.root_name = root_name
        self.base_path = "/" + base_path.strip("/")
        self.server_version = server_version
        self.authentication = authentication

    # -- public API --------------------------------------------------------

    def dispatch(
        self,
        method: str,
        raw_path: str,
        query: Optional[Dict[str, str]] = None,
        body: Any = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, Dict[str, Any]]:
        """Return (status, body). Headers are handled by the transport layer."""
        try:
            return self._dispatch(method.upper(), raw_path, query or {}, body, headers or {})
        except CliError as e:
            return e.status, e.to_body()

    # -- internals ---------------------------------------------------------

    def _dispatch(
        self,
        method: str,
        raw_path: str,
        query: Dict[str, str],
        body: Any,
        headers: Dict[str, str],
    ) -> Tuple[int, Dict[str, Any]]:
        path = raw_path.split("?", 1)[0]
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        if not path.startswith(self.base_path):
            raise CliError(
                "unknown_command",
                f"path {raw_path!r} is outside the command tree",
                hint=f"GET {self.base_path}?help=1 to see available subcommands",
            )
        rest = path[len(self.base_path):].strip("/")
        segments = [s for s in rest.split("/") if s] if rest else []

        # help=... normalization
        help_raw = query.get("help")
        want_help = False
        if help_raw is not None:
            if help_raw.lower() in HELP_VALUE_TRUE or help_raw == "":
                want_help = True
            else:
                raise CliError(
                    "invalid_param",
                    f'parameter "help" has invalid value {help_raw!r}',
                    hint="use help=1 to request help",
                )

        trail = self.base_path
        help_path = ""  # path in help documents is relative to the Base URL
        node: Any = Group(self.root_name, self.root.summary, self.root.description, self.root.children)
        for seg in segments:
            if not isinstance(node, Group):
                raise CliError(
                    "unknown_command",
                    f'unknown command {seg!r} under {trail}',
                    hint=f"GET {trail}?help=1 to see usage",
                )
            nxt = node.child(seg)
            if nxt is None:
                raise CliError(
                    "unknown_command",
                    f'unknown command {seg!r} under {trail}',
                    hint=f"GET {trail}?help=1 to see available subcommands",
                )
            node = nxt
            trail += "/" + seg
            help_path += "/" + seg
        if help_path == "":
            help_path = "/"

        if isinstance(node, Group):
            return 200, {"data": self._group_help(help_path, node)}

        # command node
        if want_help:
            return 200, {"data": self._command_help(help_path, node)}

        if method != node.method:
            raise CliError(
                "method_not_allowed",
                f"{trail} requires {node.method}",
                hint=f"GET {trail}?help=1 for usage",
            )

        params = self._collect_params(node, query, body)
        result = node.handler(params)

        if "fields" in query:
            result = project_fields(result, query["fields"])

        meta: Dict[str, Any] = {"request_id": new_request_id()}
        if isinstance(result, list):
            meta.setdefault("limit", len(result))
            meta.setdefault("has_more", False)
        return 200, {"data": result, "meta": meta}

    def _collect_params(
        self, cmd: Command, query: Dict[str, str], body: Any
    ) -> Dict[str, Any]:
        if cmd.method in ("POST", "PUT", "PATCH"):
            if body is not None and not isinstance(body, dict):
                raise CliError("bad_body", "invalid JSON body", hint="send a JSON object")
        else:
            body = {}
        body = body or {}
        values: Dict[str, Any] = {}
        for p in cmd.params:
            raw = body.get(p.name, query.get(p.name))
            if raw is None or raw == "":
                if p.default is not None:
                    raw = p.default
                elif p.required:
                    raise CliError(
                        "missing_param",
                        f'missing required parameter "{p.name}"',
                        hint=p.description,
                        details={"parameter": p.name},
                    )
                else:
                    continue
            values[p.name] = self._coerce(p, raw)
        return values

    @staticmethod
    def _coerce(p: Param, raw: Any) -> Any:
        if p.type == "enum":
            v = str(raw)
            if v not in p.enum:
                raise CliError(
                    "invalid_param",
                    f'parameter "{p.name}" has invalid value "{v}"',
                    hint="allowed: " + " | ".join(p.enum),
                    details={"parameter": p.name},
                )
            return v
        if p.type == "string":
            return str(raw)
        if p.type == "integer":
            try:
                return int(raw)
            except (TypeError, ValueError):
                raise CliError(
                    "invalid_param",
                    f'parameter "{p.name}" must be an integer',
                    hint=p.description,
                    details={"parameter": p.name},
                )
        if p.type == "number":
            try:
                return float(raw)
            except (TypeError, ValueError):
                raise CliError(
                    "invalid_param",
                    f'parameter "{p.name}" must be a number',
                    hint=p.description,
                    details={"parameter": p.name},
                )
        if p.type == "boolean":
            if isinstance(raw, bool):
                return raw
            v = str(raw).lower()
            if v in ("true", "1"):
                return True
            if v in ("false", "0"):
                return False
            raise CliError(
                "invalid_param",
                f'parameter "{p.name}" must be a boolean',
                hint="use true or false",
                details={"parameter": p.name},
            )
        if p.type == "array":
            if isinstance(raw, list):
                return raw
            return [x.strip() for x in str(raw).split(",") if x.strip()]
        return raw  # object: pass through

    # -- help documents ----------------------------------------------------

    def _group_help(self, path: str, node: Group) -> Dict[str, Any]:
        children = []
        for c in node.children:
            children.append(
                {
                    "kind": "command" if isinstance(c, Command) else "group",
                    "name": c.name,
                    "path": ("" if path == "/" else path) + "/" + c.name,
                    "method": c.method if isinstance(c, Command) else "GET",
                    "summary": c.summary,
                }
            )
        out: Dict[str, Any] = {
            "kind": "group",
            "path": path,
            "name": self.root_name if path == "/" else node.name,
            "method": "GET",
            "summary": node.summary,
            "subcommands": children,
            "usage": f"GET {{base}}{( '' if path == '/' else path )}/<command>?help=1",
        }
        if node.description:
            out["description"] = node.description
        if path == "/":
            out["protocol_version"] = PROTOCOL_VERSION
            if self.server_version:
                out["server_version"] = self.server_version
            if self.authentication:
                out["authentication"] = self.authentication
        return out

    @staticmethod
    def _command_help(path: str, cmd: Command) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "kind": "command",
            "path": path,
            "name": cmd.name,
            "method": cmd.method,
            "summary": cmd.summary,
            "params": [p.to_help() for p in cmd.params],
        }
        if cmd.description:
            out["description"] = cmd.description
        if cmd.examples:
            out["examples"] = cmd.examples
        else:
            out["examples"] = [f"{cmd.method} {{base}}{path}"]
        return out


# --------------------------------------------------------------------------
# Field projection
# --------------------------------------------------------------------------

def project_fields(data: Any, fields_raw: str) -> Any:
    keep = {f.strip() for f in fields_raw.split(",") if f.strip()}
    pick = lambda m: {k: v for k, v in m.items() if k in keep}
    if isinstance(data, dict):
        return pick(data)
    if isinstance(data, list):
        return [pick(x) if isinstance(x, dict) else x for x in data]
    return data


def new_request_id() -> str:
    import uuid

    return uuid.uuid4().hex[:16]


# --------------------------------------------------------------------------
# JSON response helper for transports
# --------------------------------------------------------------------------

def encode_body(body: Dict[str, Any]) -> bytes:
    return (json.dumps(body, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
