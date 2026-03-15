import pytest
import uuid
from conftest import ItemFactory, ItemTypeFactory, VaultFactory, UserFactory
from apps.relations.models import RelationType, ItemRelation


class TestNavigation:
    def test_returns_structure(self, editor_client, item_type, editor_user, vault):
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.get(f"/api/v1/items/{item.id}/navigation/")
        assert r.status_code == 200
        assert "parent" in r.data
        assert "children" in r.data
        assert "siblings" in r.data
        assert "left" in r.data
        assert "right" in r.data

    def test_parent_child_siblings(self, editor_client, item_type, editor_user, vault, composition_type):
        parent = ItemFactory(item_type=item_type, created_by=editor_user)
        child1 = ItemFactory(item_type=item_type, created_by=editor_user)
        child2 = ItemFactory(item_type=item_type, created_by=editor_user)
        ItemRelation(relation_type=composition_type, source=parent, target=child1, created_by=editor_user).save()
        ItemRelation(relation_type=composition_type, source=parent, target=child2, created_by=editor_user).save()

        # Child1 navigation: parent should be parent, sibling should include child2
        r = editor_client.get(f"/api/v1/items/{child1.id}/navigation/")
        assert r.data["parent"]["id"] == str(parent.id)
        sibling_ids = [s["id"] for s in r.data["siblings"]]
        assert str(child2.id) in sibling_ids

        # Parent navigation: children should include both
        r = editor_client.get(f"/api/v1/items/{parent.id}/navigation/")
        assert r.data["parent"] is None
        child_ids = [c["id"] for c in r.data["children"]]
        assert str(child1.id) in child_ids
        assert str(child2.id) in child_ids

    def test_left_right_trace(self, editor_client, item_type, editor_user, vault, trace_type):
        src = ItemFactory(item_type=item_type, created_by=editor_user)
        tgt = ItemFactory(item_type=item_type, created_by=editor_user)
        ItemRelation(relation_type=trace_type, source=src, target=tgt, created_by=editor_user).save()

        # Source: tgt should be in right
        r = editor_client.get(f"/api/v1/items/{src.id}/navigation/")
        assert len(r.data["right"]) == 1
        assert r.data["right"][0]["id"] == str(tgt.id)
        assert "relation_id" in r.data["right"][0]
        assert "relation_type" in r.data["right"][0]
        assert "relation_label" in r.data["right"][0]

        # Target: src should be in left
        r = editor_client.get(f"/api/v1/items/{tgt.id}/navigation/")
        assert len(r.data["left"]) == 1
        assert r.data["left"][0]["id"] == str(src.id)

    def test_root_has_null_parent(self, editor_client, item_type, editor_user):
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.get(f"/api/v1/items/{item.id}/navigation/")
        assert r.data["parent"] is None

    def test_no_relations_empty_arrays(self, editor_client, item_type, editor_user):
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.get(f"/api/v1/items/{item.id}/navigation/")
        assert r.data["children"] == []
        assert r.data["siblings"] == []
        assert r.data["left"] == []
        assert r.data["right"] == []

    def test_suspect_flags(self, editor_client, item_type, editor_user, vault, trace_type):
        src = ItemFactory(item_type=item_type, created_by=editor_user)
        tgt = ItemFactory(item_type=item_type, created_by=editor_user)
        ItemRelation(relation_type=trace_type, source=src, target=tgt, created_by=editor_user).save()
        # Edit source
        editor_client.patch(f"/api/v1/items/{src.id}/", {"title": "v2"}, format="json")
        r = editor_client.get(f"/api/v1/items/{src.id}/navigation/")
        assert r.data["right"][0]["is_suspect"] is True
        assert r.data["right"][0]["self_changed"] is True

    def test_nonexistent_item(self, editor_client):
        r = editor_client.get(f"/api/v1/items/{uuid.uuid4()}/navigation/")
        assert r.status_code == 404

    def test_different_vault_item(self, editor_client, editor_user):
        other_admin = UserFactory(is_site_admin=True)
        other_vault = VaultFactory(created_by=other_admin)
        other_type = ItemTypeFactory(vault=other_vault)
        item = ItemFactory(item_type=other_type, created_by=other_admin)
        r = editor_client.get(f"/api/v1/items/{item.id}/navigation/")
        assert r.status_code == 404
