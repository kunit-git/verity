import pytest
from conftest import ItemFactory, ItemTypeFactory, VaultFactory, RelationTypeFactory
from apps.relations.models import RelationType, ItemRelation


URL = "/api/v1/relations/"


class TestRelationCreate:
    def test_create_trace(self, editor_client, item_type, editor_user, trace_type):
        src = ItemFactory(item_type=item_type, created_by=editor_user)
        tgt = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.post(URL, {
            "relation_type": str(trace_type.id),
            "source": str(src.id),
            "target": str(tgt.id),
        }, format="json")
        assert r.status_code == 201
        assert r.data["source_version"] == 1
        assert r.data["target_version"] == 1

    def test_create_composition_auto_position(self, editor_client, item_type, editor_user, composition_type):
        parent = ItemFactory(item_type=item_type, created_by=editor_user)
        child1 = ItemFactory(item_type=item_type, created_by=editor_user)
        child2 = ItemFactory(item_type=item_type, created_by=editor_user)
        editor_client.post(URL, {
            "relation_type": str(composition_type.id),
            "source": str(parent.id), "target": str(child1.id),
        }, format="json")
        r = editor_client.post(URL, {
            "relation_type": str(composition_type.id),
            "source": str(parent.id), "target": str(child2.id),
        }, format="json")
        assert r.status_code == 201
        rel1 = ItemRelation.objects.get(source=parent, target=child1)
        rel2 = ItemRelation.objects.get(source=parent, target=child2)
        assert rel2.position > rel1.position

    def test_self_relation_rejected(self, editor_client, item_type, editor_user, trace_type):
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.post(URL, {
            "relation_type": str(trace_type.id),
            "source": str(item.id), "target": str(item.id),
        }, format="json")
        assert r.status_code == 400

    def test_wrong_source_type(self, editor_client, vault, editor_user):
        type_a = ItemTypeFactory(vault=vault, slug="type-a")
        type_b = ItemTypeFactory(vault=vault, slug="type-b")
        rt = RelationType.objects.create(
            vault=vault, kind="trace", name="constrained-rt",
            forward_label="x", reverse_label="y",
            source_item_type=type_a,
        )
        item_b = ItemFactory(item_type=type_b, created_by=editor_user)
        item_a = ItemFactory(item_type=type_a, created_by=editor_user)
        r = editor_client.post(URL, {
            "relation_type": str(rt.id),
            "source": str(item_b.id),  # wrong type
            "target": str(item_a.id),
        }, format="json")
        assert r.status_code == 400

    def test_duplicate_relation(self, editor_client, item_type, editor_user, trace_type):
        src = ItemFactory(item_type=item_type, created_by=editor_user)
        tgt = ItemFactory(item_type=item_type, created_by=editor_user)
        editor_client.post(URL, {
            "relation_type": str(trace_type.id),
            "source": str(src.id), "target": str(tgt.id),
        }, format="json")
        r = editor_client.post(URL, {
            "relation_type": str(trace_type.id),
            "source": str(src.id), "target": str(tgt.id),
        }, format="json")
        assert r.status_code == 400

    def test_viewer_forbidden(self, viewer_client, item_type, editor_user, trace_type):
        src = ItemFactory(item_type=item_type, created_by=editor_user)
        tgt = ItemFactory(item_type=item_type, created_by=editor_user)
        r = viewer_client.post(URL, {
            "relation_type": str(trace_type.id),
            "source": str(src.id), "target": str(tgt.id),
        }, format="json")
        assert r.status_code == 403

    def test_cannot_relate_items_from_another_vault(self, editor_client, db):
        """Source/target items from a foreign vault must be rejected even if the
        relation type belongs to the active vault."""
        other_vault = VaultFactory()
        other_type = ItemTypeFactory(vault=other_vault)
        src = ItemFactory(item_type=other_type)
        tgt = ItemFactory(item_type=other_type)
        foreign_rt = RelationType.objects.get(vault=other_vault, kind="trace")
        r = editor_client.post(URL, {
            "relation_type": str(foreign_rt.id),
            "source": str(src.id), "target": str(tgt.id),
        }, format="json")
        assert r.status_code == 400

    def test_cannot_use_relation_type_from_another_vault(self, editor_client, item_type, editor_user, db):
        """A relation type from a foreign vault must be rejected even when the
        items belong to the active vault."""
        other_vault = VaultFactory()
        foreign_rt = RelationType.objects.get(vault=other_vault, kind="trace")
        src = ItemFactory(item_type=item_type, created_by=editor_user)
        tgt = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.post(URL, {
            "relation_type": str(foreign_rt.id),
            "source": str(src.id), "target": str(tgt.id),
        }, format="json")
        assert r.status_code == 400


class TestRelationList:
    def test_list(self, editor_client, item_type, editor_user, trace_type):
        src = ItemFactory(item_type=item_type, created_by=editor_user)
        tgt = ItemFactory(item_type=item_type, created_by=editor_user)
        editor_client.post(URL, {
            "relation_type": str(trace_type.id),
            "source": str(src.id), "target": str(tgt.id),
        }, format="json")
        r = editor_client.get(URL)
        assert r.status_code == 200
        assert r.data["count"] >= 1

    def test_filter_by_source(self, editor_client, item_type, editor_user, trace_type):
        src = ItemFactory(item_type=item_type, created_by=editor_user)
        tgt = ItemFactory(item_type=item_type, created_by=editor_user)
        editor_client.post(URL, {
            "relation_type": str(trace_type.id),
            "source": str(src.id), "target": str(tgt.id),
        }, format="json")
        r = editor_client.get(f"{URL}?source={src.id}")
        assert r.data["count"] == 1

    def test_filter_by_target(self, editor_client, item_type, editor_user, trace_type):
        src = ItemFactory(item_type=item_type, created_by=editor_user)
        tgt = ItemFactory(item_type=item_type, created_by=editor_user)
        editor_client.post(URL, {
            "relation_type": str(trace_type.id),
            "source": str(src.id), "target": str(tgt.id),
        }, format="json")
        r = editor_client.get(f"{URL}?target={tgt.id}")
        assert r.data["count"] == 1


class TestRelationDelete:
    def test_delete(self, editor_client, item_type, editor_user, trace_type):
        src = ItemFactory(item_type=item_type, created_by=editor_user)
        tgt = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.post(URL, {
            "relation_type": str(trace_type.id),
            "source": str(src.id), "target": str(tgt.id),
        }, format="json")
        rel_id = r.data["id"]
        r = editor_client.delete(f"{URL}{rel_id}/")
        assert r.status_code == 204
