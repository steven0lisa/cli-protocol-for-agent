"""Unit tests for the reference engine (stdlib unittest)."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "reference"))

from app import build_app  # noqa: E402
from httpcli import (  # noqa: E402
    CliError,
    Command,
    Group,
    Param,
    project_fields,
    validate_registry,
)


class RegistryValidationTest(unittest.TestCase):
    def test_rejects_bad_name(self) -> None:
        with self.assertRaises(ValueError):
            validate_registry(Group("root", "r", children=[Command("Bad", "GET", "s", lambda p: None)]))

    def test_rejects_reserved_param(self) -> None:
        cmd = Command("x", "GET", "s", lambda p: None, params=[Param("help", "string", "d")])
        with self.assertRaises(ValueError):
            validate_registry(Group("root", "r", children=[cmd]))

    def test_rejects_enum_without_values(self) -> None:
        cmd = Command("x", "GET", "s", lambda p: None, params=[Param("p", "enum", "d")])
        with self.assertRaises(ValueError):
            validate_registry(Group("root", "r", children=[cmd]))

    def test_rejects_duplicate_sibling(self) -> None:
        a = Command("x", "GET", "s", lambda p: None)
        b = Command("x", "POST", "s", lambda p: None)
        with self.assertRaises(ValueError):
            validate_registry(Group("root", "r", children=[a, b]))

    def test_rejects_non_enum_with_enum_values(self) -> None:
        cmd = Command("x", "GET", "s", lambda p: None, params=[Param("p", "string", "d", enum=["a"])])
        with self.assertRaises(ValueError):
            validate_registry(Group("root", "r", children=[cmd]))


class ProjectionTest(unittest.TestCase):
    def test_object(self) -> None:
        self.assertEqual(project_fields({"a": 1, "b": 2, "c": 3}, "a,c"), {"a": 1, "c": 3})

    def test_array(self) -> None:
        out = project_fields([{"a": 1, "b": 2}], "a")
        self.assertEqual(out, [{"a": 1}])

    def test_unknown_keys_ignored(self) -> None:
        self.assertEqual(project_fields({"a": 1}, "a,zzz"), {"a": 1})


class DispatchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = build_app()

    def call(self, method: str, path: str, query=None, body=None):
        return self.app.dispatch(method, path, query, body)

    def test_root_help(self) -> None:
        status, body = self.call("GET", "/cli", {"help": "1"})
        self.assertEqual(status, 200)
        d = body["data"]
        self.assertEqual(d["kind"], "group")
        self.assertEqual(d["path"], "/")
        self.assertIn("protocol_version", d)
        self.assertIn("authentication", d)
        names = [c["name"] for c in d["subcommands"]]
        self.assertEqual(sorted(names), ["me", "note", "version"])

    def test_group_help_depth_limited(self) -> None:
        status, body = self.call("GET", "/cli/note", {"help": "1"})
        self.assertEqual(status, 200)
        for c in body["data"]["subcommands"]:
            self.assertNotIn("params", c)
            self.assertNotIn("subcommands", c)

    def test_command_help(self) -> None:
        status, body = self.call("GET", "/cli/note/list", {"help": "1"})
        self.assertEqual(status, 200)
        d = body["data"]
        self.assertEqual(d["kind"], "command")
        self.assertEqual(d["method"], "GET")
        names = [p["name"] for p in d["params"]]
        self.assertEqual(sorted(names), ["limit", "status"])

    def test_bare_help(self) -> None:
        status, body = self.call("GET", "/cli", {"help": ""})
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["kind"], "group")

    def test_bad_help_value(self) -> None:
        status, body = self.call("GET", "/cli", {"help": "yes"})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_param")

    def test_execute_read(self) -> None:
        status, body = self.call("GET", "/cli/note/list", {"status": "active"})
        self.assertEqual(status, 200)
        self.assertIn("data", body)
        self.assertIn("meta", body)
        self.assertTrue(all(n["status"] == "active" for n in body["data"]))

    def test_projection(self) -> None:
        status, body = self.call("GET", "/cli/note/list", {"fields": "id,title"})
        self.assertEqual(status, 200)
        for n in body["data"]:
            self.assertEqual(set(n), {"id", "title"})

    def test_invalid_enum(self) -> None:
        status, body = self.call("GET", "/cli/note/list", {"status": "open"})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_param")
        self.assertIn("active", body["error"]["hint"])

    def test_missing_required(self) -> None:
        status, body = self.call("GET", "/cli/note/get", {})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "missing_param")

    def test_unknown_command_hint(self) -> None:
        status, body = self.call("GET", "/cli/nope")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "unknown_command")
        self.assertIn("help", body["error"]["hint"])

    def test_method_not_allowed(self) -> None:
        status, body = self.call("DELETE", "/cli/note/list")
        self.assertEqual(status, 405)
        self.assertEqual(body["error"]["code"], "method_not_allowed")

    def test_write_then_read(self) -> None:
        status, body = self.call("POST", "/cli/note/create", body={"title": "T1"})
        self.assertEqual(status, 200)
        nid = body["data"]["id"]
        status, body = self.call("GET", "/cli/note/get", {"id": nid, "fields": "id,title"})
        self.assertEqual(status, 200)
        self.assertEqual(body["data"], {"id": nid, "title": "T1"})

    def test_trailing_slash_equivalent(self) -> None:
        s1, _ = self.call("GET", "/cli/note/list/", {"help": "1"})
        s2, _ = self.call("GET", "/cli/note/list", {"help": "1"})
        self.assertEqual(s1, s2)

    def test_outside_base(self) -> None:
        status, body = self.call("GET", "/other")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "unknown_command")

    def test_error_envelope_has_no_data(self) -> None:
        _, body = self.call("GET", "/cli/note/list", {"status": "x"})
        self.assertNotIn("data", body)
        self.assertIn("error", body)

    # -- standard version surface --------------------------------------

    def test_version_current(self) -> None:
        status, body = self.call("GET", "/cli/version/current", {})
        self.assertEqual(status, 200)
        d = body["data"]
        self.assertEqual(d["protocol_version"], "1.0.0")
        self.assertEqual(d["server_version"], "0.2.0")
        self.assertIn("released_at", d)

    def test_version_agrees_with_root_help(self) -> None:
        _, root = self.call("GET", "/cli", {"help": "1"})
        _, cur = self.call("GET", "/cli/version/current", {})
        self.assertEqual(root["data"]["protocol_version"], cur["data"]["protocol_version"])
        self.assertEqual(root["data"]["server_version"], cur["data"]["server_version"])

    def test_releases_newest_first(self) -> None:
        status, body = self.call("GET", "/cli/version/releases", {})
        self.assertEqual(status, 200)
        versions = [r["version"] for r in body["data"]]
        self.assertEqual(versions, ["0.2.0", "0.1.0"])
        self.assertEqual(body["data"][0]["version"], "0.2.0")

    def test_releases_since_filters(self) -> None:
        _, body = self.call("GET", "/cli/version/releases", {"since": "0.1.0"})
        self.assertEqual([r["version"] for r in body["data"]], ["0.2.0"])

    def test_releases_since_current_is_empty(self) -> None:
        _, body = self.call("GET", "/cli/version/releases", {"since": "0.2.0"})
        self.assertEqual(body["data"], [])

    def test_releases_since_uncomparable_returns_all(self) -> None:
        _, body = self.call("GET", "/cli/version/releases", {"since": "not-a-version"})
        self.assertEqual(len(body["data"]), 2)

    def test_releases_since_older_all(self) -> None:
        _, body = self.call("GET", "/cli/version/releases", {"since": "0.0.1"})
        self.assertEqual(len(body["data"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
