from django.contrib import admin

from .models import ItemRelation, RelationType


@admin.register(RelationType)
class RelationTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "forward_label", "reverse_label", "is_active", "is_deleted"]
    list_filter = ["is_active", "is_deleted"]
    actions = ["restore_selected"]

    def get_queryset(self, request):
        return self.model.all_objects.all()

    @admin.action(description="Restore selected records")
    def restore_selected(self, request, queryset):
        queryset.update(is_deleted=False, deleted_at=None)


@admin.register(ItemRelation)
class ItemRelationAdmin(admin.ModelAdmin):
    list_display = ["source", "relation_type", "target", "created_by", "is_deleted"]
    list_filter = ["relation_type", "is_deleted"]
    actions = ["restore_selected"]

    def get_queryset(self, request):
        return self.model.all_objects.all()

    @admin.action(description="Restore selected records")
    def restore_selected(self, request, queryset):
        queryset.update(is_deleted=False, deleted_at=None)
