from django.contrib import admin

from .models import MailboxArtifact


@admin.register(MailboxArtifact)
class MailboxArtifactAdmin(admin.ModelAdmin):
    list_display = ["filename", "user", "file_size", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["filename", "user__username"]
    readonly_fields = ["id", "file_size", "created_at"]
