#!/usr/bin/env python3
"""Black-box conformance suite for the HTTP CLI Protocol (v1.0.0).

Runs a sequence of plain HTTP requests against a live deployment and checks
the responses against the specification's conformance checklist. Uses only
the Python standard library and never imports the reference implementation.

Usage:
    python3 conformance/run.py --base http://127.0.0.1:8080/cli --token demo-token
    python3 conformance/run.py --base https://api.example.com/cli --token $TOKEN --strict

--strict upgrades warnings (SHOULD-level) to failures.

Suite-local naming rule for regex/enum checks: the suite assumes the demo
tree's namespace (note/me) for behavior probes when the tree exposes them;
structural checks (envelopes, help shape, error codes) run against whatever
tree the deployment publishes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

NODE_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
ERROR_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
RESERVED = ("help", "fields")
PARAM_TYPES = ("string", "integer", "number", "boolean", "enum", "array", "object")
METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
STANDARD_CODES = {
    "invalid_param", "missing_param", "bad_body", "unauthorized", "forbidden",
    "unknown_command", "not_found", "method_not_allowed", "conflict",
    "payload_too_large", "unsupported_media_type", "rate_limited", "internal_error",
}


class Result:
    def __init__(self) -> None:
        self.checks: List[Tuple[str, str, str]] = []  # (level, name, detail)

    def ok(self, name: str) -> None:
        self.checks.append(("PASS", name, ""))

    def fail(self, name: str, detail: str) -> None:
        self.checks.append(("FAIL", name, detail))

    def warn(self, name: str, detail: str) -> None:
        self.checks.append(("WARN", name, detail))

    def expect(self, cond: bool, name: str, detail: str = "") -> bool:
        if cond:
            self.ok(name)
        else:
            self.fail(name, detail)
        return cond


class Client:
    def __init__(self, base: str, token: Optional[str]) -> None:
        self.base = base.rstrip("/")
        self.token = token

    def request(
        self,
        method: str,
        path: str,
        query: Optional[Dict[str, str]] = None,
        body: Any = None,
        auth: bool = True,
    ) -> Tuple[int, Dict[str, str], Any]:
        url = self.base + path
        if query:
            from urllib.parse import urlencode

            url += "?" + urlencode(query, doseq=True)
        data = None
        headers = {"Accept": "application/json"}
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                hdrs = dict(resp.headers)
                status = resp.status
        except urllib.error.HTTPError as e:
            raw = e.read()
            hdrs = dict(e.headers or {})
            status = e.code
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"request failed: {method} {url}: {e}") from e
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else None
        except ValueError:
            parsed = None
        return status, hdrs, parsed


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def check_envelope(r: Result, body: Any, name: str, *, expect_error: bool) -> None:
    if not isinstance(body, dict):
        r.fail(name, f"body is not a JSON object: {body!r}")
        return
    has_data = "data" in body
    has_err = "error" in body
    if expect_error:
        if not r.expect(has_err, name + ": error envelope present", f"keys={list(body)}"):
            return
        err = body["error"]
        if not isinstance(err, dict):
            r.fail(name + ": error is object", repr(err))
            return
        for f in ("code", "message"):
            r.expect(isinstance(err.get(f), str) and err[f], name + f": error.{f} is non-empty string", repr(err.get(f)))
        r.expect(ERROR_CODE_RE.match(err.get("code", "")) is not None, name + ": error.code matches ^[a-z][a-z0-9_]*$", repr(err.get("code")))
        if "hint" in err:
            r.expect(isinstance(err["hint"], str), name + ": error.hint is string", repr(err.get("hint")))
        r.expect(not has_data, name + ": no data key on error", str(list(body)))
    else:
        if not r.expect(has_data, name + ": success envelope has data", f"keys={list(body)}"):
            return
        r.expect(not has_err, name + ": no error key on success", str(list(body)))
        if "meta" in body:
            r.expect(isinstance(body["meta"], dict), name + ": meta is object", repr(type(body["meta"])))


def check_help_shape(r: Result, data: Any, name: str, *, expect_kind: str) -> None:
    if not isinstance(data, dict):
        r.fail(name, f"help data is not an object: {data!r}")
        return
    kind = data.get("kind")
    r.expect(kind == expect_kind, name + f": kind == {expect_kind!r}", repr(kind))
    for f in ("path", "name", "method", "summary"):
        r.expect(isinstance(data.get(f), str) and data[f] != "", name + f": {f} present", repr(data.get(f)))
    r.expect(data.get("method") in METHODS, name + ": method is valid HTTP method", repr(data.get("method")))
    if expect_kind == "group":
        subs = data.get("subcommands")
        r.expect(isinstance(subs, list), name + ": subcommands is array", repr(type(subs)))
        if isinstance(subs, list):
            for i, c in enumerate(subs):
                if not r.expect(isinstance(c, dict), name + f": sub[{i}] is object"):
                    continue
                for f in ("kind", "name", "path", "method", "summary"):
                    r.expect(f in c, name + f": sub[{i}].{f} present", str(list(c)))
                if isinstance(c.get("name"), str):
                    r.expect(NODE_NAME_RE.match(c["name"]) is not None, name + f": sub[{i}].name matches naming rule", repr(c["name"]))
                if c.get("kind") == "command":
                    r.expect(c.get("method") in METHODS, name + f": sub[{i}].method valid", repr(c.get("method")))
                # no nested subcommands inlined (depth limiting)
                r.expect("subcommands" not in c and "params" not in c, name + f": sub[{i}] is depth-limited (no grandchildren/params inline)", str(list(c)))
    else:
        params = data.get("params")
        r.expect(isinstance(params, list), name + ": params is array", repr(type(params)))
        if isinstance(params, list):
            names = []
            for i, p in enumerate(params):
                if not r.expect(isinstance(p, dict), name + f": param[{i}] is object"):
                    continue
                names.append(p.get("name"))
                r.expect(p.get("type") in PARAM_TYPES, name + f": param[{i}].type valid", repr(p.get("type")))
                r.expect(isinstance(p.get("description"), str) and p["description"], name + f": param[{i}].description present", repr(p.get("description")))
                r.expect(NODE_NAME_RE.match(p.get("name", "")) is not None, name + f": param[{i}].name matches naming rule", repr(p.get("name")))
                if p.get("type") == "enum":
                    r.expect(isinstance(p.get("enum"), list) and p["enum"], name + f": param[{i}].enum present for enum type", str(p))
                else:
                    r.expect("enum" not in p, name + f": param[{i}].enum absent for non-enum type", str(p))
            for reserved in RESERVED:
                r.expect(reserved not in names, name + f": reserved param {reserved!r} not declared", str(names))


def run_suite(client: Client, strict: bool) -> Result:
    r = Result()

    # --- 1. root help / discovery ---------------------------------------
    status, headers, body = client.request("GET", "/", {"help": "1"})
    r.expect(status == 200, "root help returns 200", str(status))
    check_envelope(r, body, "root help", expect_error=False)
    data = (body or {}).get("data") if isinstance(body, dict) else None
    check_help_shape(r, data, "root help", expect_kind="group")
    if isinstance(data, dict):
        pv = data.get("protocol_version")
        if pv is None:
            r.warn("root help declares protocol_version", "missing (RECOMMENDED)")
        else:
            r.expect(VERSION_RE.match(str(pv)) is not None, "protocol_version is semver-like", repr(pv))
        auth = data.get("authentication")
        if auth is None:
            r.warn("root help carries authentication object", "missing (RECOMMENDED)")
        else:
            for f in ("scheme", "header", "value_format"):
                r.expect(isinstance(auth.get(f), str) and auth[f], f"authentication.{f} present", str(auth))
        # naming rule on root name
        if isinstance(data.get("name"), str):
            r.expect(NODE_NAME_RE.match(data["name"]) is not None, "root name matches naming rule", repr(data["name"]))

    ver_header = headers.get("X-HTTP-CLI-Version") or headers.get("x-http-cli-version")
    if ver_header is None:
        r.warn("X-HTTP-CLI-Version header", "missing (SHOULD)")
    else:
        r.expect(VERSION_RE.match(ver_header) is not None, "X-HTTP-CLI-Version is semver-like", repr(ver_header))

    # --- 2. help parameter handling ------------------------------------
    for val, want in (("true", True), ("1", True), ("", True)):
        st, _, b = client.request("GET", "/", {"help": val})
        ok = st == 200 and isinstance(b, dict) and "data" in b
        r.expect(ok, f"help={val or '<empty>'} accepted", f"status={st}")
    st, _, b = client.request("GET", "/", {"help": "bogus"})
    r.expect(st == 400, "help=bogus rejected with 400", str(st))
    check_envelope(r, b, "help=bogus", expect_error=True)
    if isinstance(b, dict) and isinstance(b.get("error"), dict):
        r.expect(b["error"].get("code") == "invalid_param", "help=bogus code is invalid_param", repr(b["error"].get("code")))

    # --- 3. walk the tree: every listed child must respond -------------
    def walk(path: str, depth: int = 0) -> None:
        if depth > 4:
            return
        st, _, b = client.request("GET", path, {"help": "1"})
        if st != 200 or not isinstance(b, dict):
            r.fail(f"help at {path}", f"status={st}")
            return
        d = b.get("data")
        if not isinstance(d, dict):
            r.fail(f"help at {path}", "data is not an object")
            return
        if d.get("kind") == "group":
            for c in d.get("subcommands", []):
                if not isinstance(c, dict):
                    continue
                child_path = c.get("path", "")
                cst, _, cb = client.request("GET", child_path, {"help": "1"})
                r.expect(cst == 200, f"listed child {child_path} responds 200", str(cst))
                if cst == 200 and isinstance(cb, dict):
                    cd = cb.get("data")
                    if isinstance(cd, dict):
                        r.expect(cd.get("kind") in ("group", "command"), f"{child_path} kind is group|command", repr(cd.get("kind")))
                        if cd.get("kind") == "command":
                            check_help_shape(r, cd, f"{child_path} command help", expect_kind="command")
                        else:
                            walk(child_path, depth + 1)
                # name consistency between listing and child help
                if isinstance(cb, dict) and isinstance(cb.get("data"), dict):
                    r.expect(cb["data"].get("name") == c.get("name"), f"{child_path} name consistent with listing", f'{cb["data"].get("name")} vs {c.get("name")}')

    walk("/")

    # --- 4. errors: unknown command, method mismatch -------------------
    st, _, b = client.request("GET", "/definitely-not-a-command")
    r.expect(st == 404, "unknown command returns 404", str(st))
    check_envelope(r, b, "unknown command", expect_error=True)
    if isinstance(b, dict) and isinstance(b.get("error"), dict):
        r.expect(b["error"].get("code") == "unknown_command", "unknown command code", repr(b["error"].get("code")))
        hint = b["error"].get("hint") or ""
        r.expect("help" in hint, "unknown command hint points back to help", repr(hint))

    # method mismatch (probe only if demo tree exists)
    st, _, b = client.request("DELETE", "/note/list")
    if st == 404:
        r.warn("method mismatch probe", "tree has no /note/list (demo namespace); skipped")
    else:
        r.expect(st == 405, "method mismatch returns 405", str(st))
        check_envelope(r, b, "method mismatch", expect_error=True)
        if isinstance(b, dict) and isinstance(b.get("error"), dict):
            r.expect(b["error"].get("code") == "method_not_allowed", "method mismatch code", repr(b["error"].get("code")))

    # --- 5. auth semantics ---------------------------------------------
    nostatus, _, nobody = client.request("GET", "/note/list", {"help": "1"}, auth=False)
    if client.token:
        r.expect(nostatus == 401, "missing credential returns 401", str(nostatus))
        check_envelope(r, nobody, "missing credential", expect_error=True)
        if isinstance(nobody, dict) and isinstance(nobody.get("error"), dict):
            r.expect(nobody["error"].get("code") == "unauthorized", "missing credential code", repr(nobody["error"].get("code")))
    else:
        r.warn("auth checks", "no token supplied; 401/403 checks skipped")

    # --- 6. demo behavior probes (skipped when tree differs) -----------
    st, _, b = client.request("GET", "/note/list", {"help": "1"})
    demo = st == 200 and isinstance(b, dict) and isinstance(b.get("data"), dict) and b["data"].get("kind") == "command"
    if not demo:
        r.warn("behavior probes", "tree has no demo /note namespace; params/projection/error-hint probes skipped")
    else:
        check_help_shape(r, b["data"], "/note/list help", expect_kind="command")
        params = {p.get("name"): p for p in b["data"].get("params", []) if isinstance(p, dict)}
        r.expect("status" in params and params["status"].get("type") == "enum", "status param is enum", str(list(params)))
        r.expect("fields" not in params and "help" not in params, "reserved params not declared on /note/list", str(list(params)))

        # valid read + projection
        st, _, b = client.request("GET", "/note/list", {"status": "active", "fields": "id,title"})
        r.expect(st == 200, "valid list returns 200", str(st))
        check_envelope(r, b, "valid list", expect_error=False)
        if isinstance(b, dict) and isinstance(b.get("data"), list):
            for item in b["data"]:
                r.expect(set(item.keys()) <= {"id", "title"}, "fields= projection applied", str(sorted(item.keys())))

        # invalid enum value -> invalid_param + hint lists allowed
        st, _, b = client.request("GET", "/note/list", {"status": "open"})
        r.expect(st == 400, "invalid enum returns 400", str(st))
        check_envelope(r, b, "invalid enum", expect_error=True)
        if isinstance(b, dict) and isinstance(b.get("error"), dict):
            r.expect(b["error"].get("code") == "invalid_param", "invalid enum code", repr(b["error"].get("code")))
            hint = b["error"].get("hint") or ""
            r.expect("active" in hint and "archived" in hint, "hint lists allowed enum values", repr(hint))

        # missing required on get
        st, _, b = client.request("GET", "/note/get", {})
        r.expect(st == 400, "missing required param returns 400", str(st))
        if isinstance(b, dict) and isinstance(b.get("error"), dict):
            r.expect(b["error"].get("code") == "missing_param", "missing param code", repr(b["error"].get("code")))

    # --- 7. standard version surface (skip gracefully when absent) ------
    st, _, b = client.request("GET", "/version/current", {"help": "1"})
    if st != 200 or not isinstance(b, dict) or not isinstance(b.get("data"), dict) \
            or b["data"].get("kind") != "command":
        r.warn("version surface", "tree has no standard /version group; version checks skipped")
    else:
        check_help_shape(r, b["data"], "/version/current help", expect_kind="command")
        st, _, cur = client.request("GET", "/version/current", {})
        r.expect(st == 200, "version/current returns 200", str(st))
        check_envelope(r, cur, "version/current", expect_error=False)
        curd = (cur or {}).get("data") if isinstance(cur, dict) else None
        if isinstance(curd, dict):
            for f in ("protocol_version", "server_version", "released_at"):
                r.expect(isinstance(curd.get(f), str) and curd[f], f"version/current.{f} present", repr(curd.get(f)))
            pv = curd.get("protocol_version")
            if pv is not None:
                r.expect(VERSION_RE.match(str(pv)) is not None, "version/current.protocol_version semver-like", repr(pv))
            if isinstance(data, dict):
                r.expect(curd.get("protocol_version") == data.get("protocol_version"),
                         "version/current.protocol_version agrees with root help",
                         f'{curd.get("protocol_version")} vs {data.get("protocol_version")}')
                if data.get("server_version") is not None:
                    r.expect(curd.get("server_version") == data.get("server_version"),
                             "version/current.server_version agrees with root help",
                             f'{curd.get("server_version")} vs {data.get("server_version")}')

        st, _, rel = client.request("GET", "/version/releases", {})
        r.expect(st == 200, "version/releases returns 200", str(st))
        check_envelope(r, rel, "version/releases", expect_error=False)
        reld = (rel or {}).get("data") if isinstance(rel, dict) else None
        if isinstance(reld, list):
            r.expect(len(reld) > 0, "version/releases non-empty", str(len(reld)))
            first = True
            versions = []
            for i, item in enumerate(reld):
                if not r.expect(isinstance(item, dict), f"releases[{i}] is object"):
                    continue
                for f in ("version", "released_at", "summary"):
                    r.expect(isinstance(item.get(f), str) and item[f], f"releases[{i}].{f} present", repr(item.get(f)))
                if isinstance(item.get("version"), str):
                    versions.append(item["version"])
                    r.expect(VERSION_RE.match(item["version"]) is not None, f"releases[{i}].version semver-like", repr(item["version"]))
                if first and isinstance(curd, dict) and isinstance(item.get("version"), str):
                    r.expect(item["version"] == curd.get("server_version"),
                             "newest release matches version/current.server_version",
                             f'{item["version"]} vs {curd.get("server_version")}')
                    first = False
            # since filtering: current version -> empty list
            if isinstance(curd, dict) and isinstance(curd.get("server_version"), str):
                st, _, since_resp = client.request("GET", "/version/releases", {"since": curd["server_version"]})
                r.expect(st == 200, "releases?since=<current> returns 200", str(st))
                sd = (since_resp or {}).get("data") if isinstance(since_resp, dict) else None
                r.expect(sd == [], "releases?since=<current> is empty", repr(sd))

    # --- 8. response hygiene -------------------------------------------
    st, _, b = client.request("GET", "/", {"help": "1"})
    if st == 200 and isinstance(b, dict):
        r.expect(all(isinstance(k, str) for k in b.keys()), "top-level keys are strings")
        if isinstance(b.get("data"), dict):
            r.expect(all(isinstance(k, str) for k in b["data"].keys()), "data keys are strings")

    return r


# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="HTTP CLI protocol conformance suite")
    ap.add_argument("--base", required=True, help="Base URL of the command tree")
    ap.add_argument("--token", default=None, help="Bearer credential")
    ap.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    args = ap.parse_args()

    client = Client(args.base, args.token)
    try:
        result = run_suite(client, args.strict)
    except RuntimeError as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 2

    counts = {"PASS": 0, "FAIL": 0, "WARN": 0}
    for level, name, detail in result.checks:
        counts[level] = counts.get(level, 0) + 1
        line = f"  [{level}] {name}"
        if detail and level != "PASS":
            line += f" — {detail}"
        print(line)

    print()
    print(f"Summary: {counts['PASS']} passed, {counts['FAIL']} failed, {counts['WARN']} warnings")
    if counts["FAIL"]:
        return 1
    if args.strict and counts["WARN"]:
        print("strict mode: warnings treated as failures")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
