from django.contrib import admin

from .models import MailboxArtifact


@admin.register(MailboxArtifact)
class MailboxArtifactAdmin(admin.ModelAdmin):
    list_display = ["filename", "user", "file_size", "created_at", "is_deleted"]
    list_filter = ["created_at", "is_deleted"]
    search_fields = ["filename", "user__username"]
    readonly_fields = ["id", "file_size", "created_at"]
    actions = ["restore_selected"]

    def get_queryset(self, request):
        return self.model.all_objects.all()

    @admin.action(description="Restore selected records")
    def restore_selected(self, request, queryset):
        queryset.update(is_deleted=False, deleted_at=None)
