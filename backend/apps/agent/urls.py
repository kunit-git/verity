from django.urls import path

from . import views

urlpatterns = [
    path("status/", views.AgentStatusView.as_view(), name="agent-status"),
    path("models/", views.AgentModelsView.as_view(), name="agent-models"),
    path(
        "conversations/",
        views.ConversationListCreateView.as_view(),
        name="agent-conversations",
    ),
    path(
        "conversations/<uuid:pk>/",
        views.ConversationDetailView.as_view(),
        name="agent-conversation-detail",
    ),
    path(
        "conversations/<uuid:pk>/chat/",
        views.ChatView.as_view(),
        name="agent-chat",
    ),
    path(
        "pending-actions/<uuid:pk>/accept/",
        views.PendingActionAcceptView.as_view(),
        name="agent-action-accept",
    ),
    path(
        "pending-actions/<uuid:pk>/reject/",
        views.PendingActionRejectView.as_view(),
        name="agent-action-reject",
    ),
]
