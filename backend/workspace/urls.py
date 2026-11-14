from django.urls import path

from . import library_views, views

urlpatterns = [
    path("workspace/today/", views.today, name="workspace-today"),
    path("workspace/preferences/", views.preferences, name="workspace-preferences"),
    path("tasks/", views.task_list, name="task-list"),
    path("tasks/reorder/", views.task_reorder, name="task-reorder"),
    path("tasks/<uuid:task_id>/", views.task_detail, name="task-detail"),
    path("tasks/<uuid:task_id>/restore/", views.task_restore, name="task-restore"),
    path("tasks/<uuid:task_id>/materials/", library_views.task_materials, name="task-materials"),
    path(
        "tasks/<uuid:task_id>/materials/<uuid:material_id>/",
        library_views.task_material_detail,
        name="task-material-detail",
    ),
    path("projects/", views.project_list, name="project-list"),
    path("projects/<uuid:project_id>/", views.project_detail, name="project-detail"),
    path("projects/<uuid:project_id>/restore/", views.project_restore, name="project-restore"),
    path("tags/", views.tag_list, name="tag-list"),
    path("tags/<uuid:tag_id>/", views.tag_detail, name="tag-detail"),
    path("journal/<str:day>/", views.journal, name="journal"),
    path("library/folders/", library_views.folder_list, name="library-folder-list"),
    path(
        "library/folders/<uuid:folder_id>/",
        library_views.folder_detail,
        name="library-folder-detail",
    ),
    path("library/materials/", library_views.material_list, name="library-material-list"),
    path(
        "library/materials/<uuid:material_id>/",
        library_views.material_detail,
        name="library-material-detail",
    ),
    path(
        "library/materials/<uuid:material_id>/restore/",
        library_views.material_restore,
        name="library-material-restore",
    ),
    path(
        "library/materials/<uuid:material_id>/download/",
        library_views.material_download,
        name="library-material-download",
    ),
]
