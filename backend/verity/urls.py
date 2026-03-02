from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.items.urls")),
    path("api/v1/", include("apps.relations.urls")),
    path("api/v1/", include("apps.matrices.urls")),
    path("api/v1/", include("apps.mailbox.urls")),
]
