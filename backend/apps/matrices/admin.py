from django.contrib import admin

from .models import Matrix, MatrixColumn


class MatrixColumnInline(admin.TabularInline):
    model = MatrixColumn
    extra = 1
    ordering = ["position"]

    def get_queryset(self, request):
        return self.model.all_objects.all()


@admin.register(Matrix)
class MatrixAdmin(admin.ModelAdmin):
    list_display = ["name", "created_by", "created_at", "updated_at", "is_deleted"]
    list_filter = ["is_deleted"]
    search_fields = ["name", "description"]
    inlines = [MatrixColumnInline]
    actions = ["restore_selected"]

    def get_queryset(self, request):
        return self.model.all_objects.all()

    @admin.action(description="Restore selected records")
    def restore_selected(self, request, queryset):
        queryset.update(is_deleted=False, deleted_at=None)
