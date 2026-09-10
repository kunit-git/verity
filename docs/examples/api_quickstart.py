#!/usr/bin/env python3
"""Create synthetic API examples in a NEW vault; leaves that vault selected."""
import argparse
import getpass
import json
import sys
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def run(base_url, username, password):
    token = None

    def request(method, path, payload=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        body = None if payload is None else json.dumps(payload).encode()
        with urlopen(Request(base_url.rstrip("/") + path, data=body,
                             headers=headers, method=method), timeout=30) as response:
            return json.load(response)

    token = request("POST", "/auth/login/", {"username": username, "password": password})["access"]
    me = request("GET", "/auth/me/")
    if not me["is_site_admin"]:
        raise ValueError("This demonstration requires a site-admin evaluation account.")

    suffix = uuid.uuid4().hex[:8]
    vault = request("POST", "/vaults/", {"name": f"API example {suffix}", "slug": f"api-example-{suffix}"})
    request("POST", "/vaults/select/", {"vault_id": vault["id"]})
    requirement_type = request("POST", "/item-types/", {"name": "Requirement", "slug": "requirement"})
    request("POST", f"/item-types/{requirement_type['id']}/custom-fields/", {
        "name": "Priority", "slug": "priority", "field_kind": "integer", "options": {},
    })
    test_type = request("POST", "/item-types/", {"name": "Test Case", "slug": "test-case"})
    requirement = request("POST", "/items/", {
        "item_type": requirement_type["id"], "title": "The system shall record sign-in events",
        "status": "draft", "custom_fields": {"priority": 2},
    })
    test_case = request("POST", "/items/", {
        "item_type": test_type["id"], "title": "Verify a sign-in creates an event", "status": "draft",
    })
    types = request("GET", "/relation-types/")["results"]
    trace_type = next(row for row in types if row["name"] == "traces_to")
    request("POST", "/relations/", {"relation_type": trace_type["id"], "source": requirement["id"], "target": test_case["id"]})
    table = request("POST", "/tables/", {
        "name": "Requirements and tests",
        "sources": [
            {"name": "requirements", "kind": "seed", "seed_item_type": requirement_type["id"]},
            {"name": "tests", "kind": "traversal", "relation_type": trace_type["id"], "direction": "outgoing"},
        ],
        "columns": [{"heading": "Requirement", "source": "requirements"}, {"heading": "Test case", "source": "tests"}],
    })
    data = request("GET", f"/tables/{table['id']}/data/")
    assert any(row[0] and row[1] and row[0]["id"] == requirement["id"]
               and row[1]["id"] == test_case["id"] for row in data["rows"])
    print(f"Created {vault['name']} ({vault['id']}); the account now has this vault selected.")
    print(f"Created and verified table {table['id']} with {len(data['rows'])} row(s).")
    return vault["id"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000/api/v1")
    parser.add_argument("--username", default="admin")
    args = parser.parse_args()
    try:
        run(args.base_url, args.username, getpass.getpass("Evaluation account password: "))
    except HTTPError as exc:
        print(f"API returned HTTP {exc.code}; check credentials, role, and server logs.", file=sys.stderr)
        return 1
    except (URLError, ValueError, AssertionError) as exc:
        print(f"Example failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
