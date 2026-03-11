from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ["username", "email", "role", "account_status", "is_active"]
    list_filter = ["role", "account_status", "is_active"]
    fieldsets = UserAdmin.fieldsets + (
        ("Role & Status", {"fields": ("role", "account_status")}),
    )
