import pytest
from conftest import ItemFactory, ItemTypeFactory, CustomFieldDefinitionFactory
from apps.items.models import CustomFieldValue
from apps.relations.models import RelationType, ItemRelation
from apps.matrices.models import MatrixAnnotation


URL = "/api/v1/tables/"


def _seed_source(item_type_id, name="seed"):
    return {"name": name, "kind": "seed", "seed_item_type": str(item_type_id)}


def _display_col(heading, source):
    return {"heading": heading, "source": source}


def _create_matrix_with_annotation(client, item_type, annotation_name="notes"):
    """Helper: create a matrix with seed + annotation source."""
    r = client.post(URL, {
        "name": "Ann Matrix",
        "sources": [
            _seed_source(item_type.id),
            {"name": annotation_name, "kind": "annotation"},
        ],
        "columns": [
            _display_col("Items", "seed"),
            _display_col("Notes", annotation_name),
        ],
    }, format="json")
    assert r.status_code == 201, r.data
    return r.data["id"]


class TestAnnotationColumnCRUD:
    def test_create_matrix_with_annotation_source(self, editor_client, item_type):
        matrix_id = _create_matrix_with_annotation(editor_client, item_type)
        r = editor_client.get(f"{URL}{matrix_id}/")
        assert r.status_code == 200
        sources = r.data["sources"]
        ann_src = next(s for s in sources if s["kind"] == "annotation")
        assert ann_src["name"] == "notes"

    def test_data_includes_annotation_cells(self, editor_client, item_type, editor_user):
        ItemFactory(item_type=item_type, created_by=editor_user, title="Item A")
        matrix_id = _create_matrix_with_annotation(editor_client, item_type)
        r = editor_client.get(f"{URL}{matrix_id}/data/")
        assert r.status_code == 200
        row = r.data["rows"][0]
        ann_cell = row[1]  # annotation column is at position 1
        assert ann_cell["annotation"] is True
        assert ann_cell["value"] == ""
        assert "row_hash" in ann_cell
        assert ann_cell["column_slug"] == "notes"

    def test_columns_response_includes_slug(self, editor_client, item_type, editor_user):
        ItemFactory(item_type=item_type, created_by=editor_user)
        matrix_id = _create_matrix_with_annotation(editor_client, item_type)
        r = editor_client.get(f"{URL}{matrix_id}/data/")
        cols = r.data["columns"]
        ann_col = next(c for c in cols if c["kind"] == "annotation")
        assert ann_col["slug"] == "notes"


