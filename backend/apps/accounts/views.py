from django.contrib.auth import get_user_model
from django.db import OperationalError, transaction
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .models import SiteSettings
from apps.vaults.permissions import IsVaultAdmin
from .permissions import IsSiteAdmin
from .serializers import (
    RegisterSerializer,
    UserSerializer,
    UserManagementSerializer,
    ChangeOwnPasswordSerializer,
    AdminChangePasswordSerializer,
    SiteSettingsSerializer,
)


class _SetupThrottle(AnonRateThrottle):
    scope = "initial_setup"
    rate = "10/hour"

User = get_user_model()


class SiteSettingsView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [permissions.AllowAny()]
        return [IsSiteAdmin()]

    def get(self, request):
        return Response(SiteSettingsSerializer(SiteSettings.get()).data)

    def patch(self, request):
        settings = SiteSettings.get()
        serializer = SiteSettingsSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class InitialSetupView(APIView):
    """
    GET  — returns {"setup_required": bool}. Returns 503 if the database is unavailable.
    POST — creates the first site-admin account. Rejected with 409 if any site admin
           already exists. Rate-limited to 10 requests/hour per IP.
    """

    permission_classes = [permissions.AllowAny]

    def get_throttles(self):
        if self.request.method == "POST":
            return [_SetupThrottle()]
        return []

    def get(self, request):
        try:
            setup_required = not User.objects.filter(is_site_admin=True).exists()
        except OperationalError:
            return Response(
                {"detail": "Database unavailable. Please retry later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"setup_required": setup_required})

    def post(self, request):
        username = request.data.get("username", "").strip()
        password = request.data.get("password", "")

        errors = {}
        if not username:
            errors["username"] = ["This field is required."]
        if len(password) < 8:
            errors["password"] = ["Password must be at least 8 characters."]
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # Re-verify inside the transaction to close the race window.
                if User.objects.filter(is_site_admin=True).exists():
                    return Response(
                        {"detail": "Setup already completed. An admin account already exists."},
                        status=status.HTTP_409_CONFLICT,
                    )
                if User.objects.filter(username=username).exists():
                    return Response(
                        {"username": ["A user with this username already exists."]},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                User.objects.create_user(
                    username=username,
                    password=password,
                    is_site_admin=True,
                    is_staff=True,
                    is_superuser=True,
                )
        except OperationalError:
            return Response(
                {"detail": "Database unavailable. Please retry later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {"detail": "Admin account created successfully."},
            status=status.HTTP_201_CREATED,
        )


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        if not SiteSettings.get().registration_enabled:
            return Response(
                {"detail": "Registration is currently disabled."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user.account_status = "locked"
        user.is_active = False
        user.save(update_fields=["account_status", "is_active"])
        return Response(
            {"detail": "Registration received. Your account is pending admin approval."},
            status=status.HTTP_202_ACCEPTED,
        )


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class ChangeOwnPasswordView(APIView):
    def post(self, request):
        serializer = ChangeOwnPasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminChangePasswordView(APIView):
    permission_classes = [IsSiteAdmin]

    def post(self, request, pk):
        user = generics.get_object_or_404(User, pk=pk)
        if user.account_status == "deleted":
            return Response(
                {"detail": "Cannot change password for a deleted account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = AdminChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminCreateUserView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [IsSiteAdmin]


class UserListView(generics.ListAPIView):
    serializer_class = UserManagementSerializer
    permission_classes = [IsSiteAdmin | IsVaultAdmin]
    pagination_class = None

    def get_queryset(self):
        qs = User.objects.all().order_by("date_joined")
        if self.request.query_params.get("include_deleted", "").lower() != "true":
            qs = qs.exclude(account_status="deleted")
        return qs


class UserDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = UserManagementSerializer
    permission_classes = [IsSiteAdmin]
    queryset = User.objects.all()
    http_method_names = ["get", "patch", "head", "options"]


class LockUserView(APIView):
    permission_classes = [IsSiteAdmin]

    def post(self, request, pk):
        user = generics.get_object_or_404(User, pk=pk)
        if user.pk == request.user.pk:
            return Response(
                {"detail": "You cannot lock your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if user.account_status == "deleted":
            return Response(
                {"detail": "Cannot lock a deleted account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.account_status = "locked"
        user.is_active = False
        user.save(update_fields=["account_status", "is_active"])
        return Response(UserManagementSerializer(user).data)


class UnlockUserView(APIView):
    permission_classes = [IsSiteAdmin]

    def post(self, request, pk):
        user = generics.get_object_or_404(User, pk=pk)
        if user.account_status != "locked":
            return Response(
                {"detail": "Only locked accounts can be unlocked."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.account_status = "active"
        user.is_active = True
        user.save(update_fields=["account_status", "is_active"])
        return Response(UserManagementSerializer(user).data)


class DeleteUserView(APIView):
    permission_classes = [IsSiteAdmin]

    def post(self, request, pk):
        user = generics.get_object_or_404(User, pk=pk)
        if user.pk == request.user.pk:
            return Response(
                {"detail": "You cannot delete your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if user.account_status == "deleted":
            return Response(
                {"detail": "Account is already deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.account_status = "deleted"
        user.is_active = False
        user.save(update_fields=["account_status", "is_active"])
        return Response(UserManagementSerializer(user).data)
