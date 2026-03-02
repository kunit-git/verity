from django.contrib import admin

from .models import CustomFieldDefinition, CustomFieldValue, Item, ItemType


class CustomFieldDefinitionInline(admin.TabularInline):
    model = CustomFieldDefinition
    extra = 1


@admin.register(ItemType)
class ItemTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active"]
    inlines = [CustomFieldDefinitionInline]


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ["title", "item_type", "status", "created_by", "updated_at"]
    list_filter = ["item_type", "status"]
    search_fields = ["title", "description"]
