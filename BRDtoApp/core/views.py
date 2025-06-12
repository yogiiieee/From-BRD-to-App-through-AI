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
# Ensure these imports are correct. Added identify_tech_stack
from .services.gemini_client import analyze_brd, generate_text, identify_tech_stack 
from .services.file_writer import FileWriter
from .generators.python import PythonGenerator
from .generators.react_node import ReactNodeGenerator

logger = logging.getLogger(__name__)

# Initialize FileWriter globally or once (adjust as per your app's lifecycle)
try:
    file_writer = FileWriter(base_output_dir=os.path.join(settings.MEDIA_ROOT, 'generated_projects'))
except Exception as e:
    logger.error(f"Failed to initialize FileWriter: {e}")
    file_writer = None

# Initialize Generators
gemini_client_instance = None
try:
    from .services import gemini_client as gem_client_module
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
# @login_required # Uncomment if only logged-in users can analyze tech stack
def identify_tech_stack_view(request):
    """
    Receives BRD analysis JSON, calls AI to identify tech stack, and returns it.
    """
    response_data = {
        'status': 'error',
        'message': 'Failed to identify tech stack.',
        'tech_stack': None
    }
    
    if not gemini_client_instance:
        response_data['message'] = "AI service not initialized on server. Please contact support."
        logger.error("Attempted tech stack identification with uninitialized AI service.")
        return JsonResponse(response_data, status=500)

    try:
        request_body = json.loads(request.body)
        brd_analysis_data = request_body.get('analysis_data')
        
        if not brd_analysis_data:
            response_data['message'] = "No BRD analysis data provided for tech stack identification."
            return JsonResponse(response_data, status=400)

        logger.info("Initiating tech stack identification from BRD analysis data.")
        
        # Call the AI to identify the tech stack
        tech_stack_result = identify_tech_stack(brd_analysis_data)
        
        if isinstance(tech_stack_result, dict) and tech_stack_result.get('error'):
            response_data['message'] = tech_stack_result.get('details', 'AI failed to identify tech stack.')
            logger.error(f"AI tech stack identification failed: {response_data['message']}. Raw AI: {tech_stack_result.get('raw_ai_response', 'N/A')}")
            return JsonResponse(response_data, status=500)
        else:
            response_data['status'] = 'success'
            response_data['message'] = 'Tech stack identified successfully.'
            response_data['tech_stack'] = tech_stack_result
            logger.info(f"Identified Tech Stack: {tech_stack_result}")
            return JsonResponse(response_data, status=200)

    except json.JSONDecodeError:
        response_data['message'] = "Invalid JSON payload received."
        return JsonResponse(response_data, status=400)
    except Exception as e:
        logger.exception(f"Unexpected error in identify_tech_stack_view: {e}")
        response_data['message'] = f"An unexpected server error occurred: {e}"
        return JsonResponse(response_data, status=500)


