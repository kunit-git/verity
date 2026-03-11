from django.contrib import admin

from .models import CustomFieldDefinition, CustomFieldValue, Item, ItemType


class CustomFieldDefinitionInline(admin.TabularInline):
    model = CustomFieldDefinition
    extra = 1

    def get_queryset(self, request):
        return self.model.all_objects.all()


@admin.register(ItemType)
class ItemTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active", "is_deleted"]
    list_filter = ["is_active", "is_deleted"]
    inlines = [CustomFieldDefinitionInline]
    actions = ["restore_selected"]

    def get_queryset(self, request):
        return self.model.all_objects.all()

    @admin.action(description="Restore selected records")
    def restore_selected(self, request, queryset):
        queryset.update(is_deleted=False, deleted_at=None)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ["title", "item_type", "status", "created_by", "updated_at", "is_deleted"]
    list_filter = ["item_type", "status", "is_deleted"]
    search_fields = ["title", "description"]
    actions = ["restore_selected"]

    def get_queryset(self, request):
        return self.model.all_objects.all()

    @admin.action(description="Restore selected records")
    def restore_selected(self, request, queryset):
        queryset.update(is_deleted=False, deleted_at=None)
