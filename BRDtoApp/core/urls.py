# core/urls.py
from django.urls import path, re_path
from . import views

app_name = 'core' # Namespace for your core app

urlpatterns = [
    # URL for triggering AI-driven project generation
    path('generate-project/', views.generate_project_view, name='generate_project'),
    
    # URL for listing files within a generated project (for file tree display)
    path('list-files/<int:project_id>/', views.list_project_files, name='list_project_files'),

    # URL for previewing individual generated files
    # Using re_path with a path converter for file_path (can contain slashes)
    re_path(r'preview/(?P<project_id>\d+)/(?P<file_path>.+)/$', views.get_generated_file_content, name='preview_file'),

    # URL for downloading the entire generated project as a zip
    path('download/<int:project_id>/', views.download_project_zip, name='download_project'),

    # URL for triggering tech stack identification
    path('identify-tech-stack/', views.identify_tech_stack_view, name='identify_tech_stack'),

    # URL for project preview
    path('project-preview/<int:project_id>/', views.project_preview_view, name='project_preview'),
]