@require_POST
@csrf_exempt 
# @login_required 
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
        request_body = json.loads(request.body)
        analysis_data = request_body.get('analysis_data')
        # NEW: Get identified tech stack from the request
        identified_tech_stack = request_body.get('identified_tech_stack') 

        project_name_from_brd = analysis_data.get('project_summary', 'Untitled Project')
        user_provided_project_name = request_body.get('project_name')
        final_project_name = user_provided_project_name if user_provided_project_name else project_name_from_brd
        
        if not analysis_data or not identified_tech_stack: # NEW: Ensure tech stack is provided
            response_data['message'] = "Missing analysis data or identified tech stack for project generation."
            return JsonResponse(response_data, status=400)

        logger.info(f"Initiating project generation for: {final_project_name} with tech stack: {identified_tech_stack}")

        project = Project.objects.create(
            name=final_project_name,
            description=analysis_data.get('project_summary', ''),
            owner=request.user if request.user.is_authenticated else None,
            status='GENERATING'
        )
        response_data['project_id'] = project.id

        project_dir_name = f"{slugify(project.name)}-{project.id}"
        project_output_path = os.path.join(settings.MEDIA_ROOT, 'generated_projects', project_dir_name)
        
        project.generated_path = os.path.join('generated_projects', project_dir_name)
        project.save()

        files_to_write_to_disk = []
        generated_file_models = []

        # --- ORCHESTRATION LOGIC (NOW INFORMED BY IDENTIFIED TECH STACK) ---
        # Example: Generate Django Models from User Stories if backend is Django
        if identified_tech_stack.get('backend', '').lower() == 'django':
            themes = analysis_data.get('themes', [])
            for theme in themes:
                for epic in theme.get('epics', []):
                    for user_story in epic.get('user_stories', []):
                        if "model" in user_story.get('title', '').lower() or \
                           "data structure" in user_story.get('title', '').lower() or \
                           any("database" in task.lower() for task in user_story.get('tasks', [])):
                            
                            logger.info(f"Generating Django model for story: {user_story.get('story_id')}")
                            try:
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

        # Example: Generate React Components if frontend is React
        if identified_tech_stack.get('frontend', '').lower() == 'react':
            themes = analysis_data.get('themes', [])
            for theme in themes:
                for epic in theme.get('epics', []):
                    for user_story in epic.get('user_stories', []):
                        if "interface" in user_story.get('title', '').lower() or \
                           "UI" in user_story.get('title', '').lower() or \
                           "page" in user_story.get('title', '').lower():
                            
                            logger.info(f"Generating React component for story: {user_story.get('story_id')}")
                            try:
                                react_component_data = react_node_generator.generate_react_component(
                                    user_story,
                                    {'ui_description': user_story.get('title', '')},
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

        # --- Initial project structure (base files based on identified tech stack) ---
        # This part should also be dynamic based on tech stack
        base_files = [
            {'file_path': 'README.md', 'content': f"# {project.name}\n\nGenerated with {identified_tech_stack.get('frontend', 'N/A')} frontend and {identified_tech_stack.get('backend', 'N/A')} backend.", 'language': 'markdown'},
        ]
        if identified_tech_stack.get('backend', '').lower() == 'node.js':
            base_files.append({'file_path': 'package.json', 'content': '{"name": "node-app", "version": "1.0.0", "scripts": {"start": "node index.js"}, "dependencies": {"express": "^4.17.1"}}', 'language': 'json'})
            base_files.append({'file_path': 'index.js', 'content': '// Basic Node.js server setup\nconst express = require("express");\nconst app = express();\nconst PORT = process.env.PORT || 3000;\n\napp.get("/", (req, res) => {\n  res.send("Hello from Node.js Backend!");\n});\n\napp.listen(PORT, () => {\n  console.log(`Node.js server listening on port ${PORT}`);\n});', 'language': 'javascript'})
        elif identified_tech_stack.get('backend', '').lower() == 'django':
            # For Django, you'd generate manage.py, settings.py, urls.py etc.
            # This is complex and usually requires more specialized scaffolding.
            base_files.append({'file_path': 'backend/README.md', 'content': 'Django backend will go here.', 'language': 'markdown'})
        
        if identified_tech_stack.get('frontend', '').lower() == 'react':
            base_files.append({'file_path': 'frontend/package.json', 'content': '{"name": "react-app", "version": "0.1.0", "private": true, "dependencies": {"react": "^18.2.0", "react-dom": "^18.2.0"}}', 'language': 'json'})
            base_files.append({'file_path': 'frontend/src/App.js', 'content': 'import React from "react";\n\nfunction App() {\n  return (\n    <div className="App">\n      <header className="App-header">\n        <p>Hello from React Frontend!</p>\n      </header>\n    </div>\n  );\n}\n\nexport default App;', 'language': 'javascript'})
            base_files.append({'file_path': 'frontend/public/index.html', 'content': '<!DOCTYPE html>\n<html lang="en">\n<head><title>React App</title></head><body><div id="root"></div><script src="../src/index.js"></script></body></html>', 'language': 'html'})
        elif identified_tech_stack.get('frontend', '').lower() == 'plain html/css/js':
            base_files.append({'file_path': 'frontend/index.html', 'content': '<!DOCTYPE html>\n<html lang="en">\n<head><meta charset="UTF-8"><title>Plain HTML App</title></head><body><h1>Hello from Plain HTML!</h1><script src="script.js"></script></body></html>', 'language': 'html'})
            base_files.append({'file_path': 'frontend/script.js', 'content': 'console.log("Hello from plain JavaScript!");', 'language': 'javascript'})


        files_to_write_to_disk.extend(base_files)
        generated_file_models.extend([
            GeneratedFile(project=project, file_path=f['file_path'], file_type=f['language'])
            for f in base_files
        ])


        try:
            file_writer.write_files(project_dir_name, files_to_write_to_disk)
            logger.info(f"Successfully wrote {len(files_to_write_to_disk)} files to disk for project {project.id}")
        except Exception as write_e:
            project.status = 'FAILED'
            project.save()
            response_data['message'] = f"Failed to write generated files to disk: {write_e}"
            logger.error(f"Error writing files for project {project.id}: {write_e}", exc_info=True)
            return JsonResponse(response_data, status=500)

        GeneratedFile.objects.bulk_create(generated_file_models)
        logger.info(f"Created {len(generated_file_models)} GeneratedFile records for project {project.id}")

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
        logger.exception(f"An unexpected error occurred in generate_project_view: {e}")
        if 'project' in locals() and project.status == 'GENERATING':
            project.status = 'FAILED'
            project.save()
        response_data['message'] = f"An unexpected server error occurred: {e}"
        return JsonResponse(response_data, status=500)


@require_GET
# @login_required
def list_project_files(request, project_id):
    project = Project.objects.get(id=project_id) 
    
    files_info = []
    for generated_file in project.files.all().order_by('file_path'):
        files_info.append({
            'path': generated_file.file_path,
            'type': generated_file.file_type,
            'url': os.path.join(settings.MEDIA_URL, project.generated_path, generated_file.file_path)
        })
    
    return JsonResponse({'status': 'success', 'files': files_info})


@require_GET
# @login_required
def get_generated_file_content(request, project_id, file_path):
    project = Project.objects.get(id=project_id)
    
    abs_project_path = os.path.join(settings.MEDIA_ROOT, project.generated_path)
    abs_requested_file_path = os.path.abspath(os.path.join(abs_project_path, file_path))

    if not abs_requested_file_path.startswith(abs_project_path):
        logger.warning(f"Attempted directory traversal: {request.user} requested {file_path} outside {project.generated_path}")
        return JsonResponse({'error': 'Access denied: Invalid file path.'}, status=403)

    if not os.path.exists(abs_requested_file_path) or not os.path.isfile(abs_requested_file_path):
        return JsonResponse({'error': 'File not found.'}, status=404)

    try:
        with open(abs_requested_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        file_extension = os.path.splitext(file_path)[1].lstrip('.')
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
    project = Project.objects.get(id=project_id)
    
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
                archive_name = os.path.relpath(full_file_path, full_project_dir)
                zf.write(full_file_path, archive_name)
    
    zip_buffer.seek(0)
    response.write(zip_buffer.read())
    return response