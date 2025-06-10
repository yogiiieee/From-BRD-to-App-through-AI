# core/views.py
import json
import logging
import os
import re
import io
import zipfile
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt # Use this for AJAX POST if not using CSRF token in JS
from django.views.decorators.http import require_POST, require_GET
from django.utils.text import slugify
from django.contrib.auth.decorators import login_required # If you want to require login

# Import your core app's models and services
from .models import Project, GeneratedFile
from .services.gemini_client import analyze_brd, generate_text # analyze_brd for initial analysis, generate_text for code
from .services.file_writer import FileWriter
from .generators.python import PythonGenerator
from .generators.react_node import ReactNodeGenerator

# You might need to import your BRD model if you link it:
# from brd.models import Brd # Uncomment if you have a Brd model

logger = logging.getLogger(__name__)

# Initialize FileWriter globally or once (adjust as per your app's lifecycle)
# Ensure MEDIA_ROOT is correctly configured in settings.py
try:
    file_writer = FileWriter(base_output_dir=os.path.join(settings.MEDIA_ROOT, 'generated_projects'))
except Exception as e:
    logger.error(f"Failed to initialize FileWriter: {e}")
    file_writer = None # Handle this gracefully in your views

# Initialize Generators
# This assumes gemini_client is robust enough to be passed directly
# You might instantiate a new gemini_client for each request in a more complex setup
gemini_client_instance = None
try:
    # We are using `generate_text` for raw code generation now, so `analyze_brd` is for structured output.
    # The `gemini_client` can handle both.
    from .services import gemini_client as gem_client_module # Import the module to access its functions
    gemini_client_instance = gem_client_module 
except Exception as e:
    logger.error(f"Failed to initialize Gemini client: {e}")
    gemini_client_instance = None

python_generator = None
react_node_generator = None
if gemini_client_instance:
    python_generator = PythonGenerator(gemini_client_instance)
    react_node_generator = ReactNodeGenerator(gemini_client_instance)
else:
    logger.critical("Gemini client not initialized, code generation will fail.")


