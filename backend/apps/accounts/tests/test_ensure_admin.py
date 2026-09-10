import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command

User = get_user_model()

pytestmark = pytest.mark.django_db


def test_creates_admin_when_missing():
    call_command("ensure_admin", username="root", password="pw12345!")

    user = User.objects.get(username="root")
    assert user.is_superuser
    assert user.is_staff
    assert user.is_site_admin
    assert user.check_password("pw12345!")


def test_idempotent_keeps_existing_password():
    call_command("ensure_admin", username="root", password="original!")
    call_command("ensure_admin", username="root", password="different!")

    user = User.objects.get(username="root")
    # Without --recreate the existing account (and password) is left in place.
    assert user.check_password("original!")
    assert User.objects.filter(username="root").count() == 1


def test_refuses_to_promote_existing_user(django_user_model):
    django_user_model.objects.create_user(username="root", password="pw")

    with pytest.raises(CommandError, match="never promoted automatically"):
        call_command("ensure_admin", username="root", password="pw")

    user = User.objects.get(username="root")
    assert not user.is_superuser
    assert not user.is_site_admin


def test_recreate_resets_password():
    call_command("ensure_admin", username="root", password="original!")
    call_command("ensure_admin", username="root", password="fresh!", recreate=True)

    user = User.objects.get(username="root")
    assert user.check_password("fresh!")
    assert User.objects.filter(username="root").count() == 1


def test_empty_password_raises():
    with pytest.raises(CommandError):
        call_command("ensure_admin", username="root", password="")


def test_no_default_admin_password(monkeypatch):
    monkeypatch.delenv("DJANGO_SUPERUSER_PASSWORD", raising=False)
    with pytest.raises(CommandError, match="No admin password"):
        call_command("ensure_admin")
    assert not User.objects.exists()
