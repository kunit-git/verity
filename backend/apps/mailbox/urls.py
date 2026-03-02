from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("mailbox", views.MailboxViewSet, basename="mailbox")

urlpatterns = [
    path("", include(router.urls)),
]
