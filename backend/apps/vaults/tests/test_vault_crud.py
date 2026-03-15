import pytest
from apps.relations.models import RelationType


URL = "/api/v1/vaults/"


class TestVaultList:
    def test_site_admin_lists_vaults(self, site_admin_client, vault):
        r = site_admin_client.get(URL)
        assert r.status_code == 200
        assert len(r.data) >= 1

    def test_non_admin_forbidden(self, editor_client):
        r = editor_client.get(URL)
        assert r.status_code == 403


class TestVaultCreate:
    def test_create_vault(self, site_admin_client):
        r = site_admin_client.post(URL, {
            "name": "New Vault", "slug": "new-vault",
        }, format="json")
        assert r.status_code == 201
        assert r.data["name"] == "New Vault"

    def test_auto_creates_builtin_relation_types(self, site_admin_client):
        r = site_admin_client.post(URL, {
            "name": "With Builtins", "slug": "with-builtins",
        }, format="json")
        vault_id = r.data["id"]
        builtins = RelationType.objects.filter(vault_id=vault_id, is_builtin=True)
        assert builtins.count() == 2
        names = set(builtins.values_list("name", flat=True))
        assert names == {"is_composed_of", "traces_to"}

    def test_duplicate_name(self, site_admin_client, vault):
        r = site_admin_client.post(URL, {
            "name": vault.name, "slug": "diff-slug",
        }, format="json")
        assert r.status_code == 400

    def test_duplicate_slug(self, site_admin_client, vault):
        r = site_admin_client.post(URL, {
            "name": "Different Name", "slug": vault.slug,
        }, format="json")
        assert r.status_code == 400

    def test_non_admin_forbidden(self, editor_client):
        r = editor_client.post(URL, {
            "name": "Nope", "slug": "nope",
        }, format="json")
        assert r.status_code == 403


class TestVaultDetail:
    def test_get(self, site_admin_client, vault):
        r = site_admin_client.get(f"{URL}{vault.id}/")
        assert r.status_code == 200
        assert r.data["name"] == vault.name

    def test_patch(self, site_admin_client, vault):
        r = site_admin_client.patch(f"{URL}{vault.id}/", {
            "description": "Updated",
        }, format="json")
        assert r.status_code == 200
        assert r.data["description"] == "Updated"

    def test_delete(self, site_admin_client):
        r = site_admin_client.post(URL, {"name": "ToDelete", "slug": "to-delete"}, format="json")
        vault_id = r.data["id"]
        r = site_admin_client.delete(f"{URL}{vault_id}/")
        assert r.status_code == 204

    def test_non_admin_forbidden(self, editor_client, vault):
        r = editor_client.get(f"{URL}{vault.id}/")
        assert r.status_code == 403