class TestAnnotatePatchEndpoint:
    def test_patch_annotation_persists_value(self, editor_client, item_type, editor_user):
        ItemFactory(item_type=item_type, created_by=editor_user, title="Item A")
        matrix_id = _create_matrix_with_annotation(editor_client, item_type)

        # Get the row_hash from the data endpoint
        r = editor_client.get(f"{URL}{matrix_id}/data/")
        row_hash = r.data["rows"][0][1]["row_hash"]

        # PATCH annotation
        r = editor_client.patch(f"{URL}{matrix_id}/annotate/", {
            "column_slug": "notes",
            "row_hash": row_hash,
            "value": "This is a note",
        }, format="json")
        assert r.status_code == 200
        assert r.data["value"] == "This is a note"

        # Fetch data again — value should appear
        r = editor_client.get(f"{URL}{matrix_id}/data/")
        ann_cell = r.data["rows"][0][1]
        assert ann_cell["value"] == "This is a note"

    def test_patch_annotation_upsert(self, editor_client, item_type, editor_user):
        ItemFactory(item_type=item_type, created_by=editor_user, title="Item A")
        matrix_id = _create_matrix_with_annotation(editor_client, item_type)

        r = editor_client.get(f"{URL}{matrix_id}/data/")
        row_hash = r.data["rows"][0][1]["row_hash"]

        editor_client.patch(f"{URL}{matrix_id}/annotate/", {
            "column_slug": "notes", "row_hash": row_hash, "value": "first",
        }, format="json")
        editor_client.patch(f"{URL}{matrix_id}/annotate/", {
            "column_slug": "notes", "row_hash": row_hash, "value": "updated",
        }, format="json")

        assert MatrixAnnotation.objects.filter(matrix_id=matrix_id).count() == 1
        ann = MatrixAnnotation.objects.get(matrix_id=matrix_id)
        assert ann.value == "updated"

    def test_viewer_cannot_annotate(self, viewer_client, editor_client, item_type, editor_user):
        ItemFactory(item_type=item_type, created_by=editor_user)
        matrix_id = _create_matrix_with_annotation(editor_client, item_type)
        r = editor_client.get(f"{URL}{matrix_id}/data/")
        row_hash = r.data["rows"][0][1]["row_hash"]

        r = viewer_client.patch(f"{URL}{matrix_id}/annotate/", {
            "column_slug": "notes", "row_hash": row_hash, "value": "nope",
        }, format="json")
        assert r.status_code == 403

    def test_patch_unknown_slug_returns_400(self, editor_client, item_type, editor_user):
        ItemFactory(item_type=item_type, created_by=editor_user)
        matrix_id = _create_matrix_with_annotation(editor_client, item_type)
        r = editor_client.patch(f"{URL}{matrix_id}/annotate/", {
            "column_slug": "nonexistent",
            "row_hash": "abc123",
            "value": "test",
        }, format="json")
        assert r.status_code == 400

    def test_row_hash_stable_for_same_row(self, editor_client, item_type, editor_user):
        ItemFactory(item_type=item_type, created_by=editor_user, title="Stable")
        matrix_id = _create_matrix_with_annotation(editor_client, item_type)

        r1 = editor_client.get(f"{URL}{matrix_id}/data/")
        r2 = editor_client.get(f"{URL}{matrix_id}/data/")
        assert r1.data["rows"][0][1]["row_hash"] == r2.data["rows"][0][1]["row_hash"]


class TestItemFieldColumn:
    def test_item_field_source_reads_custom_field(
        self, editor_client, item_type, editor_user, vault
    ):
        field = CustomFieldDefinitionFactory(
            item_type=item_type, slug="priority", field_kind="integer"
        )
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        CustomFieldValue.objects.create(item=item, field_definition=field, value=42)

        r = editor_client.post(URL, {
            "name": "Item Field Matrix",
            "sources": [
                _seed_source(item_type.id),
                {
                    "name": "prio",
                    "kind": "item_field",
                    "field_slug": "priority",
                    "source_ref": "seed",
                },
            ],
            "columns": [
                _display_col("Items", "seed"),
                _display_col("Priority", "prio"),
            ],
        }, format="json")
        assert r.status_code == 201, r.data
        matrix_id = r.data["id"]

        r = editor_client.get(f"{URL}{matrix_id}/data/")
        assert r.status_code == 200
        cell = r.data["rows"][0][1]
        assert cell["item_field"] is True
        assert cell["value"] == 42

    def test_item_field_requires_field_slug(self, editor_client, item_type):
        r = editor_client.post(URL, {
            "name": "Bad",
            "sources": [
                _seed_source(item_type.id),
                {
                    "name": "prio",
                    "kind": "item_field",
                    "source_ref": "seed",
                    # field_slug missing
                },
            ],
            "columns": [_display_col("Items", "seed")],
        }, format="json")
        assert r.status_code == 400

    def test_item_field_requires_source_ref(self, editor_client, item_type):
        r = editor_client.post(URL, {
            "name": "Bad",
            "sources": [
                _seed_source(item_type.id),
                {
                    "name": "prio",
                    "kind": "item_field",
                    "field_slug": "priority",
                    # source_ref missing
                },
            ],
            "columns": [_display_col("Items", "seed")],
        }, format="json")
        assert r.status_code == 400

    def test_item_field_invalid_source_ref(self, editor_client, item_type):
        r = editor_client.post(URL, {
            "name": "Bad",
            "sources": [
                _seed_source(item_type.id),
                {
                    "name": "prio",
                    "kind": "item_field",
                    "field_slug": "priority",
                    "source_ref": "nonexistent",
                },
            ],
            "columns": [_display_col("Items", "seed")],
        }, format="json")
        assert r.status_code == 400
