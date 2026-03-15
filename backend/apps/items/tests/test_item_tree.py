import pytest
from conftest import ItemFactory, ItemRelationFactory
from apps.relations.models import RelationType, ItemRelation


class TestRoots:
    def test_returns_root_items(self, editor_client, item_type, editor_user, vault):
        comp = RelationType.objects.get(vault=vault, kind="composition")
        parent = ItemFactory(item_type=item_type, created_by=editor_user)
        child = ItemFactory(item_type=item_type, created_by=editor_user)
        ItemRelation(
            relation_type=comp, source=parent, target=child, created_by=editor_user,
        ).save()
        r = editor_client.get("/api/v1/items/roots/")
        assert r.status_code == 200
        ids = [i["id"] for i in r.data["results"]]
        assert str(parent.id) in ids
        assert str(child.id) not in ids

    def test_annotations(self, editor_client, item_type, editor_user, vault):
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.get("/api/v1/items/roots/")
        result = r.data["results"][0]
        assert "child_count" in result
        assert "has_suspect_links" in result
        assert "has_suspect_descendants" in result


class TestChildren:
    def test_returns_children(self, editor_client, item_type, editor_user, vault):
        comp = RelationType.objects.get(vault=vault, kind="composition")
        parent = ItemFactory(item_type=item_type, created_by=editor_user)
        child1 = ItemFactory(item_type=item_type, created_by=editor_user, title="Child A")
        child2 = ItemFactory(item_type=item_type, created_by=editor_user, title="Child B")
        ItemRelation(relation_type=comp, source=parent, target=child1, created_by=editor_user, position=10).save()
        ItemRelation(relation_type=comp, source=parent, target=child2, created_by=editor_user, position=20).save()
        r = editor_client.get(f"/api/v1/items/{parent.id}/children/")
        assert r.status_code == 200
        assert len(r.data["results"]) == 2
        assert r.data["results"][0]["title"] == "Child A"


class TestReorderChildren:
    def test_reorder(self, editor_client, item_type, editor_user, vault):
        comp = RelationType.objects.get(vault=vault, kind="composition")
        parent = ItemFactory(item_type=item_type, created_by=editor_user)
        child1 = ItemFactory(item_type=item_type, created_by=editor_user)
        child2 = ItemFactory(item_type=item_type, created_by=editor_user)
        ItemRelation(relation_type=comp, source=parent, target=child1, created_by=editor_user, position=10).save()
        ItemRelation(relation_type=comp, source=parent, target=child2, created_by=editor_user, position=20).save()
        r = editor_client.post(f"/api/v1/items/{parent.id}/reorder-children/", {
            "child_ids": [str(child2.id), str(child1.id)],
        }, format="json")
        assert r.status_code == 200
        rel1 = ItemRelation.objects.get(source=parent, target=child1)
        rel2 = ItemRelation.objects.get(source=parent, target=child2)
        assert rel2.position < rel1.position


class TestAncestors:
    def test_returns_chain(self, editor_client, item_type, editor_user, vault):
        comp = RelationType.objects.get(vault=vault, kind="composition")
        root = ItemFactory(item_type=item_type, created_by=editor_user)
        mid = ItemFactory(item_type=item_type, created_by=editor_user)
        leaf = ItemFactory(item_type=item_type, created_by=editor_user)
        ItemRelation(relation_type=comp, source=root, target=mid, created_by=editor_user).save()
        ItemRelation(relation_type=comp, source=mid, target=leaf, created_by=editor_user).save()
        r = editor_client.get(f"/api/v1/items/{leaf.id}/ancestors/")
        assert r.status_code == 200
        assert r.data == [str(root.id), str(mid.id)]

    def test_root_returns_empty(self, editor_client, item_type, editor_user):
        root = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.get(f"/api/v1/items/{root.id}/ancestors/")
        assert r.status_code == 200
        assert r.data == []
