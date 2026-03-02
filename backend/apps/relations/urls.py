from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("relation-types", views.RelationTypeViewSet, basename="relationtype")
router.register("relations", views.ItemRelationViewSet, basename="relation")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "items/<uuid:pk>/navigation/",
        views.ItemNavigationView.as_view({"get": "retrieve"}),
        name="item-navigation",
    ),
]