@require_POST
@csrf_exempt # Consider using Django's CSRF middleware for AJAX instead of this
# @login_required # Uncomment if only logged-in users can generate
def generate_project_view(request):
    response_data = {
        'status': 'error',
        'message': 'Failed to generate project.',
        'project_id': None,
        'generated_files_info': []
    }

    if not file_writer or not python_generator or not react_node_generator:
        response_data['message'] = "Server generators not initialized. Please contact support."
        logger.error("Attempted project generation with uninitialized generators.")
        return JsonResponse(response_data, status=500)

    try:
        # Get the analysis_data from the request body (sent by JavaScript)
        # Ensure your frontend sends this as JSON in the body
        request_body = json.loads(request.body)
        analysis_data = request_body.get('analysis_data')
        project_name_from_brd = analysis_data.get('project_summary', 'Untitled Project')
        
        # You might also get a user-provided project name
        user_provided_project_name = request_body.get('project_name')
        final_project_name = user_provided_project_name if user_provided_project_name else project_name_from_brd
        
        if not analysis_data:
            response_data['message'] = "No analysis data provided for project generation."
            return JsonResponse(response_data, status=400)

        logger.info(f"Initiating project generation for: {final_project_name}")

        # 1. Create a new Project instance
        # If you link to Brd model: brd_instance = Brd.objects.get(id=request_body.get('brd_id'))
        project = Project.objects.create(
            name=final_project_name,
            description=analysis_data.get('project_summary', ''),
            owner=request.user if request.user.is_authenticated else None, # Link to current user
            status='GENERATING'
            # brd=brd_instance # Uncomment if linking to Brd model
        )
        response_data['project_id'] = project.id

        # Determine a unique directory name for this project
        project_dir_name = f"{slugify(project.name)}-{project.id}"
        project_output_path = os.path.join(settings.MEDIA_ROOT, 'generated_projects', project_dir_name)
        
        # Update project with its generated path
        project.generated_path = os.path.join('generated_projects', project_dir_name)
        project.save()

        files_to_write_to_disk = [] # List to hold all generated files for FileWriter
        generated_file_models = [] # List to hold GeneratedFile instances for bulk creation

        # --- ORCHESTRATION LOGIC ---
        # This is simplified. In a real app, you'd have more complex logic
        # to decide what to generate first (e.g., models, then views, then frontend).

        # Example: Generate Django Models from User Stories
        themes = analysis_data.get('themes', [])
        for theme in themes:
            for epic in theme.get('epics', []):
                for user_story in epic.get('user_stories', []):
                    # Decide if this user story warrants a Django Model
                    # This is a heuristic, refine based on your BRD patterns
                    if "model" in user_story.get('title', '').lower() or \
                       "data structure" in user_story.get('title', '').lower() or \
                       any("database" in task.lower() for task in user_story.get('tasks', [])):
                        
                        logger.info(f"Generating Django model for story: {user_story.get('story_id')}")
                        try:
                            # Pass relevant parts of the user story and overall context
                            model_data = python_generator.generate_django_model(
                                user_story, 
                                {'project_summary': analysis_data.get('project_summary')}
                            )
                            if model_data and model_data.get('content'):
                                files_to_write_to_disk.append(model_data)
                                generated_file_models.append(
                                    GeneratedFile(
                                        project=project,
                                        file_path=model_data['file_path'],
                                        file_type=model_data['language']
                                    )
                                )
                        except Exception as gen_e:
                            logger.error(f"Failed to generate Django model for {user_story.get('story_id')}: {gen_e}")
                            # Continue, but log and potentially update status

                    # Example: Generate React Components for User Stories
                    # This is another heuristic, refine based on your BRD patterns
                    if "interface" in user_story.get('title', '').lower() or \
                       "UI" in user_story.get('title', '').lower() or \
                       "page" in user_story.get('title', '').lower():
                        
                        logger.info(f"Generating React component for story: {user_story.get('story_id')}")
                        try:
                            # You'll need to extract or infer UI requirements from the BRD
                            # For now, let's pass an empty dict for ui_requirements if not explicit
                            react_component_data = react_node_generator.generate_react_component(
                                user_story,
                                {'ui_description': user_story.get('title', '')}, # Basic UI description
                                {'project_summary': analysis_data.get('project_summary')}
                            )
                            if react_component_data and react_component_data.get('content'):
                                files_to_write_to_disk.append(react_component_data)
                                generated_file_models.append(
                                    GeneratedFile(
                                        project=project,
                                        file_path=react_component_data['file_path'],
                                        file_type=react_component_data['language']
                                    )
                                )
                        except Exception as gen_e:
                            logger.error(f"Failed to generate React component for {user_story.get('story_id')}: {gen_e}")
                            # Continue, but log and potentially update status

        # --- Initial project structure (e.g., package.json, base index.html/App.js, README) ---
        # You'll need a separate prompt/generator for this "base scaffolding"
        # For demonstration, let's hardcode a couple of files here
        base_files = [
            {'file_path': 'README.md', 'content': f"# {project.name}\n\nGenerated from your BRD. More details soon.", 'language': 'markdown'},
            {'file_path': 'package.json', 'content': '{"name": "generated-app", "version": "1.0.0", "scripts": {"start": "echo No start script yet"}, "dependencies": {}}', 'language': 'json'},
            # Add more base files as needed for Django/React setup
        ]
        files_to_write_to_disk.extend(base_files)
        generated_file_models.extend([
            GeneratedFile(project=project, file_path=f['file_path'], file_type=f['language'])
            for f in base_files
        ])


        # 2. Write all generated files to disk
        # Pass the desired output path relative to MEDIA_ROOT
        try:
            file_writer.write_files(project_dir_name, files_to_write_to_disk)
            logger.info(f"Successfully wrote {len(files_to_write_to_disk)} files to disk for project {project.id}")
        except Exception as write_e:
            project.status = 'FAILED'
            project.save()
            response_data['message'] = f"Failed to write generated files to disk: {write_e}"
            logger.error(f"Error writing files for project {project.id}: {write_e}", exc_info=True)
            return JsonResponse(response_data, status=500)

        # 3. Bulk create GeneratedFile instances
        GeneratedFile.objects.bulk_create(generated_file_models)
        logger.info(f"Created {len(generated_file_models)} GeneratedFile records for project {project.id}")

        # 4. Update Project status
        project.status = 'COMPLETED'
        project.save()

        response_data['status'] = 'success'
        response_data['message'] = 'Project generated successfully!'
        response_data['generated_files_info'] = [
            {'file_path': gf.file_path, 'file_type': gf.file_type} for gf in generated_file_models
        ]
        return JsonResponse(response_data, status=200)

    except json.JSONDecodeError:
        response_data['message'] = "Invalid JSON payload received."
        return JsonResponse(response_data, status=400)
    except Exception as e:
        logger.exception(f"Unexpected error in generate_project_view: {e}")
        # If project was created, try to mark as failed
        if 'project' in locals() and project.status == 'GENERATING':
            project.status = 'FAILED'
            project.save()
        response_data['message'] = f"An unexpected server error occurred: {e}"
        return JsonResponse(response_data, status=500)


