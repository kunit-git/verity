import pytest
from conftest import ItemFactory, ItemTypeFactory, CustomFieldDefinitionFactory
from apps.items.models import CustomFieldValue
from apps.relations.models import RelationType, ItemRelation


URL = "/api/v1/tables/"


def _seed_source(item_type_id, name="seed", container_id=None):
    src = {"name": name, "kind": "seed", "seed_item_type": str(item_type_id)}
    if container_id:
        src["seed_container"] = str(container_id)
    return src


def _traversal_source(relation_type_id, direction="outgoing", name="linked"):
    return {
        "name": name,
        "kind": "traversal",
        "relation_type": str(relation_type_id),
        "direction": direction,
    }


def _display_col(heading, source):
    return {"heading": heading, "source": source}


class TestMatrixData:
    def test_seed_column_returns_items(self, editor_client, item_type, editor_user, vault):
        ItemFactory(item_type=item_type, created_by=editor_user, title="A")
        ItemFactory(item_type=item_type, created_by=editor_user, title="B")
        r = editor_client.post(URL, {
            "name": "Seed Only",
            "sources": [_seed_source(item_type.id)],
            "columns": [_display_col("Items", "seed")],
        }, format="json")
        matrix_id = r.data["id"]
        r = editor_client.get(f"{URL}{matrix_id}/data/")
        assert r.status_code == 200
        assert len(r.data["rows"]) == 2
        assert len(r.data["columns"]) == 1

    def test_seed_container_filters(self, editor_client, item_type, editor_user, vault):
        comp = RelationType.objects.get(vault=vault, kind="composition")
        parent = ItemFactory(item_type=item_type, created_by=editor_user)
        child = ItemFactory(item_type=item_type, created_by=editor_user)
        other = ItemFactory(item_type=item_type, created_by=editor_user)
        ItemRelation(relation_type=comp, source=parent, target=child, created_by=editor_user).save()
        r = editor_client.post(URL, {
            "name": "Filtered",
            "sources": [_seed_source(item_type.id, container_id=parent.id)],
            "columns": [_display_col("Children", "seed")],
        }, format="json")
        matrix_id = r.data["id"]
        r = editor_client.get(f"{URL}{matrix_id}/data/")
        assert len(r.data["rows"]) == 1
        assert r.data["rows"][0][0]["id"] == str(child.id)

    def test_traversal_follows_relations(self, editor_client, vault, editor_user):
        type_a = ItemTypeFactory(vault=vault, slug="type-a-data")
        type_b = ItemTypeFactory(vault=vault, slug="type-b-data")
        trace = RelationType.objects.get(vault=vault, kind="trace")
        item_a = ItemFactory(item_type=type_a, created_by=editor_user)
        item_b = ItemFactory(item_type=type_b, created_by=editor_user)
        ItemRelation(relation_type=trace, source=item_a, target=item_b, created_by=editor_user).save()
        r = editor_client.post(URL, {
            "name": "Traverse",
            "sources": [
                _seed_source(type_a.id),
                _traversal_source(trace.id),
            ],
            "columns": [
                _display_col("Source", "seed"),
                _display_col("Target", "linked"),
            ],
        }, format="json")
        matrix_id = r.data["id"]
        r = editor_client.get(f"{URL}{matrix_id}/data/")
        assert len(r.data["rows"]) == 1
        assert r.data["rows"][0][1]["id"] == str(item_b.id)

    def test_no_match_returns_null(self, editor_client, vault, editor_user):
        type_a = ItemTypeFactory(vault=vault, slug="type-a-null")
        trace = RelationType.objects.get(vault=vault, kind="trace")
        ItemFactory(item_type=type_a, created_by=editor_user)
        r = editor_client.post(URL, {
            "name": "NoMatch",
            "sources": [
                _seed_source(type_a.id),
                _traversal_source(trace.id),
            ],
            "columns": [
                _display_col("Source", "seed"),
                _display_col("Target", "linked"),
            ],
        }, format="json")
        matrix_id = r.data["id"]
        r = editor_client.get(f"{URL}{matrix_id}/data/")
        assert r.data["rows"][0][1] is None

    def test_formula_evaluates(self, editor_client, vault, editor_user):
        item_type = ItemTypeFactory(vault=vault, slug="formula-eval-type")
        field = CustomFieldDefinitionFactory(
            item_type=item_type, slug="weight", field_kind="decimal",
        )
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        CustomFieldValue.objects.create(item=item, field_definition=field, value=5.0)
        r = editor_client.post(URL, {
            "name": "Formula",
            "sources": [
                _seed_source(item_type.id),
                {"name": "calc", "kind": "formula", "formula": "$seed.weight * 2"},
            ],
            "columns": [
                _display_col("Items", "seed"),
                _display_col("Double", "calc"),
            ],
        }, format="json")
        matrix_id = r.data["id"]
        r = editor_client.get(f"{URL}{matrix_id}/data/")
        assert r.data["rows"][0][1]["value"] == 10.0

    def test_formula_missing_field_null(self, editor_client, vault, editor_user):
        item_type = ItemTypeFactory(vault=vault, slug="formula-null-type")
        ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.post(URL, {
            "name": "NullFormula",
            "sources": [
                _seed_source(item_type.id),
                {"name": "calc", "kind": "formula", "formula": "$seed.nonexistent + 1"},
            ],
            "columns": [
                _display_col("Items", "seed"),
                _display_col("Missing", "calc"),
            ],
        }, format="json")
        matrix_id = r.data["id"]
        r = editor_client.get(f"{URL}{matrix_id}/data/")
        assert r.data["rows"][0][1] is None

    def test_formula_division_by_zero_null(self, editor_client, vault, editor_user):
        item_type = ItemTypeFactory(vault=vault, slug="formula-div0-type")
        field = CustomFieldDefinitionFactory(
            item_type=item_type, slug="val", field_kind="decimal",
        )
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        CustomFieldValue.objects.create(item=item, field_definition=field, value=0.0)
        r = editor_client.post(URL, {
            "name": "DivZero",
            "sources": [
                _seed_source(item_type.id),
                {"name": "calc", "kind": "formula", "formula": "10 / $seed.val"},
            ],
            "columns": [
                _display_col("Items", "seed"),
                _display_col("Div", "calc"),
            ],
        }, format="json")
        matrix_id = r.data["id"]
        r = editor_client.get(f"{URL}{matrix_id}/data/")
        assert r.data["rows"][0][1] is None

    def test_empty_matrix_data(self, editor_client, vault, editor_user):
        item_type = ItemTypeFactory(vault=vault, slug="empty-data")
        r = editor_client.post(URL, {
            "name": "Empty",
            "sources": [_seed_source(item_type.id)],
            "columns": [_display_col("Seed", "seed")],
        }, format="json")
        matrix_id = r.data["id"]
        r = editor_client.get(f"{URL}{matrix_id}/data/")
        assert r.data["rows"] == []
