import factory
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


# ── Factories ──


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        if not create:
            return
        obj.set_password(extracted or "testpass123")
        obj.save()


class VaultFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "vaults.Vault"

    name = factory.Sequence(lambda n: f"Vault {n}")
    slug = factory.Sequence(lambda n: f"vault-{n}")
    created_by = factory.SubFactory(UserFactory, is_site_admin=True)


class VaultMembershipFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "vaults.VaultMembership"

    vault = factory.SubFactory(VaultFactory)
    user = factory.SubFactory(UserFactory)
    role = "editor"


class ItemTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "items.ItemType"

    vault = factory.SubFactory(VaultFactory)
    name = factory.Sequence(lambda n: f"Type {n}")
    slug = factory.Sequence(lambda n: f"type-{n}")


class CustomFieldDefinitionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "items.CustomFieldDefinition"

    item_type = factory.SubFactory(ItemTypeFactory)
    name = factory.Sequence(lambda n: f"Field {n}")
    slug = factory.Sequence(lambda n: f"field-{n}")
    field_kind = "text"
    display_order = factory.Sequence(lambda n: n)


class ItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "items.Item"

    item_type = factory.SubFactory(ItemTypeFactory)
    title = factory.Sequence(lambda n: f"Item {n}")
    created_by = factory.SubFactory(UserFactory)


class RelationTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "relations.RelationType"

    vault = factory.SubFactory(VaultFactory)
    kind = "trace"
    name = factory.Sequence(lambda n: f"relation-type-{n}")
    forward_label = "relates to"
    reverse_label = "is related from"


class ItemRelationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "relations.ItemRelation"
        skip_postgeneration_save = True

    relation_type = factory.SubFactory(RelationTypeFactory)
    source = factory.SubFactory(ItemFactory)
    target = factory.SubFactory(ItemFactory)
    created_by = factory.SubFactory(UserFactory)


class MatrixFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "matrices.Matrix"

    vault = factory.SubFactory(VaultFactory)
    name = factory.Sequence(lambda n: f"Matrix {n}")
    created_by = factory.SubFactory(UserFactory)


class MatrixSourceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "matrices.MatrixSource"

    matrix = factory.SubFactory(MatrixFactory)
    name = factory.Sequence(lambda n: f"source-{n}")
    position = 0
    kind = "seed"
    seed_item_type = factory.SubFactory(ItemTypeFactory)


class MatrixDisplayColumnFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "matrices.MatrixDisplayColumn"

    matrix = factory.SubFactory(MatrixFactory)
    position = 0
    heading = "Column"
    source_name = "source"


class MailboxArtifactFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "mailbox.MailboxArtifact"

    user = factory.SubFactory(UserFactory)
    filename = factory.Sequence(lambda n: f"doc-{n}.md")
    content = "# Test Document"
    file_size = 15


# ── Fixtures ──


def _authenticate_client(client, user):
    """Get JWT tokens via the login endpoint and set on client."""
    response = client.post(
        "/api/v1/auth/login/",
        {"username": user.username, "password": "testpass123"},
        format="json",
    )
    assert response.status_code == 200, f"Login failed: {response.data}"
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return client


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def site_admin_user(db):
    return UserFactory(is_site_admin=True)


@pytest.fixture
def regular_user(db):
    return UserFactory()


@pytest.fixture
def vault(db, site_admin_user):
    return VaultFactory(created_by=site_admin_user)


@pytest.fixture
def item_type(vault):
    return ItemTypeFactory(vault=vault)


@pytest.fixture
def item_type_with_fields(item_type):
    from apps.items.models import CustomFieldDefinition
    CustomFieldDefinitionFactory(
        item_type=item_type, name="Priority", slug="priority",
        field_kind="integer", is_required=True, display_order=0,
    )
    CustomFieldDefinitionFactory(
        item_type=item_type, name="Notes", slug="notes",
        field_kind="text", is_required=False, display_order=1,
    )
    return item_type


@pytest.fixture
def composition_type(vault):
    from apps.relations.models import RelationType
    return RelationType.objects.get(vault=vault, kind="composition")


@pytest.fixture
def trace_type(vault):
    from apps.relations.models import RelationType
    return RelationType.objects.get(vault=vault, kind="trace")


@pytest.fixture
def editor_user(db, vault):
    user = UserFactory()
    VaultMembershipFactory(vault=vault, user=user, role="editor")
    user.active_vault = vault
    user.save(update_fields=["active_vault"])
    return user


@pytest.fixture
def viewer_user(db, vault):
    user = UserFactory()
    VaultMembershipFactory(vault=vault, user=user, role="viewer")
    user.active_vault = vault
    user.save(update_fields=["active_vault"])
    return user


@pytest.fixture
def site_admin_client(api_client, site_admin_user, vault):
    site_admin_user.active_vault = vault
    site_admin_user.save(update_fields=["active_vault"])
    return _authenticate_client(api_client, site_admin_user)


@pytest.fixture
def editor_client(editor_user):
    client = APIClient()
    return _authenticate_client(client, editor_user)


@pytest.fixture
def viewer_client(viewer_user):
    client = APIClient()
    return _authenticate_client(client, viewer_user)
