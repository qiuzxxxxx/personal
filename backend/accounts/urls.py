from django.urls import path

from .views import (
    ChangePasswordView,
    LoginView,
    LogsView,
    LogoutView,
    MeView,
    UsersListView,
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("users/", UsersListView.as_view(), name="auth-users"),
    path("logs/", LogsView.as_view(), name="auth-logs"),
    path(
        "<str:username>/password/",
        ChangePasswordView.as_view(),
        name="auth-change-password",
    ),
]