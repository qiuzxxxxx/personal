"""Helpers for resolving the owner of an agent conversation.

Agent conversations belong to a logged-in user; anonymous access is rejected
by the CanUseAgent permission before these helpers are reached.
"""
from django.db.models import Q
from rest_framework.request import Request

from .models import AgentAttachment, Conversation


def owner_q(request: Request) -> Q:
    if getattr(request.user, "is_authenticated", False):
        return Q(user=request.user)
    return Q(pk__in=[])


def conversations_for(request: Request):
    return Conversation.objects.filter(owner_q(request))


def conversation_for(request: Request, conversation_id):
    return conversations_for(request).filter(pk=conversation_id).first()


def attachments_for(request: Request):
    return AgentAttachment.objects.filter(owner_q(request))


def assign_owner(instance, request: Request):
    instance.user = request.user
    instance.session_key = ""
    return instance