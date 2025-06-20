# generate_app_code.py

import os
import json
import logging
import google.generativeai as genai
from datetime import datetime
from dotenv import load_dotenv
import re
import shutil

# Define the base directory for your boilerplate templates
# Using absolute path to ensure correct location
BOILERPLATE_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "boilerplate_templates")

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Gemini API Configuration ---
load_dotenv() # Load from .env file if it exists in the same directory or parent

try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    logger.info("Gemini API configured successfully.")
except KeyError:
    logger.error("GEMINI_API_KEY environment variable not set. Please set it in your .env file or system environment.")
    raise EnvironmentError("GEMINI_API_KEY not found. Cannot proceed without API key.")

GEMINI_MODEL_NAME = "gemini-1.5-flash"
gemini_model = genai.GenerativeModel(GEMINI_MODEL_NAME)
logger.info(f"Using Gemini model: {GEMINI_MODEL_NAME}")

#Helper functions (small resuable utilities)
def get_boilerplate_file_content(template_name: str, relative_file_paths: list) -> str:
    """
    Reads and formats content of specified files from a boilerplate template for AI context.

    Args:
        template_name (str): The name of the boilerplate folder (e.g., 'react-vite-ts-frontend').
        relative_file_paths (list): A list of file paths relative to the boilerplate template root
                                   (e.g., ['src/App.tsx', 'package.json']).

    Returns:
        str: Formatted string containing file paths and their contents,
             suitable for including in the AI prompt.
    """
    boilerplate_root_path = os.path.join(BOILERPLATE_TEMPLATES_DIR, template_name)
    context_content = ""

    for rel_path in relative_file_paths:
        file_full_path = os.path.join(boilerplate_root_path, rel_path)
        if os.path.exists(file_full_path) and os.path.isfile(file_full_path):
            try:
                with open(file_full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Truncate very long files if necessary to stay within context window limits.
                # Adjust this limit based on your model's context window.
                MAX_CONTENT_LENGTH = 1500 # Characters, adjust as needed
                if len(content) > MAX_CONTENT_LENGTH:
                    content = content[:MAX_CONTENT_LENGTH] + "\n... (truncated for brevity) ..."

                # Determine markdown language for syntax highlighting in prompt
                file_extension = os.path.splitext(rel_path)[1].lower()
                lang_map = {
                    '.ts': 'typescript', '.tsx': 'typescript', '.js': 'javascript', '.jsx': 'javascript',
                    '.json': 'json', '.css': 'css', '.html': 'html', '.py': 'python',
                    '.env': 'bash', '.md': 'markdown'
                }
                lang = lang_map.get(file_extension, '') # Default to no language if unknown

                context_content += f"File: {rel_path}\n"
                context_content += f"```{lang}\n{content}\n```\n\n"
                logger.debug(f"Added {rel_path} to AI context.")
            except Exception as e:
                logger.warning(f"Could not read file {file_full_path} for AI context: {e}")
        else:
            logger.warning(f"Boilerplate file not found for AI context: {file_full_path}")

    return context_content

#strip_indents_and_format
def strip_indents_and_format(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("Input to strip_indents_and_format must be a string.")

    lines = value.split('\n')
    trimmed_lines = [line.strip() for line in lines]
    rejoined_string = '\n'.join(trimmed_lines)
    result_without_leading_block_indent = rejoined_string.lstrip()
    final_result = re.sub(r'[\r\n]$', '', result_without_leading_block_indent)

    return final_result

#copy_boilerplate
def copy_boilerplate(template_name: str, destination_path: str) -> bool:
    """
    Copies a specified boilerplate template to a destination path.

    Args:
        template_name (str): The name of the boilerplate folder (e.g., 'react-vite-ts-frontend').
        destination_path (str): The path where the boilerplate should be copied.
    """
    source_path = os.path.join(BOILERPLATE_TEMPLATES_DIR, template_name)

    if not os.path.exists(source_path):
        print(f"Error: Boilerplate template '{template_name}' not found at {source_path}")
        return False

    # Ensure the destination directory exists
    os.makedirs(destination_path, exist_ok=True)

    try:
        # Copy contents of the template folder to the destination
        # Using copytree with dirs_exist_ok=True for Python 3.8+
        # If using older Python, you might need to handle directory existence manually or use a different strategy.
        shutil.copytree(source_path, destination_path, dirs_exist_ok=True)
        logger.info(f"Successfully copied boilerplate from '{source_path}' to '{destination_path}'")
        return True
    except shutil.Error as e:
        logger.error(f"Error copying boilerplate: {e}")
        return False
    except FileExistsError: # Catch this specifically if dirs_exist_ok is not available or desired for specific logic
        logger.error(f"Destination '{destination_path}' already exists and is not empty. Skipping copy.")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during boilerplate copy: {e}")
        return False

# Core Logic Functions
# --- Helper Function to Call AI ---
def get_ai_response(prompt_text: str) -> str:
    """
    Sends a prompt to the configured Gemini model and returns the response text,
    forcing it to be in application/json MIME type.
    """
    try:
        # Crucial change: Add the generation_config with response_mime_type
        response = gemini_model.generate_content(
            prompt_text,
            generation_config={
                "response_mime_type": "application/json"
            }
        )

        # When response_mime_type="application/json" is used,
        # response.text should directly contain the JSON string.
        # No stripping of markdown fences is typically needed.
        raw_json_string = response.text

        logger.info("Received AI response in JSON format.")
        return raw_json_string

    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}", exc_info=True)
        return ""

#determine_boilerplates
def determine_boilerplates(tech_stack_json: dict) -> dict:
    required_boilerplates = {}
    
    # Get the actual tech stack from the nested structure
    tech_stack = tech_stack_json.get("tech_stack", {})
    
    # Frontend
    frontend = tech_stack.get("frontend", {})
    frontend_framework = frontend.get("framework")
    frontend_build_tool = frontend.get("build_tool")
    
    logger.info(f"Detected frontend tech stack: {frontend}")
    
    if frontend_framework == "React" and frontend_build_tool == "Vite":
        required_boilerplates['frontend'] = "react_vite_ts"
    elif frontend_framework == "Next.js" and frontend_build_tool == "Vite":
        required_boilerplates['frontend'] = "next_tailwind"
    
    # Backend
    backend = tech_stack.get("backend", {})
    backend_language = backend.get("language")
    backend_framework = backend.get("framework")
    
    logger.info(f"Detected backend tech stack: {backend}")
    
    if backend_language == "Node.js" and backend_framework == "Express.js":
        required_boilerplates['backend'] = "node_js"
    elif backend_language == "Python" and backend_framework == "Flask":
        required_boilerplates['backend'] = "python_flask"

    logger.info(f"Required boilerplates: {required_boilerplates}")
    return required_boilerplates

#High-level orchestration functions
#orchestrate_code_generation
def orchestrate_code_generation(brd_analysis_json: dict, tech_stack_json: dict, feature_name: str):
    """
    Orchestrates code generation while maintaining the existing generated_code folder structure.
    Returns paths where boilerplates were copied.
    """
    # Use your existing generated_code directory
    generated_code_root = "generated_code"
    
    # Create timestamped folder within generated_code
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sanitized_feature_name = feature_name.replace(" ", "_").replace("/", "_")[:60].strip('_')
    project_output_dir = os.path.join(generated_code_root, f"{sanitized_feature_name}_{timestamp}")
    os.makedirs(project_output_dir, exist_ok=True)
    
    logger.info(f"Project directory created at: {project_output_dir}")

    # Determine which boilerplates are needed
    boilerplates_to_use = determine_boilerplates(tech_stack_json)
    copied_paths = {}

    # Copy the boilerplates
    if 'frontend' in boilerplates_to_use:
        frontend_dest = os.path.join(project_output_dir, "frontend")
        if copy_boilerplate(boilerplates_to_use['frontend'], frontend_dest):
            copied_paths['frontend'] = frontend_dest
            logger.info(f"Successfully copied frontend boilerplate to {frontend_dest}")
    if 'backend' in boilerplates_to_use:
        backend_dest = os.path.join(project_output_dir, "backend")
        if copy_boilerplate(boilerplates_to_use['backend'], backend_dest):
            copied_paths['backend'] = backend_dest
            logger.info(f"Successfully copied backend boilerplate to {backend_dest}")

    if not copied_paths:
        logger.error("No boilerplates were successfully copied. Cannot proceed with AI generation.")
        print("Error: No boilerplates were copied. Check your template directory or tech stack configuration.")
        return
    
    # --- Generate Frontend Code (if applicable) ---
    if 'frontend' in copied_paths:
        print(f"\n--- Generating frontend code ---")
        frontend_boilerplate_name = boilerplates_to_use['frontend']

        # Define key boilerplate files to include in the prompt context
        if frontend_boilerplate_name == "react_vite_ts":
             frontend_context_files = [
                'package.json',
                'vite.config.js',
                'index.html', # This is the root index.html
                'src/main.tsx',
                'src/App.tsx',
                'src/index.css',
                'eslint.config.js',
                'tsconfig.json',
                'tsconfig.node.json'
                # '.gitignore' and 'package-lock.json' are typically not modified by AI
            ]
        elif frontend_boilerplate_name == "next_tailwind":
             frontend_context_files = [
                'package.json',
                'tailwind.config.js',
                'app/layout.tsx',
                'app/page.tsx',
                'app/globals.css'
            ]
        else:
            frontend_context_files = [] # Add other frontend types if needed

        # Get content of boilerplate files to provide as context to the AI
        frontend_context = get_boilerplate_file_content(
            frontend_boilerplate_name,
            frontend_context_files
        )

        
        frontend_framework = tech_stack_json.get('frontend', {}).get('framework', 'unknown frontend framework')

        frontend_prompt = f"""
        The basic project structure for a {frontend_framework} frontend 
        ({frontend_boilerplate_name}) has already been generated and is in place at the root of the frontend project.

        Your task is to implement the following frontend features:
        {brd_analysis_json.get('frontend_features', 'Implement basic application logic as per BRD analysis.')}

        To achieve this, you **MUST** make necessary modifications to existing boilerplate files (e.g., `src/App.tsx`, `src/main.tsx` for routing, `package.json` for new dependencies). You should also create any new components, pages, or service files required.

        **Provide the *full and complete content* for any file you modify or create.** If you modify an existing boilerplate file, ensure you output its entire new content, not just the changes.
        List files with their relative paths from the frontend project root, followed by their content.

        --- Existing Frontend Files Context ---
        {frontend_context}

        --- Requested Frontend Files ---
        """
        frontend_ai_response = get_ai_response(frontend_prompt)
        save_generated_code(frontend_ai_response, copied_paths['frontend'])
        print(f"Frontend code generation requested. Output directory: {copied_paths['frontend']}")

    # --- Generate Backend Code (if applicable) ---
    if 'backend' in copied_paths:
        print(f"\n--- Generating backend code ---")
        backend_boilerplate_name = boilerplates_to_use['backend']

        # Define key boilerplate files to include in the prompt context
        if backend_boilerplate_name == "node_js":
            backend_context_files = [
                'package.json',
                'tsconfig.json',
                '.env.example',
                'eslint.config.js',
                'src/routes/health.ts',
                'src/routes/index.ts' # This is likely your main routing file
                # '.gitignore', 'package-lock.json', and 'README.md' are typically not modified by AI
            ]
        elif backend_boilerplate_name == "python_flask":
            backend_context_files = [
                'requirements.txt',
                'app.py',
                '.env.example'
            ]
        else:
            backend_context_files = [] # Add other backend types if needed

        # Get content of boilerplate files to provide as context to the AI
        backend_context = get_boilerplate_file_content(
            backend_boilerplate_name,
            backend_context_files
        )

        backend_framework = tech_stack_json.get('backend', {}).get('framework', 'unknown backend framework')
        backend_language = tech_stack_json.get('backend', {}).get('language', 'unknown backend language')

        backend_prompt = f"""
        The basic project structure for a {backend_language} + {backend_framework} backend
        ({backend_boilerplate_name}) has already been generated and is in place at the root of the backend project.

        Your task is to implement the following backend functionalities:
        {brd_analysis_json.get('backend_features', 'Implement basic API endpoints as per BRD analysis.')}

        To achieve this, you **MUST** make necessary modifications to existing boilerplate files (e.g., `src/index.ts` for adding new routes/middleware, `package.json` for new dependencies, `src/data-source.ts` for entities). You should also create any new routes, controllers, services, or database models/entities required.

        **Provide the *full and complete content* for any file you modify or create.** If you modify an existing boilerplate file, ensure you output its entire new content, not just the changes.
        List files with their relative paths from the backend project root, followed by their content.

        --- Existing Backend Files Context ---
        {backend_context}

        --- Requested Backend Files ---
        """
        backend_ai_response = get_ai_response(backend_prompt)
        save_generated_code(backend_ai_response, copied_paths['backend'])
        print(f"Backend code generation requested. Output directory: {copied_paths['backend']}")

    print(f"\nOrchestration complete. Boilerplates are in {project_output_dir}. AI will now add/modify code.")
    return copied_paths

# --- Code Generation Function ---
def generate_code_from_requirements(brd_analysis_json, tech_stack_json, specific_feature_prompt, default_design_prompt):
    """
    Generates code based on the BRD analysis, identified tech stack,
    and a specific prompt for the feature to be coded.
    
    Args:
        brd_analysis_json (dict): The structured BRD analysis (Themes, Epics, User Stories, Tasks).
        tech_stack_json (dict): The identified tech stack for frontend/backend.
        specific_feature_prompt (str): A natural language description of what code to generate (e.g., "login page", "user registration API").
        
    Returns:
        str: AI's response, expected to be a JSON string containing file paths and code content.
    """
    
    # Construct a comprehensive prompt for the AI
    # This prompt is critical! Be very clear and structured.
    prompt = f"""
    You are an expert software architect and senior full-stack developer. Your task is to generate production-ready code based on provided project requirements and a specified technology stack.

    {default_design_prompt}

    Here is the high-level analysis of a Business Requirement Document (BRD):
    ---BRD Analysis---
    {json.dumps(brd_analysis_json, indent=2)}
    ---END BRD Analysis---

    Here is the identified technology stack for the project:
    ---Tech Stack---
    {json.dumps(tech_stack_json, indent=2)}
    ---END Tech Stack---

    Based on the above information, generate the necessary code for the following specific feature(s):
    "{specific_feature_prompt}"

    **Important Instructions:**
    1.  **Output Format:** Provide the code for multiple files. Respond strictly in a single JSON object.
        The JSON object should have a key `files`. The value of `files` should be a list of objects.
        Each object in the `files` list must have two keys: `file_path` (string) and `content` (string).
        
        Example JSON structure:
        ```json
        {{
          "files": [
            {{
              "file_path": "frontend/src/pages/LoginPage.js",
              "content": "import React from 'react';\\n// ... React login page code here"
            }},
            {{
              "file_path": "backend/routes/auth.js",
              "content": "const express = require('express');\\n// ... Express auth routes here"
            }},
            {{
              "file_path": "backend/models/User.js",
              "content": "// ... User model/schema here"
            }}
          ]
        }}
        ```
    2.  **Code Quality:** Generate production-ready, clean, well-commented, and idiomatic code for the specified tech stack. Include necessary imports, basic error handling, and placeholder comments for areas needing further business logic.
    3.  **File Paths:** Provide realistic and conventional file paths relative to a project root (e.g., `frontend/src/components/`, `backend/routes/`, `backend/models/`, `database/migrations/`).
    4.  **Completeness:** Provide all necessary files for the requested feature(s) to be functional in a basic sense (e.g., if asking for a login page, include the UI, and the corresponding backend API endpoint, and any necessary model/schema).
    5.  **Scope:** Strictly adhere to the requested features in "{specific_feature_prompt}". Do not generate code for unrelated features unless explicitly asked.
    6.  **No Explanations Outside JSON:** Do not include any conversational text, explanations, or markdown outside the JSON structure. **The entire response from the AI should be the JSON string only.**
    """

    logger.info(f"Generating code for: {specific_feature_prompt}")
    return get_ai_response(prompt)

# --- Function to Save Generated Code to Files ---
def save_generated_code(ai_response_json_str, output_base_dir="generated_code", project_paths=None):
    """
    Parses the AI's JSON response and saves the code content into respective files.
    Now supports both traditional saving and boilerplate-integrated saving.
    
    Args:
        ai_response_json_str (str): The raw JSON string received from the AI
        output_base_dir (str): Base directory for traditional saving (default: "generated_code")
        project_paths (dict): Optional - {'frontend': path, 'backend': path} for boilerplate integration
    """
    try:
        response_data = json.loads(ai_response_json_str)
        if "files" not in response_data or not isinstance(response_data["files"], list):
            logger.error("AI response is not in the expected 'files' JSON format")
            print("AI Response was not in expected JSON format.")
            print(f"Raw AI Response:\n{ai_response_json_str}")
            return

        # NEW: Determine save mode
        use_boilerplate = project_paths is not None
        
        if use_boilerplate:
            logger.info("Saving files into boilerplate project structure")
        else:
            # Traditional saving with timestamped folder
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            feature_dir_name = specific_feature_prompt.replace(" ", "_").replace("/", "_")[:60].strip('_')
            full_output_dir = os.path.join(output_base_dir, f"{feature_dir_name}_{timestamp}")
            os.makedirs(full_output_dir, exist_ok=True)
            logger.info(f"Saving generated code to: {full_output_dir}")

        for file_info in response_data["files"]:
            file_path = file_info.get("file_path")
            content = file_info.get("content")

            if not file_path or content is None:
                logger.warning(f"Skipping malformed file entry: {file_info}")
                continue

            # NEW: Handle both saving modes
            if use_boilerplate:
                # Boilerplate-integrated saving
                if file_path.startswith("frontend/"):
                    full_path = os.path.join(project_paths['frontend'], file_path)
                elif file_path.startswith("backend/"):
                    full_path = os.path.join(project_paths['backend'], file_path)
                else:
                    logger.warning(f"Skipping file with invalid path prefix: {file_path}")
                    continue
            else:
                # Traditional saving
                full_path = os.path.join(full_output_dir, file_path)
                abs_output_dir = os.path.abspath(full_output_dir)
                abs_file_path = os.path.abspath(full_path)
                
                # Security check
                if not abs_file_path.startswith(abs_output_dir):
                    logger.warning(f"Skipping potentially malicious path: {file_path}")
                    continue

            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Saved: {full_path}")
        
        if not use_boilerplate:
            print(f"\nCode generation complete. Files saved to: {os.path.abspath(full_output_dir)}")
            print("You can now navigate to test the generated code.")

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response as JSON: {e}", exc_info=True)
        print("Error: Invalid JSON response from AI.")
        print(f"Raw Response:\n{ai_response_json_str}")
    except Exception as e:
        logger.critical(f"Error while saving files: {e}", exc_info=True)

# --- Main Execution Block ---
if __name__ == "__main__":
    logger.info("--- Starting Code Generation Test Script ---")

    # --- INPUT 1: Default Design Prompt ---
    default_design_prompt = """
        For all designs I ask you to make, have them be beautiful, not cookie cutter. Make webpages that are fully featured and worthy for production.

        By default, this template supports JSX syntax with Tailwind CSS classes, React hooks, and Lucide React for icons. Do not install other packages for UI themes, icons, etc unless absolutely necessary or I request them.

        Use icons from lucide-react for logos.
        """

    # --- INPUT 2: Structured BRD Analysis Output ---
    brd_analysis_from_app = {
        "project_summary": "Manage registration, authentication, and authorization for dealerships, agencies, and super admins. Enable dealerships to post jobs and agencies to manage and share candidate data. Facilitate communication and collaboration between dealerships and agencies. Provide dashboards for super admins, dealership HRs, and agencies to track key metrics.",
        "themes": [
            {
                "theme_name": "User Management",
                "description": "Manage registration, authentication, and authorization for dealerships, agencies, and super admins.",
                "epics": [
                    {
                        "epic_name": "Registration and Authentication",
                        "description": "Implement user registration, login, and authentication for different user roles.",
                        "user_stories": [
                            {
                                "story_id": "US-001",
                                "title": "As a dealership HR manager, I want to register on the platform using my Mahindra Dealership Code, so that I can post jobs.",
                                "acceptance_criteria": [
                                    "The system should accept valid Mahindra Dealership Codes.",
                                    "A unique account is created for each dealership.",
                                    "An email confirmation is sent upon successful registration."
                                ],
                                "tasks": [
                                    "Create user registration API endpoint",
                                    "Develop frontend registration form for dealerships",
                                    "Implement Mahindra Dealership Code verification",
                                    "Create 'Dealership' model in the database",
                                    "Send email confirmation upon successful registration"
                                ]
                            },
                            {
                                "story_id": "US-002",
                                "title": "As a recruitment agency, I want to register on the platform and request approval, so that I can access and utilize the platform's features.",
                                "acceptance_criteria": [
                                    "The system allows agencies to submit a registration request.",
                                    "The Super Admin receives notification of new registration requests.",
                                    "Agencies receive a notification upon approval or rejection."
                                ],
                                "tasks": [
                                    "Create user registration API endpoint for agencies",
                                    "Develop frontend registration form for agencies",
                                    "Implement admin approval workflow",
                                    "Create 'Agency' model in the database",
                                    "Send notifications (email and in-app) upon approval/rejection"
                                ]
                            },
                            {
                                "story_id": "US-003",
                                "title": "As a super admin, I want to approve or reject agency registration requests, so that I can control access to the platform.",
                                "acceptance_criteria": [
                                    "The Super Admin has a dashboard to review pending requests.",
                                    "The system allows the Super Admin to approve or reject requests.",
                                    "Approved agencies receive platform access; rejected agencies receive a notification."
                                ],
                                "tasks": [
                                    "Develop admin dashboard for managing agency registrations",
                                    "Implement approval/rejection functionality",
                                    "Send notifications to agencies upon approval/rejection",
                                    "Manage user roles and permissions"
                                ]
                            }
                        ]
                    }
                ]
            },
            {
                "theme_name": "Job Posting and Candidate Management",
                "description": "Enable dealerships to post jobs and agencies to manage and share candidate data.",
                "epics": [
                    {
                        "epic_name": "Job Posting",
                        "description": "Implement functionality for dealerships to post jobs with auto-filled details from a master list.",
                        "user_stories": [
                            {
                                "story_id": "US-004",
                                "title": "As a dealership HR manager, I want to post a job opening and have job details auto-filled from a master list, so that I can save time.",
                                "acceptance_criteria": [
                                    "The system displays a list of predefined job titles.",
                                    "Selecting a job title auto-populates relevant fields.",
                                    "Dealership HR can modify auto-populated fields if needed.",
                                    "Jobs are only posted by verified dealerships."
                                ],
                                "tasks": [
                                    "Create job posting API endpoint",
                                    "Develop frontend job posting form with auto-fill functionality",
                                    "Create 'Job' model in the database",
                                    "Implement master data integration for job details",
                                    "Implement Mahindra Dealership Code verification for job posting"
                                ]
                            }
                        ]
                    },
                    {
                        "epic_name": "Candidate Management",
                        "description": "Allow agencies to upload candidate data, manage candidate profiles, and share candidates with dealerships.",
                        "user_stories": [
                            {
                                "story_id": "US-005",
                                "title": "As a recruitment agency, I want to upload candidate data via CSV, so that I can efficiently manage a large number of candidates.",
                                "acceptance_criteria": [
                                    "The system supports CSV file uploads.",
                                    "The system checks for duplicate profiles based on email and phone number.",
                                    "A report is generated indicating unique and duplicate profiles.",
                                    "Unique profiles are added to the agency's candidate pool."
                                ],
                                "tasks": [
                                    "Implement CSV file upload functionality",
                                    "Develop duplicate profile detection algorithm",
                                    "Create 'Candidate' model in the database",
                                    "Generate import report for agencies",
                                    "Implement frontend for CSV upload and report viewing"
                                ]
                            },
                            {
                                "story_id": "US-006",
                                "title": "As a recruitment agency, I want to share candidates with dealerships for specific job postings, so that I can recommend suitable candidates.",
                                "acceptance_criteria": [
                                    "Agencies can select candidates from their pool or upload new ones.",
                                    "Dealerships can view candidate profiles (without contact details).",
                                    "A matching percentage indicates candidate suitability.",
                                    "Duplicate candidate profiles are prevented from being shared."
                                ],
                                "tasks": [
                                    "Implement candidate sharing functionality",
                                    "Develop candidate matching algorithm",
                                    "Create UI to display candidate profiles (excluding contact details)",
                                    "Implement duplicate candidate check before sharing"
                                ]
                            }
                        ]
                    }
                ]
            },
            {
                "theme_name": "Communication and Collaboration",
                "description": "Facilitate communication and collaboration between dealerships and agencies.",
                "epics": [
                    {
                        "epic_name": "Chat Functionality",
                        "description": "Implement a chat feature for communication between dealerships and agencies after candidate selection.",
                        "user_stories": [
                            {
                                "story_id": "US-007",
                                "title": "As a dealership HR manager, I want to chat with agencies after a candidate is selected, so that I can coordinate interviews and share information.",
                                "acceptance_criteria": [
                                    "A chat interface is available post-candidate selection.",
                                    "Chat history is preserved.",
                                    "Notifications for new messages are sent."
                                ],
                                "tasks": [
                                    "Implement real-time chat functionality",
                                    "Integrate chat into candidate profile views",
                                    "Implement notification system for new messages",
                                    "Store chat history in the database"
                                ]
                            }
                        ]
                    }
                ]
            },
            {
                "theme_name": "Reporting and Dashboards",
                "description": "Provide dashboards for super admins, dealership HRs, and agencies to track key metrics.",
                "epics": [
                    {
                        "epic_name": "Dashboard Implementation",
                        "description": "Develop dashboards for different user roles to visualize key performance indicators.",
                        "user_stories": [
                            {
                                "story_id": "US-008",
                                "title": "As a super admin, I want a customizable dashboard to view key platform metrics, so that I can monitor platform performance and make informed decisions.",
                                "acceptance_criteria": [
                                    "The dashboard displays key metrics (e.g., top jobs, top dealerships, top agencies).",
                                    "The dashboard is customizable.",
                                    "Data is displayed in clear and concise visualizations."
                                ],
                                "tasks": [
                                    "Develop super admin dashboard UI",
                                    "Implement data aggregation and visualization",
                                    "Implement dashboard customization options",
                                    "Connect dashboard to database for real-time data"
                                ]
                            },
                            {
                                "story_id": "US-009",
                                "title": "As a dealership HR manager, I want a dashboard to track job postings, candidate applications, and interview schedules, so that I can effectively manage the recruitment process.",
                                "acceptance_criteria": [
                                    "The dashboard displays key metrics relevant to dealership HRs (e.g., top jobs, resumes received, candidates selected).",
                                    "Data is displayed in clear and concise visualizations."
                                ],
                                "tasks": [
                                    "Develop dealership HR dashboard UI",
                                    "Implement data aggregation and visualization for dealership HRs",
                                    "Connect dashboard to database for real-time data"
                                ]
                            },
                            {
                                "story_id": "US-010",
                                "title": "As a recruitment agency, I want a dashboard to track candidate profiles, job applications, and candidate status, so that I can effectively manage my candidate pool and track performance.",
                                "acceptance_criteria": [
                                    "The dashboard displays key metrics relevant to agencies (e.g., candidate profiles shared, candidate status, top positions closed).",
                                    "Data is displayed in clear and concise visualizations."
                                ],
                                "tasks": [
                                    "Develop agency dashboard UI",
                                    "Implement data aggregation and visualization for agencies",
                                    "Connect dashboard to database for real-time data"
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }


    # --- INPUT 3: Identified Tech Stack ---
    tech_stack_identified = {
        "status": "success",
        "tech_stack": {
            "frontend": {
                "framework": "React",
                "state_management": "Zustand",
                "ui_components": "Material-UI",
                "routing": "React Router",
                "testing": "Jest + React Testing Library",
                "linting": "ESLint + Prettier",
                "build_tool": "Vite",
                "reasoning": "React provides a robust and widely adopted framework for building complex user interfaces. Zustand offers a lightweight and performant state management solution, suitable for the project's scope. Material-UI provides a rich set of pre-built components, accelerating development and ensuring consistency. React Router handles navigation efficiently. Jest and React Testing Library offer comprehensive testing capabilities. ESLint and Prettier ensure code quality and maintainability. Vite is a fast build tool improving developer experience."
            },
            "backend": {
                "language": "Node.js",
                "framework": "Express.js",
                "database": "PostgreSQL",
                "orm": "TypeORM", # Note: AI used Sequelize in actual code, TypeORM was requested.
                "caching": "Redis",
                "authentication": "JWT",
                "testing": "Jest + Supertest",
                "monitoring": "Prometheus + Grafana",
                "reasoning": "Node.js with Express.js provides a flexible and scalable backend solution. PostgreSQL is a robust, open-source relational database that handles complex data structures well. TypeORM provides an Object-Relational Mapper (ORM) for easier database interactions. Redis is used for caching frequently accessed data to improve performance. JWT is a secure and widely adopted authentication standard. Jest and Supertest enable comprehensive testing of backend functionalities. Prometheus and Grafana provide comprehensive monitoring and alerting."
            }
        },
        "raw_ai_response": "{\"frontend\": {\"framework\": \"React\", \"state_management\": \"Zustand\", \"ui_components\": \"Material-UI\", \"routing\": \"React Router\", \"testing\": \"Jest + React Testing Library\", \"linting\": \"ESLint + Prettier\", \"build_tool\": \"Vite\", \"reasoning\": \"React provides a robust and widely adopted framework for building complex user interfaces. Zustand offers a lightweight and performant state management solution, suitable for the project's scope. Material-UI provides a rich set of pre-built components, accelerating development and ensuring consistency. React Router handles navigation efficiently. Jest and React Testing Library offer comprehensive testing capabilities. ESLint and Prettier ensure code quality and maintainability. Vite is a fast build tool improving developer experience.\"}, \"backend\": {\"language\": \"Node.js\", \"framework\": \"Express.js\", \"database\": \"PostgreSQL\", \"orm\": \"TypeORM\", \"caching\": \"Redis\", \"authentication\": \"JWT\", \"testing\": \"Jest + Supertest\", \"monitoring\": \"Prometheus + Grafana\", \"reasoning\": \"Node.js with Express.js provides a flexible and scalable backend solution. PostgreSQL is a robust, open-source relational database that handles complex data structures well. TypeORM provides an Object-Relational Mapper (ORM) for easier database interactions. Redis is used for caching frequently accessed data to improve performance. JWT is a secure and widely adopted authentication standard. Jest and Supertest enable comprehensive testing of backend functionalities. Prometheus and Grafana provide comprehensive monitoring and alerting.\"}}"
    }

    # --- INPUT 4: Specific Feature Prompt ---
    specific_feature_prompt = """
        Your task is to implement a **login and signup functionality** for a full-stack application.
        **Crucially, the backend should use IN-MEMORY storage only; DO NOT implement any database models, database connections, or persistence logic.**

        You have access to the existing boilerplate code as provided in the context below. You MUST modify existing boilerplate files (like main entry points) and create new files as needed.

        === FRONTEND (React + Vite + TS) ===
        Your goal is to provide the user interface for login and signup, and integrate it with the backend API endpoints.

        Files to generate/modify:

        1.  **Login Page:**
            * Path: `src/pages/auth/LoginPage.tsx`
            * Requirements:
                * React functional component.
                * Email and Password input fields.
                * A "Login" button.
                * Basic client-side form validation (e.g., email format, password length).
                * A submit handler that calls the backend `/api/auth/login` endpoint using `src/services/authService.ts`.
                * Handle successful login (e.g., store a mock JWT token in memory/localStorage, redirect to a dashboard/home page).
                * Handle basic error display (e.g., "Invalid credentials").
                * "Remember me" checkbox.
                * "Forgot password" link (can be a placeholder).
                * Link to Signup page.

        2.  **Signup Page:**
            * Path: `src/pages/auth/SignupPage.tsx`
            * Requirements:
                * React functional component.
                * Fields: Name, Email, Password, Confirm Password.
                * Role selection (e.g., a simple dropdown or radio buttons for "Dealership" / "Agency").
                * Basic client-side form validation (e.g., email format, password match).
                * A submit handler that calls the backend `/api/auth/signup` endpoint using `src/services/authService.ts`.
                * Handle successful signup (e.g., redirect to login page or show success message).
                * Handle basic error display (e.g., "Email already registered").
                * Link back to Login page.

        3.  **Auth Service:**
            * Path: `src/services/authService.ts`
            * Requirements:
                * Provides functions for `login(email, password)` and `signup(name, email, password, role)`.
                * Uses `fetch` or `axios` (if you manually add it to package.json) for API calls.
                * Handles mock JWT token storage (e.g., `localStorage.setItem('token', 'mock_jwt_token')`).
                * Basic error handling for API responses.

        4.  **Application Routing:**
            * Modify `src/App.tsx` to set up basic routing using `react-router-dom`.
            * Include routes for `/login` (mapping to `LoginPage`), `/signup` (mapping to `SignupPage`), and a default `/` route (e.g., a simple placeholder or redirect to login).
            * **Do NOT add Protected Routes yet.** Just basic routing.

        === BACKEND (Node.js + Express + TS) ===
        Your goal is to provide the API endpoints for login and signup. **All user data MUST be stored and managed IN-MEMORY only. NO DATABASE INTERACTION.**

        Files to generate/modify:

        1.  **Auth Routes:**
            * Path: `src/routes/authRoutes.ts`
            * Endpoints:
                * `POST /api/auth/login`: Handles user login. Calls `authController.login`.
                * `POST /api/auth/signup`: Handles user registration. Calls `authController.signup`.
            * No JWT authentication middleware needed at the route level for this in-memory mock.

        2.  **Auth Controller:**
            * Path: `src/controllers/authController.ts`
            * Requirements:
                * **Implement IN-MEMORY user storage:** Maintain a simple `Array` or `Map` to store mock user objects (e.g., `{ id, name, email, password_hash, role }`). For simplicity, you can mock password hashing with a simple string concatenation or a placeholder.
                * **`signup(req, res)` method:**
                    * Accepts `name`, `email`, `password`, `role`.
                    * Perform basic input validation.
                    * Check if email already exists in in-memory storage. If so, return 409 Conflict.
                    * If new, add user to in-memory storage. Generate a simple `id`.
                    * Return 201 Created with a success message.
                * **`login(req, res)` method:**
                    * Accepts `email`, `password`.
                    * Find user by email in in-memory storage.
                    * If user not found or password doesn't match (mock password check), return 401 Unauthorized.
                    * If successful, return 200 OK with a mock JWT token (e.g., `{ token: "mock_jwt_token_for_" + user.email }`).
                * No actual password hashing or JWT generation needed for this in-memory mock.

        3.  **Backend Server Entry Point:**
            * Modify `src/index.ts` to import and use the `authRoutes.ts`. Mount it at `/api/auth`.

        === IMPORTANT INSTRUCTIONS ===
        1.  **FOCUS ON IN-MEMORY BACKEND:** Absolutely no database-related code (no TypeORM, no database connections, no `src/entities/User.ts` or similar). All user data handling is strictly in-memory.
        2.  **Generate ONLY new or modified files** based on the requirements above. If you modify an existing boilerplate file, output its *full and complete new content*.
        3.  Ensure the frontend and backend are designed to **interact with each other** using the specified API endpoints.
        4.  The final generated project should require only `npm install` (in both `frontend` and `backend` directories) and `npm run dev` (in each directory) to run.
        5.  **For Frontend:** Use React functional components with hooks.
        6.  **For Backend:** Use Express.js, TypeScript, async/await with basic error handling.

        Output format (STRICT JSON, follow this structure EXACTLY):
        ```json
        {
        "files": [
            {
            "file_path": "frontend/src/pages/auth/LoginPage.tsx",
            "content": "/* Your generated React code for Login page */",
            "overwrite": false
            },
            {
            "file_path": "frontend/src/pages/auth/SignupPage.tsx",
            "content": "/* Your generated React code for Signup page */",
            "overwrite": false
            },
            {
            "file_path": "frontend/src/services/authService.ts",
            "content": "/* Your generated Auth Service code */",
            "overwrite": false
            },
            {
            "file_path": "frontend/src/App.tsx",
            "content": "/* FULL content of App.tsx with routing changes */",
            "overwrite": true
            },
            {
            "file_path": "backend/src/routes/authRoutes.ts",
            "content": "/* Your generated Auth Routes code */",
            "overwrite": false
            },
            {
            "file_path": "backend/src/controllers/authController.ts",
            "content": "/* Your generated Auth Controller code */",
            "overwrite": false
            },
            {
            "file_path": "backend/src/index.ts",
            "content": "/* FULL content of backend index.ts with authRoutes import/use */",
            "overwrite": true
            }
        ]
        }
        """.strip()

    # 1. Copy boilerplates first
    project_paths = orchestrate_code_generation(
        brd_analysis_json=brd_analysis_from_app,
        tech_stack_json=tech_stack_identified,
        feature_name="user_auth"  # Or make this dynamic
    )
    # --- Call the Code Generation Function ---
    ai_raw_response = generate_code_from_requirements(
        brd_analysis_json=brd_analysis_from_app,
        tech_stack_json=tech_stack_identified,
        specific_feature_prompt=specific_feature_prompt,
        default_design_prompt=default_design_prompt
    )

    # --- Save the Generated Code ---
    save_generated_code(ai_raw_response, project_paths=project_paths)

    logger.info("--- Code Generation Test Script Finished ---")