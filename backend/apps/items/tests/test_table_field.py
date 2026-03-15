import pytest
from conftest import CustomFieldDefinitionFactory, ItemFactory, ItemTypeFactory
from apps.relations.models import RelationType, ItemRelation
from apps.items.models import CustomFieldValue, ItemTableAnnotation


FIELD_URL = "/api/v1/item-types/{type_id}/custom-fields/"
ITEMS_URL = "/api/v1/items/"


def _table_options(relation_type_id, direction="outgoing"):
    return {
        "columns": [
            {
                "name": "linked",
                "kind": "traversal",
                "relation_type_id": str(relation_type_id),
                "direction": direction,
                "label": "Linked Items",
            },
            {
                "name": "notes",
                "kind": "annotation",
                "slug": "notes",
                "label": "Notes",
            },
        ]
    }


class TestTableFieldDefinition:
    def test_create_table_field_succeeds(self, editor_client, item_type, vault):
        trace = RelationType.objects.get(vault=vault, kind="trace")
        r = editor_client.post(FIELD_URL.format(type_id=item_type.id), {
            "name": "Related Items",
            "slug": "related-items",
            "field_kind": "table",
            "display_order": 0,
            "options": _table_options(trace.id),
        }, format="json")
        assert r.status_code == 201, r.data
        assert r.data["field_kind"] == "table"

    def test_table_field_requires_columns(self, editor_client, item_type):
        r = editor_client.post(FIELD_URL.format(type_id=item_type.id), {
            "name": "Empty Table",
            "slug": "empty-table",
            "field_kind": "table",
            "display_order": 0,
            "options": {},
        }, format="json")
        assert r.status_code == 400

    def test_table_field_first_column_must_be_traversal(self, editor_client, item_type):
        r = editor_client.post(FIELD_URL.format(type_id=item_type.id), {
            "name": "Bad Table",
            "slug": "bad-table",
            "field_kind": "table",
            "display_order": 0,
            "options": {
                "columns": [
                    {"name": "notes", "kind": "annotation", "slug": "notes", "label": "Notes"},
                ]
            },
        }, format="json")
        assert r.status_code == 400

    def test_traversal_column_requires_relation_type_id(self, editor_client, item_type):
        r = editor_client.post(FIELD_URL.format(type_id=item_type.id), {
            "name": "Bad Traversal",
            "slug": "bad-traversal",
            "field_kind": "table",
            "display_order": 0,
            "options": {
                "columns": [
                    {"name": "linked", "kind": "traversal", "direction": "outgoing", "label": "Items"},
                ]
            },
        }, format="json")
        assert r.status_code == 400

    def test_annotation_column_requires_slug(self, editor_client, item_type, vault):
        trace = RelationType.objects.get(vault=vault, kind="trace")
        r = editor_client.post(FIELD_URL.format(type_id=item_type.id), {
            "name": "Bad Annotation",
            "slug": "bad-annotation",
            "field_kind": "table",
            "display_order": 0,
            "options": {
                "columns": [
                    {"name": "linked", "kind": "traversal", "relation_type_id": str(trace.id), "direction": "outgoing", "label": "Items"},
                    {"name": "notes", "kind": "annotation", "label": "Notes"},  # slug missing
                ]
            },
        }, format="json")
        assert r.status_code == 400

    def test_column_name_required(self, editor_client, item_type, vault):
        trace = RelationType.objects.get(vault=vault, kind="trace")
        r = editor_client.post(FIELD_URL.format(type_id=item_type.id), {
            "name": "No Name",
            "slug": "no-name",
            "field_kind": "table",
            "display_order": 0,
            "options": {
                "columns": [
                    {"kind": "traversal", "relation_type_id": str(trace.id), "direction": "outgoing", "label": "Items"},
                ]
            },
        }, format="json")
        assert r.status_code == 400

    def test_column_names_must_be_unique(self, editor_client, item_type, vault):
        trace = RelationType.objects.get(vault=vault, kind="trace")
        r = editor_client.post(FIELD_URL.format(type_id=item_type.id), {
            "name": "Dup Names",
            "slug": "dup-names",
            "field_kind": "table",
            "display_order": 0,
            "options": {
                "columns": [
                    {"name": "col", "kind": "traversal", "relation_type_id": str(trace.id), "direction": "outgoing", "label": "Items"},
                    {"name": "col", "kind": "annotation", "slug": "notes", "label": "Notes"},
                ]
            },
        }, format="json")
        assert r.status_code == 400

    def test_table_field_excluded_from_custom_fields_dict(
        self, editor_client, item_type, editor_user, vault
    ):
        """Table field should not appear in the item's custom_fields dict."""
        trace = RelationType.objects.get(vault=vault, kind="trace")
        CustomFieldDefinitionFactory(
            item_type=item_type, slug="related", field_kind="table",
            options=_table_options(trace.id)
        )
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.get(f"{ITEMS_URL}{item.id}/")
        assert r.status_code == 200
        assert "related" not in r.data["custom_fields"]

    def test_table_field_not_in_version_snapshot(
        self, editor_client, item_type, editor_user, vault
    ):
        """Table fields are NOT included in ItemVersion snapshots."""
        from apps.items.models import ItemVersion
        trace = RelationType.objects.get(vault=vault, kind="trace")
        CustomFieldDefinitionFactory(
            item_type=item_type, slug="related", field_kind="table",
            options=_table_options(trace.id)
        )
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        editor_client.patch(f"{ITEMS_URL}{item.id}/", {"title": "Updated"}, format="json")
        item.refresh_from_db()
        snapshot = ItemVersion.objects.get(item=item, version_number=1)
        assert "related" not in snapshot.custom_fields_snapshot


