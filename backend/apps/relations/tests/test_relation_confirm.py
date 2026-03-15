import pytest
from conftest import ItemFactory
from apps.relations.models import ItemRelation


URL = "/api/v1/relations/"


class TestConfirm:
    def test_confirm_resets_versions(self, editor_client, item_type, editor_user, trace_type):
        src = ItemFactory(item_type=item_type, created_by=editor_user)
        tgt = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.post(URL, {
            "relation_type": str(trace_type.id),
            "source": str(src.id), "target": str(tgt.id),
        }, format="json")
        rel_id = r.data["id"]
        # Edit source to make suspect
        editor_client.patch(f"/api/v1/items/{src.id}/", {"title": "Changed"}, format="json")
        # Confirm
        r = editor_client.post(f"{URL}{rel_id}/confirm/")
        assert r.status_code == 200
        assert r.data["source_version"] == 2
        assert r.data["target_version"] == 1

    def test_confirm_with_explicit_versions(self, editor_client, item_type, editor_user, trace_type):
        src = ItemFactory(item_type=item_type, created_by=editor_user)
        tgt = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.post(URL, {
            "relation_type": str(trace_type.id),
            "source": str(src.id), "target": str(tgt.id),
        }, format="json")
        rel_id = r.data["id"]
        # Edit both to create versions
        editor_client.patch(f"/api/v1/items/{src.id}/", {"title": "v2"}, format="json")
        # Confirm with explicit version (version 1 should exist as snapshot)
        r = editor_client.post(f"{URL}{rel_id}/confirm/", {
            "source_version": 1,
            "target_version": 1,
        }, format="json")
        assert r.status_code == 200
        assert r.data["source_version"] == 1

    def test_confirm_with_pinned(self, editor_client, item_type, editor_user, trace_type):
        src = ItemFactory(item_type=item_type, created_by=editor_user)
        tgt = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.post(URL, {
            "relation_type": str(trace_type.id),
            "source": str(src.id), "target": str(tgt.id),
        }, format="json")
        rel_id = r.data["id"]
        r = editor_client.post(f"{URL}{rel_id}/confirm/", {
            "version_pinned": True,
        }, format="json")
        assert r.status_code == 200
        assert r.data["version_pinned"] is True

    def test_confirm_nonexistent_version(self, editor_client, item_type, editor_user, trace_type):
        src = ItemFactory(item_type=item_type, created_by=editor_user)
        tgt = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.post(URL, {
            "relation_type": str(trace_type.id),
            "source": str(src.id), "target": str(tgt.id),
        }, format="json")
        rel_id = r.data["id"]
        r = editor_client.post(f"{URL}{rel_id}/confirm/", {
            "source_version": 999,
        }, format="json")
        assert r.status_code == 400

    def test_viewer_forbidden(self, viewer_client, editor_client, item_type, editor_user, trace_type):
        src = ItemFactory(item_type=item_type, created_by=editor_user)
        tgt = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.post(URL, {
            "relation_type": str(trace_type.id),
            "source": str(src.id), "target": str(tgt.id),
        }, format="json")
        rel_id = r.data["id"]
        r = viewer_client.post(f"{URL}{rel_id}/confirm/")
        assert r.status_code == 403
