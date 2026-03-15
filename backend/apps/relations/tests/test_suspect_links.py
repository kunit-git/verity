import pytest
from conftest import ItemFactory
from apps.relations.models import ItemRelation


URL = "/api/v1/relations/"


class TestSuspectLinks:
    def test_new_relation_not_suspect(self, editor_client, item_type, editor_user, trace_type):
        src = ItemFactory(item_type=item_type, created_by=editor_user)
        tgt = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.post(URL, {
            "relation_type": str(trace_type.id),
            "source": str(src.id), "target": str(tgt.id),
        }, format="json")
        rel_id = r.data["id"]
        # Check via navigation
        nav = editor_client.get(f"/api/v1/items/{src.id}/navigation/")
        assert nav.status_code == 200
        right = nav.data["right"]
        assert len(right) == 1
        assert right[0]["is_suspect"] is False

    def test_source_edit_makes_suspect(self, editor_client, item_type, editor_user, trace_type):
        src = ItemFactory(item_type=item_type, created_by=editor_user)
        tgt = ItemFactory(item_type=item_type, created_by=editor_user)
        editor_client.post(URL, {
            "relation_type": str(trace_type.id),
            "source": str(src.id), "target": str(tgt.id),
        }, format="json")
        # Edit source
        editor_client.patch(f"/api/v1/items/{src.id}/", {"title": "Changed"}, format="json")
        nav = editor_client.get(f"/api/v1/items/{src.id}/navigation/")
        right = nav.data["right"]
        assert right[0]["is_suspect"] is True

    def test_target_edit_makes_suspect(self, editor_client, item_type, editor_user, trace_type):
        src = ItemFactory(item_type=item_type, created_by=editor_user)
        tgt = ItemFactory(item_type=item_type, created_by=editor_user)
        editor_client.post(URL, {
            "relation_type": str(trace_type.id),
            "source": str(src.id), "target": str(tgt.id),
        }, format="json")
        # Edit target
        editor_client.patch(f"/api/v1/items/{tgt.id}/", {"title": "Changed"}, format="json")
        nav = editor_client.get(f"/api/v1/items/{src.id}/navigation/")
        right = nav.data["right"]
        assert right[0]["is_suspect"] is True

    def test_confirm_clears_suspect(self, editor_client, item_type, editor_user, trace_type):
        src = ItemFactory(item_type=item_type, created_by=editor_user)
        tgt = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.post(URL, {
            "relation_type": str(trace_type.id),
            "source": str(src.id), "target": str(tgt.id),
        }, format="json")
        rel_id = r.data["id"]
        # Make suspect
        editor_client.patch(f"/api/v1/items/{src.id}/", {"title": "Changed"}, format="json")
        # Confirm
        editor_client.post(f"{URL}{rel_id}/confirm/")
        nav = editor_client.get(f"/api/v1/items/{src.id}/navigation/")
        right = nav.data["right"]
        assert right[0]["is_suspect"] is False

    def test_version_pinned_then_edit_resets_pin(self, editor_client, item_type, editor_user, trace_type):
        src = ItemFactory(item_type=item_type, created_by=editor_user)
        tgt = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.post(URL, {
            "relation_type": str(trace_type.id),
            "source": str(src.id), "target": str(tgt.id),
        }, format="json")
        rel_id = r.data["id"]
        # Pin
        editor_client.post(f"{URL}{rel_id}/confirm/", {"version_pinned": True}, format="json")
        rel = ItemRelation.objects.get(pk=rel_id)
        assert rel.version_pinned is True
        # Edit source — should reset pin
        editor_client.patch(f"/api/v1/items/{src.id}/", {"title": "After Pin"}, format="json")
        rel.refresh_from_db()
        assert rel.version_pinned is False
