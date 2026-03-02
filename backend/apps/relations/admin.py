from django.contrib import admin

from .models import ItemRelation, RelationType


@admin.register(RelationType)
class RelationTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "forward_label", "reverse_label", "is_active"]


@admin.register(ItemRelation)
class ItemRelationAdmin(admin.ModelAdmin):
    list_display = ["source", "relation_type", "target", "created_by"]
    list_filter = ["relation_type"]
