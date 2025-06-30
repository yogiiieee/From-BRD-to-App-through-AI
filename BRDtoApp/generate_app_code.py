# generate_app_code.py

import os
import json
import logging
import google.generativeai as genai
from datetime import datetime
from dotenv import load_dotenv
import re
import shutil
import textwrap
from jinja2 import Environment, FileSystemLoader

# Define the base directory for your boilerplate templates
# Using absolute path to ensure correct location
BOILERPLATE_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "boilerplate_templates")
PROMPT_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")

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

jinja_env = Environment(
    loader=FileSystemLoader(PROMPT_TEMPLATES_DIR),
    trim_blocks=True,
    lstrip_blocks=True
)

def load_prompt_template(template_name: str, **context) -> str:
    """
    Loads a Jinja2 template by name from the PROMPT_TEMPLATES_DIR
    and renders it with the provided context variables.
    """
    try:
        template = jinja_env.get_template(template_name)
        rendered_string = template.render(**context)
        return rendered_string.strip()
    except Exception as e:
        logger.error(f"Error loading or rendering template '{template_name}': {e}")
        raise # Re-raise the exception to stop execution if a prompt can't be loaded

#Helper functions (small resuable utilities)
def get_boilerplate_file_content(project_root_path: str, files_to_include: list) -> str:
    """
    Reads and formats content of specified files from a boilerplate template for AI context.

    Args:
        project_root_path (str): The root directory path of the project.
        files_to_include (list): A list of file paths relative to the boilerplate template root
                                    (e.g., ['src/App.tsx', 'package.json']).

    Returns:
        str: Formatted string containing file paths and their contents,
                suitable for including in the AI prompt.
    """
    base_path = project_root_path # project_root_path is already the correct base path to read from
    context_content = ""

    for rel_path in files_to_include:
        file_full_path = os.path.join(base_path, rel_path)
        if os.path.exists(file_full_path) and os.path.isfile(file_full_path):
            try:
                with open(file_full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
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
    """
    Removes common leading indentation from a multiline string and then
    strips any remaining leading/trailing whitespace (including newlines).
    This function is designed to clean up multi-line Python string literals
    (like docstrings or prompts) while preserving their internal formatting.

    Args:
        value (str): The input string to process.

    Returns:
        str: The cleaned string with common leading indentation and
                outer whitespace removed.

    Raises:
        TypeError: If the input value is not a string.
    """
    if not isinstance(value, str):
        raise TypeError("Input to strip_indents_and_format must be a string.")
    dedented_string = textwrap.dedent(value)
    final_result = dedented_string.strip()

    return final_result

#copy_boilerplate
def copy_boilerplate(project_root_path: str, destination_path: str) -> bool:
    """
    Copies a specified boilerplate template to a destination path.

    Args:
        project_root_path (str): The root directory path of the project.
        destination_path (str): The path where the boilerplate should be copied.
    """
    source_path = os.path.join(project_root_path)

    if not os.path.exists(source_path):
        print(f"Error: Boilerplate template not found at {source_path}")
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
    
    if frontend_framework == "React.js" and frontend_build_tool == "Vite":
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

#extract_relevant_brd_features
def extract_relevant_brd_features(
    full_brd_analysis_json: dict,
    specific_feature_request_text: str
    ) -> dict:
    """
    Calls an AI to extract BRD themes, epics, and user stories relevant to a specific feature.

    Args:
        full_brd_analysis_json (dict): The complete, parsed BRD analysis dictionary.
        specific_feature_request_text (str): The specific feature prompt text (e.g., login/signup).

    Returns:
        dict: A subset of the BRD analysis (themes, epics, user stories) relevant to the feature,
              or an empty dictionary if extraction fails.
    """
    logger.info(f"Extracting relevant BRD features for: '{specific_feature_request_text[:80]}...'")

    try:
        # Load the dedicated BRD feature extractor prompt template
        extractor_template = jinja_env.get_template("brd_feature_extractor_prompt.j2")

        # Render the prompt with the full BRD and the specific feature request
        extraction_prompt = extractor_template.render(
            full_brd_analysis_json=full_brd_analysis_json,
            specific_feature_request=specific_feature_request_text
        )

        # Assuming gemini_model is a global instance of genai.GenerativeModel
        # (This is the first AI call in the multi-stage process)
        api_response = gemini_model.generate_content(extraction_prompt)
        ai_extracted_json_str = api_response.text

        # Optional: Log token usage for this extraction call
        if api_response.usage_metadata:
            logger.info(f"BRD Extraction Call - Input Tokens: {api_response.usage_metadata.prompt_token_count}, Output Tokens: {api_response.usage_metadata.candidates_token_count}, Total Tokens: {api_response.usage_metadata.total_token_count}")

        # Parse the JSON response from the extraction AI
        extracted_brd_data = json.loads(ai_extracted_json_str)

        logger.info("Successfully extracted relevant BRD features.")
        return extracted_brd_data

    except Exception as e:
        logger.error(f"Error during BRD feature extraction AI call: {e}")
        return {"project_summary": "Error during extraction, check logs.", "themes": []} # Return a default structure on error

#High-level orchestration functions
#orchestrate_code_generation
def orchestrate_code_generation(brd_analysis_json: dict, tech_stack_json: dict, project_output_dir: str):
    """
    Orchestrates code generation while maintaining the existing generated_code folder structure.
    Returns paths where boilerplates were copied.
    """

    # Determine which boilerplates are expected based on tech stack
    boilerplates_to_use = determine_boilerplates(tech_stack_json)

    # Construct the actual paths where boilerplates *should* exist within project_output_dir
    # This dictionary will store the actual paths where the AI should read/write
    copied_paths = {}   
    
    if 'frontend' in boilerplates_to_use:
        actual_frontend_folder_name = boilerplates_to_use['frontend']
        frontend_path_in_project = os.path.join(project_output_dir, "frontend")
        if os.path.exists(frontend_path_in_project) and os.path.isdir(frontend_path_in_project):
            copied_paths['frontend'] = frontend_path_in_project
        else:
            logger.warning(f"Frontend boilerplate directory not found or is not a directory at {frontend_path_in_project}. Skipping frontend generation.")

    if 'backend' in boilerplates_to_use:
        actual_backend_folder_name = boilerplates_to_use['backend']
        backend_path_in_project = os.path.join(project_output_dir, "backend")
        if os.path.exists(backend_path_in_project) and os.path.isdir(backend_path_in_project):
            copied_paths['backend'] = backend_path_in_project
        else:
            logger.warning(f"Backend boilerplate directory not found or is not a directory at {backend_path_in_project}. Skipping backend generation.")

    if not copied_paths:
        logger.error(f"No boilerplate directories found in {project_output_dir} as expected based on tech stack. Cannot proceed with AI generation.")
        print(f"Error: No boilerplate directories found in {project_output_dir}. Please ensure boilerplates are copied manually to this location.")
        return # Exit if no relevant paths are found
    # END ADDED LINES
    
    # --- Generate Frontend Code (if applicable) ---
    if 'frontend' in copied_paths:
        print(f"\n--- Generating frontend code ---")
        frontend_boilerplate_name = actual_frontend_folder_name

        # Define key boilerplate files to include in the prompt context
        if frontend_boilerplate_name == "react_vite_ts":
                frontend_context_files = [
                'package.json',
                'vite.config.ts',
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
            copied_paths['frontend'],
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
        backend_boilerplate_name = actual_backend_folder_name

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
            copied_paths['backend'],
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

    print(f"\nAI code generation initiated for project at: {project_output_dir}. AI will now add/modify code.")
    return copied_paths

# --- Code Generation Function ---
def generate_code_from_requirements(brd_analysis_json, tech_stack_json, specific_feature_prompt, default_design_prompt, system_prompt_architecture):
    """
    Generates code based on the BRD analysis, identified tech stack,
    and a specific prompt for the feature to be coded.
    
    Args:
        brd_analysis_json (dict): The structured BRD analysis (Themes, Epics, User Stories, Tasks).
        tech_stack_json (dict): The identified tech stack for frontend/backend.
        specific_feature_prompt (str): A natural language description of what code to generate (e.g., "login page", "user registration API").
        default_design_prompt (str): Design guidelines and aesthetic principles.
        system_prompt_architecture (str): Overarching system architecture rules and instructions for the AI.    
    Returns:
        dict: AI's response, expected to be a JSON string containing file paths and code content.
    """
    
    # Construct a comprehensive prompt for the AI
    # This prompt is critical! Be very clear and structured.
    prompt = f"""
    {system_prompt_architecture}
    
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

    """

    logger.info(f"Generating code for: {specific_feature_prompt}")
    return get_ai_response(prompt)

# --- Function to Save Generated Code to Files ---
def save_generated_code(ai_response_json_str: str, project_paths: dict):
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

        for file_info in response_data["files"]:
            file_path = file_info.get("file_path")
            content = file_info.get("content")

            if not file_path or content is None:
                logger.warning(f"Skipping malformed file entry: {file_info}")
                continue

            # Determine the full path based on the file_path prefix (frontend/ or backend/)
            full_path = None
            if file_path and file_path.startswith("frontend/") and 'frontend' in project_paths:
                # Ensure the 'frontend/' prefix itself is not duplicated in the join
                # Example: os.path.join(project_paths['frontend'], 'src/App.tsx')
                # not os.path.join(project_paths['frontend'], 'frontend/src/App.tsx')
                # So we remove the "frontend/" prefix from file_path before joining
                relative_file_path = file_path[len("frontend/"):]
                full_path = os.path.join(project_paths['frontend'], relative_file_path)
            elif file_path and file_path.startswith("backend/") and 'backend' in project_paths:
                # Same for backend
                relative_file_path = file_path[len("backend/"):]
                full_path = os.path.join(project_paths['backend'], relative_file_path)
            else:
                logger.warning(f"Skipping file with invalid or unhandled path prefix: {file_path}")
                continue

            if full_path:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
                logger.info(f"Saved: {full_path}")
        
        print(f"\nCode generation complete. Files saved/updated in project directories.")
        # You might want to print the actual project_paths['frontend'] or project_paths['backend'] for user clarity
        if 'frontend' in project_paths:
            print(f"Frontend code in: {os.path.abspath(project_paths['frontend'])}")
        if 'backend' in project_paths:
            print(f"Backend code in: {os.path.abspath(project_paths['backend'])}")
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response as JSON: {e}", exc_info=True)
        print("Error: Invalid JSON response from AI.")
        print(f"Raw Response:\n{ai_response_json_str}")
    except Exception as e:
        logger.critical(f"Error while saving files: {e}", exc_info=True)

MY_PROJECT_NAME = "WizRD"
GENERATED_CODE_ROOT = "generated_code"
PERMANENT_PROJECT_DIR = os.path.join(GENERATED_CODE_ROOT, MY_PROJECT_NAME)
os.makedirs(PERMANENT_PROJECT_DIR, exist_ok=True)
print(f"Working in project directory: {PERMANENT_PROJECT_DIR}")
print(f"Ensure boilerplates are manually copied into '{os.path.join(PERMANENT_PROJECT_DIR, 'frontend')}' and '{os.path.join(PERMANENT_PROJECT_DIR, 'backend')}'")

# --- Main Execution Block ---
if __name__ == "__main__":
    logger.info("--- Starting Code Generation Test Script ---")

    # --- Load your prompts from .j2 files ---
    # brd_analysis_from_app.j2 and tech_stack_identified_prompt.j2 should contain pure JSON
    # so we json.loads them after loading.
    BRD_ANALYSIS_DICT = json.loads(load_prompt_template("brd_analysis_from_app.j2"))
    TECH_STACK_IDENTIFIED_DICT = json.loads(load_prompt_template("tech_stack_identified.j2"))

    # Other prompts are just text strings
    SYSTEM_PROMPT_ARCHITECTURE_CONTENT = load_prompt_template(
        "system_prompt_architecture.j2",
        include_npm_dependencies_instruction=True # Pass True if you want this block in the prompt
    )
    DEFAULT_DESIGN_PROMPT_CONTENT = load_prompt_template("default_design_prompt.j2")
    SPECIFIC_FEATURE_PROMPT_CONTENT = load_prompt_template("specific_feature_prompt.j2")

    # 1. Copy boilerplates first
    project_paths = orchestrate_code_generation(
        brd_analysis_json = BRD_ANALYSIS_DICT,
        tech_stack_json = TECH_STACK_IDENTIFIED_DICT,
        project_output_dir = PERMANENT_PROJECT_DIR
    )
    # --- Call the Code Generation Function ---
    ai_raw_response = generate_code_from_requirements(
        brd_analysis_json = BRD_ANALYSIS_DICT,
        tech_stack_json = TECH_STACK_IDENTIFIED_DICT,
        specific_feature_prompt = SPECIFIC_FEATURE_PROMPT_CONTENT,
        default_design_prompt = DEFAULT_DESIGN_PROMPT_CONTENT,
        system_prompt_architecture = SYSTEM_PROMPT_ARCHITECTURE_CONTENT
    )

    # --- Save the Generated Code ---
    save_generated_code(ai_raw_response, project_paths=project_paths)

    logger.info("--- Code Generation Test Script Finished ---")