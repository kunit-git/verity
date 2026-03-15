import pytest
from conftest import ItemTypeFactory, ItemFactory
from apps.relations.models import RelationType


URL = "/api/v1/tables/"


class TestMatrixCreate:
    def test_create_with_seed_column(self, editor_client, item_type, vault):
        r = editor_client.post(URL, {
            "name": "Test Matrix",
            "columns": [{
                "position": 0,
                "label": "Requirements",
                "column_kind": "seed",
                "seed_item_type": str(item_type.id),
            }],
        }, format="json")
        assert r.status_code == 201
        assert r.data["name"] == "Test Matrix"
        assert len(r.data["columns"]) == 1

    def test_create_with_traversal_column(self, editor_client, item_type, vault):
        trace = RelationType.objects.get(vault=vault, kind="trace")
        r = editor_client.post(URL, {
            "name": "Traversal Matrix",
            "columns": [
                {
                    "position": 0, "label": "Seed", "column_kind": "seed",
                    "seed_item_type": str(item_type.id),
                },
                {
                    "position": 1, "label": "Traces", "column_kind": "traversal",
                    "relation_type": str(trace.id), "direction": "outgoing",
                },
            ],
        }, format="json")
        assert r.status_code == 201
        assert len(r.data["columns"]) == 2

    def test_create_with_formula_column(self, editor_client, item_type, vault):
        r = editor_client.post(URL, {
            "name": "Formula Matrix",
            "columns": [
                {
                    "position": 0, "label": "Seed", "column_kind": "seed",
                    "seed_item_type": str(item_type.id),
                },
                {
                    "position": 1, "label": "Calc", "column_kind": "formula",
                    "formula": "$1.weight + 10",
                },
            ],
        }, format="json")
        assert r.status_code == 201

    def test_seed_not_at_position_zero(self, editor_client, item_type, vault):
        trace = RelationType.objects.get(vault=vault, kind="trace")
        r = editor_client.post(URL, {
            "name": "Bad",
            "columns": [{
                "position": 1, "label": "Wrong", "column_kind": "seed",
                "seed_item_type": str(item_type.id),
            }],
        }, format="json")
        assert r.status_code == 400

    def test_seed_without_item_type(self, editor_client, vault):
        r = editor_client.post(URL, {
            "name": "Bad",
            "columns": [{
                "position": 0, "label": "Missing", "column_kind": "seed",
            }],
        }, format="json")
        assert r.status_code == 400

    def test_traversal_without_relation_type(self, editor_client, item_type, vault):
        r = editor_client.post(URL, {
            "name": "Bad",
            "columns": [
                {"position": 0, "label": "Seed", "column_kind": "seed", "seed_item_type": str(item_type.id)},
                {"position": 1, "label": "Missing", "column_kind": "traversal", "direction": "outgoing"},
            ],
        }, format="json")
        assert r.status_code == 400

    def test_traversal_without_direction(self, editor_client, item_type, vault):
        trace = RelationType.objects.get(vault=vault, kind="trace")
        r = editor_client.post(URL, {
            "name": "Bad",
            "columns": [
                {"position": 0, "label": "Seed", "column_kind": "seed", "seed_item_type": str(item_type.id)},
                {"position": 1, "label": "Missing", "column_kind": "traversal", "relation_type": str(trace.id)},
            ],
        }, format="json")
        assert r.status_code == 400

    def test_formula_without_formula(self, editor_client, item_type, vault):
        r = editor_client.post(URL, {
            "name": "Bad",
            "columns": [
                {"position": 0, "label": "Seed", "column_kind": "seed", "seed_item_type": str(item_type.id)},
                {"position": 1, "label": "No Formula", "column_kind": "formula"},
            ],
        }, format="json")
        assert r.status_code == 400

    def test_invalid_formula_syntax(self, editor_client, item_type, vault):
        r = editor_client.post(URL, {
            "name": "Bad",
            "columns": [
                {"position": 0, "label": "Seed", "column_kind": "seed", "seed_item_type": str(item_type.id)},
                {"position": 1, "label": "Bad Formula", "column_kind": "formula", "formula": "@invalid@"},
            ],
        }, format="json")
        assert r.status_code == 400

    def test_seed_with_formula(self, editor_client, item_type, vault):
        r = editor_client.post(URL, {
            "name": "Bad",
            "columns": [{
                "position": 0, "label": "Seed", "column_kind": "seed",
                "seed_item_type": str(item_type.id), "formula": "$1.a",
            }],
        }, format="json")
        assert r.status_code == 400

    def test_viewer_forbidden(self, viewer_client, item_type, vault):
        r = viewer_client.post(URL, {
            "name": "Nope",
            "columns": [{
                "position": 0, "label": "Seed", "column_kind": "seed",
                "seed_item_type": str(item_type.id),
            }],
        }, format="json")
        assert r.status_code == 403


class TestMatrixUpdate:
    def test_patch_replaces_columns(self, editor_client, item_type, vault):
        r = editor_client.post(URL, {
            "name": "Update Me",
            "columns": [{
                "position": 0, "label": "Seed", "column_kind": "seed",
                "seed_item_type": str(item_type.id),
            }],
        }, format="json")
        matrix_id = r.data["id"]
        r = editor_client.patch(f"{URL}{matrix_id}/", {
            "name": "Updated",
            "columns": [{
                "position": 0, "label": "New Seed", "column_kind": "seed",
                "seed_item_type": str(item_type.id),
            }],
        }, format="json")
        assert r.status_code == 200
        assert r.data["name"] == "Updated"
        assert r.data["columns"][0]["label"] == "New Seed"


class TestMatrixDelete:
    def test_delete(self, editor_client, item_type, vault):
        r = editor_client.post(URL, {
            "name": "Delete Me",
            "columns": [{
                "position": 0, "label": "Seed", "column_kind": "seed",
                "seed_item_type": str(item_type.id),
            }],
        }, format="json")
        matrix_id = r.data["id"]
        r = editor_client.delete(f"{URL}{matrix_id}/")
        assert r.status_code == 204
