from django.contrib import admin

from .models import Vault, VaultMembership


@admin.register(Vault)
class VaultAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_by", "created_at", "is_deleted")
    search_fields = ("name", "slug")


@admin.register(VaultMembership)
class VaultMembershipAdmin(admin.ModelAdmin):
    list_display = ("vault", "user", "created_at", "is_deleted")
