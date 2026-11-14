from django.urls import path

from . import views

urlpatterns = [
    path("workspace/today/", views.today, name="workspace-today"),
    path("workspace/preferences/", views.preferences, name="workspace-preferences"),
    path("tasks/", views.task_list, name="task-list"),
    path("tasks/reorder/", views.task_reorder, name="task-reorder"),
    path("tasks/<uuid:task_id>/", views.task_detail, name="task-detail"),
    path("tasks/<uuid:task_id>/restore/", views.task_restore, name="task-restore"),
    path("projects/", views.project_list, name="project-list"),
    path("projects/<uuid:project_id>/", views.project_detail, name="project-detail"),
    path("projects/<uuid:project_id>/restore/", views.project_restore, name="project-restore"),
    path("tags/", views.tag_list, name="tag-list"),
    path("tags/<uuid:tag_id>/", views.tag_detail, name="tag-detail"),
    path("journal/<str:day>/", views.journal, name="journal"),
]
