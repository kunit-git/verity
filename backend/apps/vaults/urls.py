from django.urls import path

from . import views

urlpatterns = [
    path("vaults/", views.VaultListCreateView.as_view(), name="vault-list"),
    path("vaults/select/", views.SelectVaultView.as_view(), name="vault-select"),
    path("vaults/my/", views.MyVaultsView.as_view(), name="vault-my"),
    path("vaults/<uuid:pk>/", views.VaultDetailView.as_view(), name="vault-detail"),
    path(
        "vaults/<uuid:vault_id>/members/",
        views.VaultMemberListView.as_view(),
        name="vault-members",
    ),
    path(
        "vaults/<uuid:vault_id>/members/<uuid:membership_id>/",
        views.VaultMemberDetailView.as_view(),
        name="vault-member-detail",
    ),
]