@require_GET
# @login_required
def list_project_files(request, project_id):
    """
    Returns a list of generated files for a project, suitable for building a file tree.
    """
    project = Project.objects.get(id=project_id) # Use get_object_or_404 in production
    
    files_info = []
    # Option 1: Iterate through database records (simpler, less overhead)
    for generated_file in project.files.all().order_by('file_path'):
        files_info.append({
            'path': generated_file.file_path,
            'type': generated_file.file_type,
            'url': os.path.join(settings.MEDIA_URL, project.generated_path, generated_file.file_path)
            # DANGER: `url` might not directly point to content if `MEDIA_URL` is different
            # You might need a separate endpoint for secure content serving
        })

    # Option 2: Walk the filesystem (more robust for actual files, but requires disk access)
    # This assumes project.generated_path is correct and points to a real directory
    # full_project_dir = os.path.join(settings.MEDIA_ROOT, project.generated_path)
    # for root, dirs, files in os.walk(full_project_dir):
    #     for file_name in files:
    #         full_file_path = os.path.join(root, file_name)
    #         relative_path = os.path.relpath(full_file_path, full_project_dir)
    #         file_type = os.path.splitext(file_name)[1].lstrip('.') # Get extension
    #         files_info.append({
    #             'path': relative_path,
    #             'type': file_type,
    #             # For preview, you'd typically have a separate view that serves content
    #             'preview_url': reverse('core:preview_file', args=[project_id, relative_path])
    #         })
    
    return JsonResponse({'status': 'success', 'files': files_info})


@require_GET
# @login_required
def get_generated_file_content(request, project_id, file_path):
    """
    Returns the content of a specific generated file for preview.
    DANGER: Implement strong path sanitization to prevent directory traversal attacks.
    """
    project = Project.objects.get(id=project_id) # Use get_object_or_404
    
    # CRITICAL: Sanitize file_path to ensure it's within the project directory
    abs_project_path = os.path.join(settings.MEDIA_ROOT, project.generated_path)
    abs_requested_file_path = os.path.abspath(os.path.join(abs_project_path, file_path))

    # Ensure the requested path is actually inside the allowed project directory
    if not abs_requested_file_path.startswith(abs_project_path):
        logger.warning(f"Attempted directory traversal: {request.user} requested {file_path} outside {project.generated_path}")
        return JsonResponse({'error': 'Access denied: Invalid file path.'}, status=403)

    if not os.path.exists(abs_requested_file_path) or not os.path.isfile(abs_requested_file_path):
        return JsonResponse({'error': 'File not found.'}, status=404)

    try:
        with open(abs_requested_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        file_extension = os.path.splitext(file_path)[1].lstrip('.')
        # Map common extensions to languages for frontend syntax highlighting
        language_map = {
            'py': 'python', 'js': 'javascript', 'jsx': 'javascript', 'ts': 'typescript', 'tsx': 'typescript',
            'html': 'html', 'css': 'css', 'json': 'json', 'md': 'markdown', 'txt': 'plaintext',
        }
        language = language_map.get(file_extension, 'plaintext')

        return JsonResponse({'filename': file_path, 'content': content, 'language': language}, status=200)
    except Exception as e:
        logger.error(f"Error reading generated file {file_path} for project {project_id}: {e}", exc_info=True)
        return JsonResponse({'error': f'Could not read file content: {e}'}, status=500)


@require_GET
# @login_required
def download_project_zip(request, project_id):
    """
    Zips up the entire generated project and serves it for download.
    """
    project = Project.objects.get(id=project_id) # Use get_object_or_404
    
    full_project_dir = os.path.join(settings.MEDIA_ROOT, project.generated_path)

    if not os.path.isdir(full_project_dir):
        return JsonResponse({'error': 'Project directory not found.'}, status=404)

    response = HttpResponse(content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{slugify(project.name)}-{project.id}.zip"'

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(full_project_dir):
            for file in files:
                full_file_path = os.path.join(root, file)
                # Calculate archive path relative to the base project directory
                archive_name = os.path.relpath(full_file_path, full_project_dir)
                zf.write(full_file_path, archive_name)
    
    zip_buffer.seek(0)
    response.write(zip_buffer.read())
    return response