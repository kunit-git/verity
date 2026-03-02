from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("item-types", views.ItemTypeViewSet, basename="itemtype")
router.register("items", views.ItemViewSet, basename="item")

urlpatterns = [
    path("", include(router.urls)),
]
