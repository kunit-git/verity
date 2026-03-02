from django.contrib import admin

from .models import Matrix, MatrixColumn


class MatrixColumnInline(admin.TabularInline):
    model = MatrixColumn
    extra = 1
    ordering = ["position"]


@admin.register(Matrix)
class MatrixAdmin(admin.ModelAdmin):
    list_display = ["name", "created_by", "created_at", "updated_at"]
    search_fields = ["name", "description"]
    inlines = [MatrixColumnInline]
