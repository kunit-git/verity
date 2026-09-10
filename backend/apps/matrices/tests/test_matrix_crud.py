import pytest
from conftest import ItemTypeFactory, ItemFactory, RelationTypeFactory
from apps.relations.models import RelationType


URL = "/api/v1/tables/"


def _seed_source(item_type_id, name="seed"):
    return {"name": name, "kind": "seed", "seed_item_type": str(item_type_id)}


def _traversal_source(relation_type_id, direction="outgoing", name="linked"):
    return {
        "name": name,
        "kind": "traversal",
        "relation_type": str(relation_type_id),
        "direction": direction,
    }


def _display_col(heading, source):
    return {"heading": heading, "source": source}


class TestMatrixCreate:
    @pytest.mark.parametrize("field", ["seed_item_type", "seed_container", "relation_type"])
    @pytest.mark.parametrize("missing", [False, True])
    def test_rejects_foreign_or_missing_references(self, editor_client, item_type, field, missing):
        from uuid import uuid4
        from apps.matrices.models import Matrix

        foreign = {
            "seed_item_type": ItemTypeFactory,
            "seed_container": ItemFactory,
            "relation_type": RelationTypeFactory,
        }
        reference = uuid4() if missing else foreign[field]().pk
        seed = _seed_source(item_type.id)
        sources = [seed]
        if field == "relation_type":
            sources.append(_traversal_source(reference))
        else:
            seed[field] = str(reference)
        count = Matrix.objects.count()
        response = editor_client.post(URL, {
            "name": "Invalid references", "sources": sources,
            "columns": [_display_col("Items", "seed")],
        }, format="json")
        assert response.status_code == 400
        assert Matrix.objects.count() == count

    def test_invalid_update_preserves_existing_sources(self, editor_client, item_type):
        from apps.matrices.models import Matrix

        payload = {"name": "Original", "sources": [_seed_source(item_type.id)],
                   "columns": [_display_col("Items", "seed")]}
        created = editor_client.post(URL, payload, format="json")
        matrix = Matrix.objects.get(pk=created.data["id"])
        source_ids = list(matrix.sources.values_list("id", flat=True))
        payload["name"] = "Changed"
        payload["sources"] = [_seed_source(ItemTypeFactory().pk)]
        response = editor_client.put(f"{URL}{matrix.pk}/", payload, format="json")
        assert response.status_code == 400
        matrix.refresh_from_db()
        assert matrix.name == "Original"
        assert list(matrix.sources.values_list("id", flat=True)) == source_ids

    def test_create_with_seed_source(self, editor_client, item_type, vault):
        r = editor_client.post(URL, {
            "name": "Test Matrix",
            "sources": [_seed_source(item_type.id)],
            "columns": [_display_col("Requirements", "seed")],
        }, format="json")
        assert r.status_code == 201
        assert r.data["name"] == "Test Matrix"
        assert len(r.data["sources"]) == 1
        assert len(r.data["columns"]) == 1

    def test_create_with_traversal_source(self, editor_client, item_type, vault):
        trace = RelationType.objects.get(vault=vault, kind="trace")
        r = editor_client.post(URL, {
            "name": "Traversal Matrix",
            "sources": [
                _seed_source(item_type.id),
                _traversal_source(trace.id),
            ],
            "columns": [
                _display_col("Seed", "seed"),
                _display_col("Linked", "linked"),
            ],
        }, format="json")
        assert r.status_code == 201
        assert len(r.data["sources"]) == 2
        assert len(r.data["columns"]) == 2

    def test_create_with_formula_source(self, editor_client, item_type, vault):
        r = editor_client.post(URL, {
            "name": "Formula Matrix",
            "sources": [
                _seed_source(item_type.id),
                {"name": "calc", "kind": "formula", "formula": "$seed.weight + 10"},
            ],
            "columns": [
                _display_col("Items", "seed"),
                _display_col("Calc", "calc"),
            ],
        }, format="json")
        assert r.status_code == 201

    def test_first_source_must_be_seed(self, editor_client, item_type, vault):
        trace = RelationType.objects.get(vault=vault, kind="trace")
        r = editor_client.post(URL, {
            "name": "Bad",
            "sources": [_traversal_source(trace.id)],
            "columns": [_display_col("Items", "linked")],
        }, format="json")
        assert r.status_code == 400

    def test_seed_without_item_type(self, editor_client, vault):
        r = editor_client.post(URL, {
            "name": "Bad",
            "sources": [{"name": "seed", "kind": "seed"}],
            "columns": [_display_col("Items", "seed")],
        }, format="json")
        assert r.status_code == 400

    def test_traversal_without_relation_type(self, editor_client, item_type, vault):
        r = editor_client.post(URL, {
            "name": "Bad",
            "sources": [
                _seed_source(item_type.id),
                {"name": "linked", "kind": "traversal", "direction": "outgoing"},
            ],
            "columns": [_display_col("Items", "seed")],
        }, format="json")
        assert r.status_code == 400

    def test_traversal_without_direction(self, editor_client, item_type, vault):
        trace = RelationType.objects.get(vault=vault, kind="trace")
        r = editor_client.post(URL, {
            "name": "Bad",
            "sources": [
                _seed_source(item_type.id),
                {"name": "linked", "kind": "traversal", "relation_type": str(trace.id)},
            ],
            "columns": [_display_col("Items", "seed")],
        }, format="json")
        assert r.status_code == 400

    def test_formula_without_formula(self, editor_client, item_type, vault):
        r = editor_client.post(URL, {
            "name": "Bad",
            "sources": [
                _seed_source(item_type.id),
                {"name": "calc", "kind": "formula"},
            ],
            "columns": [_display_col("Items", "seed")],
        }, format="json")
        assert r.status_code == 400

    def test_invalid_formula_syntax(self, editor_client, item_type, vault):
        r = editor_client.post(URL, {
            "name": "Bad",
            "sources": [
                _seed_source(item_type.id),
                {"name": "calc", "kind": "formula", "formula": "@invalid@"},
            ],
            "columns": [_display_col("Items", "seed")],
        }, format="json")
        assert r.status_code == 400

    def test_seed_with_formula(self, editor_client, item_type, vault):
        r = editor_client.post(URL, {
            "name": "Bad",
            "sources": [{
                "name": "seed", "kind": "seed",
                "seed_item_type": str(item_type.id), "formula": "$x.a",
            }],
            "columns": [_display_col("Items", "seed")],
        }, format="json")
        assert r.status_code == 400

    def test_viewer_forbidden(self, viewer_client, item_type, vault):
        r = viewer_client.post(URL, {
            "name": "Nope",
            "sources": [_seed_source(item_type.id)],
            "columns": [_display_col("Items", "seed")],
        }, format="json")
        assert r.status_code == 403

    def test_duplicate_source_names(self, editor_client, item_type, vault):
        r = editor_client.post(URL, {
            "name": "Bad",
            "sources": [
                _seed_source(item_type.id, name="dup"),
                {"name": "dup", "kind": "formula", "formula": "1 + 2"},
            ],
            "columns": [_display_col("Items", "dup")],
        }, format="json")
        assert r.status_code == 400

    def test_formula_references_unknown_source(self, editor_client, item_type, vault):
        r = editor_client.post(URL, {
            "name": "Bad",
            "sources": [
                _seed_source(item_type.id),
                {"name": "calc", "kind": "formula", "formula": "$nonexistent.weight + 1"},
            ],
            "columns": [_display_col("Items", "seed")],
        }, format="json")
        assert r.status_code == 400

    def test_display_column_references_unknown_source(self, editor_client, item_type, vault):
        r = editor_client.post(URL, {
            "name": "Bad",
            "sources": [_seed_source(item_type.id)],
            "columns": [_display_col("Items", "nonexistent")],
        }, format="json")
        assert r.status_code == 400


class TestMatrixUpdate:
    def test_patch_replaces_sources_and_columns(self, editor_client, item_type, vault):
        r = editor_client.post(URL, {
            "name": "Update Me",
            "sources": [_seed_source(item_type.id)],
            "columns": [_display_col("Items", "seed")],
        }, format="json")
        matrix_id = r.data["id"]
        r = editor_client.patch(f"{URL}{matrix_id}/", {
            "name": "Updated",
            "sources": [_seed_source(item_type.id, name="items")],
            "columns": [_display_col("New Items", "items")],
        }, format="json")
        assert r.status_code == 200
        assert r.data["name"] == "Updated"
        assert r.data["columns"][0]["heading"] == "New Items"


class TestMatrixDelete:
    def test_delete(self, editor_client, item_type, vault):
        r = editor_client.post(URL, {
            "name": "Delete Me",
            "sources": [_seed_source(item_type.id)],
            "columns": [_display_col("Items", "seed")],
        }, format="json")
        matrix_id = r.data["id"]
        r = editor_client.delete(f"{URL}{matrix_id}/")
        assert r.status_code == 204
