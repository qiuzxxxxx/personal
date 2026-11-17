from django.urls import path

from .views import (
    AccountCreateView,
    AccountDetailView,
    AccountLockListView,
    AccountLockToggleView,
    ChangePasswordView,
    LoginView,
    LogsView,
    LogoutView,
    MeView,
    MaintenanceStatusView,
    MaintenanceToggleView,
    UsersListView,
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("users/", UsersListView.as_view(), name="auth-users"),
    path("users/create/", AccountCreateView.as_view(), name="auth-user-create"),
    path("users/<str:username>/", AccountDetailView.as_view(), name="auth-user-detail"),
    path("logs/", LogsView.as_view(), name="auth-logs"),
    path(
        "<str:username>/password/",
        ChangePasswordView.as_view(),
        name="auth-change-password",
    ),
    # 维护模式 + 账号锁定
    path("maintenance/status/", MaintenanceStatusView.as_view(), name="maintenance-status"),
    path("maintenance/toggle/", MaintenanceToggleView.as_view(), name="maintenance-toggle"),
    path("maintenance/locks/", AccountLockListView.as_view(), name="account-lock-list"),
    path("maintenance/lock/", AccountLockToggleView.as_view(), name="account-lock-toggle"),
]