class TestTableFieldData:
    def _setup(self, editor_client, item_type, editor_user, vault):
        trace = RelationType.objects.get(vault=vault, kind="trace")
        field_def = CustomFieldDefinitionFactory(
            item_type=item_type, slug="linked",
            field_kind="table", options=_table_options(trace.id)
        )
        parent = ItemFactory(item_type=item_type, created_by=editor_user, title="Parent")
        child = ItemFactory(item_type=item_type, created_by=editor_user, title="Child")
        ItemRelation(
            relation_type=trace, source=parent, target=child, created_by=editor_user
        ).save()
        return parent, child, field_def, trace

    def test_data_returns_linked_items(self, editor_client, item_type, editor_user, vault):
        parent, child, _, _ = self._setup(editor_client, item_type, editor_user, vault)
        r = editor_client.get(f"{ITEMS_URL}{parent.id}/table-field/linked/data/")
        assert r.status_code == 200
        assert len(r.data["rows"]) == 1
        traversal_cell = r.data["rows"][0][0]
        assert traversal_cell["id"] == str(child.id)

    def test_data_includes_annotation_cells(self, editor_client, item_type, editor_user, vault):
        parent, child, _, _ = self._setup(editor_client, item_type, editor_user, vault)
        r = editor_client.get(f"{ITEMS_URL}{parent.id}/table-field/linked/data/")
        assert r.status_code == 200
        ann_cell = r.data["rows"][0][1]
        assert ann_cell["annotation"] is True
        assert ann_cell["value"] == ""
        assert "row_hash" in ann_cell

    def test_data_404_for_nonexistent_field(self, editor_client, item_type, editor_user):
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.get(f"{ITEMS_URL}{item.id}/table-field/nonexistent/data/")
        assert r.status_code == 404

    def test_data_empty_when_no_relations(self, editor_client, item_type, editor_user, vault):
        trace = RelationType.objects.get(vault=vault, kind="trace")
        CustomFieldDefinitionFactory(
            item_type=item_type, slug="linked", field_kind="table",
            options=_table_options(trace.id)
        )
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.get(f"{ITEMS_URL}{item.id}/table-field/linked/data/")
        assert r.status_code == 200
        assert r.data["rows"] == []

    def test_viewer_can_read_data(self, viewer_client, editor_client, item_type, editor_user, vault):
        parent, _, _, _ = self._setup(editor_client, item_type, editor_user, vault)
        r = viewer_client.get(f"{ITEMS_URL}{parent.id}/table-field/linked/data/")
        assert r.status_code == 200


class TestTableFieldAnnotate:
    def _setup(self, editor_client, item_type, editor_user, vault):
        trace = RelationType.objects.get(vault=vault, kind="trace")
        field_def = CustomFieldDefinitionFactory(
            item_type=item_type, slug="linked",
            field_kind="table", options=_table_options(trace.id)
        )
        parent = ItemFactory(item_type=item_type, created_by=editor_user)
        child = ItemFactory(item_type=item_type, created_by=editor_user)
        ItemRelation(
            relation_type=trace, source=parent, target=child, created_by=editor_user
        ).save()
        return parent, child, field_def

    def test_annotate_persists_value(self, editor_client, item_type, editor_user, vault):
        parent, child, _ = self._setup(editor_client, item_type, editor_user, vault)
        r = editor_client.get(f"{ITEMS_URL}{parent.id}/table-field/linked/data/")
        row_hash = r.data["rows"][0][1]["row_hash"]

        r = editor_client.patch(f"{ITEMS_URL}{parent.id}/table-field/linked/annotate/", {
            "column_slug": "notes",
            "row_hash": row_hash,
            "value": "Important note",
        }, format="json")
        assert r.status_code == 200
        assert r.data["value"] == "Important note"

        # Data endpoint should now return the annotation
        r = editor_client.get(f"{ITEMS_URL}{parent.id}/table-field/linked/data/")
        assert r.data["rows"][0][1]["value"] == "Important note"

    def test_annotate_upsert(self, editor_client, item_type, editor_user, vault):
        parent, child, _ = self._setup(editor_client, item_type, editor_user, vault)
        r = editor_client.get(f"{ITEMS_URL}{parent.id}/table-field/linked/data/")
        row_hash = r.data["rows"][0][1]["row_hash"]

        editor_client.patch(f"{ITEMS_URL}{parent.id}/table-field/linked/annotate/", {
            "column_slug": "notes", "row_hash": row_hash, "value": "first",
        }, format="json")
        editor_client.patch(f"{ITEMS_URL}{parent.id}/table-field/linked/annotate/", {
            "column_slug": "notes", "row_hash": row_hash, "value": "second",
        }, format="json")

        assert ItemTableAnnotation.objects.filter(item=parent).count() == 1
        assert ItemTableAnnotation.objects.get(item=parent).value == "second"

    def test_viewer_cannot_annotate(self, viewer_client, editor_client, item_type, editor_user, vault):
        parent, _, _ = self._setup(editor_client, item_type, editor_user, vault)
        r = editor_client.get(f"{ITEMS_URL}{parent.id}/table-field/linked/data/")
        row_hash = r.data["rows"][0][1]["row_hash"]

        r = viewer_client.patch(f"{ITEMS_URL}{parent.id}/table-field/linked/annotate/", {
            "column_slug": "notes", "row_hash": row_hash, "value": "nope",
        }, format="json")
        assert r.status_code == 403

    def test_annotate_unknown_column_slug_returns_400(
        self, editor_client, item_type, editor_user, vault
    ):
        parent, _, _ = self._setup(editor_client, item_type, editor_user, vault)
        r = editor_client.patch(f"{ITEMS_URL}{parent.id}/table-field/linked/annotate/", {
            "column_slug": "nonexistent", "row_hash": "abc123", "value": "test",
        }, format="json")
        assert r.status_code == 400
