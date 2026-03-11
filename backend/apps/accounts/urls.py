from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

urlpatterns = [
    path("settings/", views.SiteSettingsView.as_view(), name="site-settings"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", TokenObtainPairView.as_view(), name="token_obtain"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("me/", views.MeView.as_view(), name="me"),
    path("me/password/", views.ChangeOwnPasswordView.as_view(), name="change-own-password"),
    path("users/", views.UserListView.as_view(), name="user-list"),
    path("users/<int:pk>/", views.UserDetailView.as_view(), name="user-detail"),
    path("users/<int:pk>/password/", views.AdminChangePasswordView.as_view(), name="admin-change-password"),
    path("users/<int:pk>/lock/", views.LockUserView.as_view(), name="user-lock"),
    path("users/<int:pk>/unlock/", views.UnlockUserView.as_view(), name="user-unlock"),
    path("users/<int:pk>/delete/", views.DeleteUserView.as_view(), name="user-delete"),
]
