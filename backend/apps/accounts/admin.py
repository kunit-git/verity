from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ["username", "email", "is_site_admin", "account_status", "is_active"]
    list_filter = ["is_site_admin", "account_status", "is_active"]
    fieldsets = UserAdmin.fieldsets + (
        ("Role & Status", {"fields": ("is_site_admin", "account_status")}),
    )
