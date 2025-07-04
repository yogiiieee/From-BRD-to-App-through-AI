# generate_app_code_v2.py

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

#Helper functions (small resuable utilities)
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

def read_existing_project_code(project_path: str, logger: logging.Logger) -> str:
    """
    Reads all relevant code files from a given project directory and formats them
    into a single string for AI context. Skips common non-code directories/files.

    Args:
        project_path (str): The root path of the project (e.g., 'generated_code/WizRD/frontend').
        logger (logging.Logger): The logger instance.

    Returns:
        str: A formatted string containing file paths and their content.
    """
    if not os.path.isdir(project_path):
        logger.warning(f"Project path not found or is not a directory: {project_path}")
        return ""

    code_context_lines = []
    # Define common directories/files to ignore
    ignore_dirs = ['node_modules', 'dist', 'build', '.git', '.vscode', '__pycache__', '.venv', 'public']
    ignore_files = ['.DS_Store', 'Thumbs.db', 'package-lock.json', 'yarn.lock', '.env', '.env.example', 'README.md']

    logger.info(f"Reading existing code from: {project_path}")

    for root, dirs, files in os.walk(project_path):
        # Modify dirs in-place to skip ignored directories for os.walk
        dirs[:] = [d for d in dirs if d not in ignore_dirs]

        for file_name in files:
            if file_name in ignore_files:
                continue

            file_full_path = os.path.join(root, file_name)
            # Calculate path relative to the project_path (e.g., 'src/App.tsx')
            relative_path = os.path.relpath(file_full_path, project_path)

            try:
                with open(file_full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                code_context_lines.append(f"--- FILE_START: {relative_path} ---\n")
                code_context_lines.append(content)
                code_context_lines.append(f"\n--- FILE_END: {relative_path} ---\n\n")
            except Exception as e:
                logger.warning(f"Could not read file {file_full_path}: {e}")

    logger.info(f"Finished reading existing code from: {project_path}")
    return "".join(code_context_lines)

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
    ):
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
        logger.info(f"DEBUG: Type of full_brd_analysis_json being passed to Jinja: {type(full_brd_analysis_json)}")
        #TEMPORARY DEBUG
        if isinstance(full_brd_analysis_json, dict) or isinstance(full_brd_analysis_json, list):
            logger.info(f"DEBUG: First 200 chars of full_brd_analysis_json: {str(full_brd_analysis_json)[:200]}...")
        else:
            logger.info(f"DEBUG: full_brd_analysis_json content (non-dict/list): {full_brd_analysis_json}")

        # Render the prompt with the full BRD and the specific feature request
        try:
            extraction_prompt = extractor_template.render(
                full_brd_analysis_json=full_brd_analysis_json,
                specific_feature_request=specific_feature_request_text
            )
        except Exception as render_error: # Catch any error during rendering
            logger.error(f"DEBUG: Error during Jinja2 template rendering: {render_error}", exc_info=True)
            # This is where the 'Object of type Undefined' error should surface more clearly
            raise # Re-raise to propagate the error and stop execution


        # Assuming gemini_model is a global instance of genai.GenerativeModel
        # (This is the first AI call in the multi-stage process)
        api_response = gemini_model.generate_content(extraction_prompt)
        ai_extracted_json_str = api_response.text

        # Optional: Log token usage for this extraction call
        if api_response.usage_metadata:
            logger.info(f"BRD Extraction Call - Input Tokens: {api_response.usage_metadata.prompt_token_count}, Output Tokens: {api_response.usage_metadata.candidates_token_count}, Total Tokens: {api_response.usage_metadata.total_token_count}")

        # Parse the JSON response from the extraction AI
        extracted_brd_data = {} # Initialize in case of failure
        try:
            # Attempt to find and extract JSON within markdown code blocks
            # This is a common pattern for LLMs
            json_match = re.search(r'```json\n(.*?)```', ai_extracted_json_str, re.DOTALL)
            if json_match:
                pure_json_str = json_match.group(1).strip()
                logger.info("DEBUG: Extracted JSON from markdown block.")
            else:
                # If no markdown block, assume the whole response *should* be JSON
                pure_json_str = ai_extracted_json_str.strip()
                logger.info("DEBUG: No markdown block found, attempting to parse raw response as JSON.")

            extracted_brd_data = json.loads(pure_json_str)
            logger.info("Successfully parsed AI extracted BRD data.")

        except json.JSONDecodeError as json_err:
            logger.error(f"Error parsing AI extracted BRD data as JSON: {json_err}")
            logger.error(f"Raw AI Extractor Response (causing error):\n{ai_extracted_json_str}")
            # You might want to return a specific error structure or re-raise
            return {"project_summary": "Error parsing AI response.", "themes": []}
        except Exception as general_err:
            logger.error(f"Unexpected error during AI extracted BRD data processing: {general_err}")
            logger.error(f"Raw AI Extractor Response (causing error):\n{ai_extracted_json_str}")
            return {"project_summary": "Unexpected error.", "themes": []}

        #TEMPORARY DEBUG
        logger.info(f"DEBUG: Raw AI Extractor Response:\n{ai_extracted_json_str}")

        logger.info("Successfully extracted relevant BRD features.")
        return extracted_brd_data

    except Exception as e:
        logger.error(f"Error during BRD feature extraction AI call: {e}")
        return {"project_summary": "Error during extraction, check logs.", "themes": []} # Return a default structure on error

#High-level orchestration functions
#orchestrate_code_generation
def orchestrate_code_generation(brd_analysis_json: dict,
    tech_stack_json: dict,
    project_output_base_dir: str, 
    system_prompt_content: str,       
    default_design_prompt_content: str, 
    specific_feature_prompt_content: str 
    ):
    """
    Orchestrates code generation while maintaining the existing generated_code folder structure.
    Returns paths where boilerplates were copied.
    """

    # Determine which boilerplates are expected based on tech stack
    boilerplates_to_use = determine_boilerplates(tech_stack_json)

    logger.info(f"Identified required boilerplates: {boilerplates_to_use}")

    # Define the full path to the project's root output directory (e.g., generated_code/WizRD)
    # Using PROJECT_NAME from global constants (ensure PROJECT_NAME is defined globally)
    current_project_root = os.path.join(project_output_base_dir, PROJECT_NAME)

    # Dictionary to store the actual paths where boilerplates are copied
    # This will be passed to save_generated_code
    copied_output_dirs = {}

    logger.info("Starting automated boilerplate copying...")

    # --- Copy Frontend Boilerplate ---
    if 'frontend' in boilerplates_to_use:
        boilerplate_name = boilerplates_to_use['frontend'] # e.g., 'react_vite_ts'
        source_path = os.path.join(BOILERPLATE_TEMPLATES_DIR, boilerplate_name) # BOILERPLATE_TEMPLATES_DIR must be global
        destination_path = os.path.join(current_project_root, "frontend")

        if os.path.exists(destination_path) and os.path.exists(os.path.join(destination_path, 'package.json')):
            logger.info(f"Frontend boilerplate already exists at '{destination_path}'. Skipping copy.")
            copied_output_dirs['frontend'] = destination_path # Still store the path
        else:
            logger.info(f"Copying frontend boilerplate from '{source_path}' to '{destination_path}'")
            try:
                # If it exists but is incomplete (e.g., no package.json), or we want a fresh copy, remove it.
                if os.path.exists(destination_path):
                    logger.warning(f"Existing frontend directory '{destination_path}' is incomplete or needs refresh. Removing before copy.")
                    shutil.rmtree(destination_path)

                os.makedirs(os.path.dirname(destination_path), exist_ok=True) # Ensure parent 'WizRD' exists
                shutil.copytree(source_path, destination_path)
                copied_output_dirs['frontend'] = destination_path # Store the actual path
                logger.info("Frontend boilerplate copied successfully.")
            except Exception as e:
                logger.error(f"Failed to copy frontend boilerplate: {e}")
                return {} # Indicate failure

    # --- Copy Backend Boilerplate ---
    if 'backend' in boilerplates_to_use:
        boilerplate_name = boilerplates_to_use['backend'] # e.g., 'node_js'
        source_path = os.path.join(BOILERPLATE_TEMPLATES_DIR, boilerplate_name)
        destination_path = os.path.join(current_project_root, "backend")

        if os.path.exists(destination_path) and os.path.exists(os.path.join(destination_path, 'package.json')):
            logger.info(f"Backend boilerplate already exists at '{destination_path}'. Skipping copy.")
            copied_output_dirs['backend'] = destination_path # Still store the path
        else:
            logger.info(f"Copying backend boilerplate from '{source_path}' to '{destination_path}'")
            try:
                if os.path.exists(destination_path):
                    logger.warning(f"Existing backend directory '{destination_path}' is incomplete or needs refresh. Removing before copy.")
                    shutil.rmtree(destination_path)

                os.makedirs(os.path.dirname(destination_path), exist_ok=True) # Ensure parent 'WizRD' exists
                shutil.copytree(source_path, destination_path)
                copied_output_dirs['backend'] = destination_path # Store the actual path
                logger.info("Backend boilerplate copied successfully.")
            except Exception as e:
                logger.error(f"Failed to copy backend boilerplate: {e}")
                return {} # Indicate failure

    if not copied_output_dirs:
        logger.warning("No boilerplates copied. Exiting orchestration.")
        return {} # No boilerplates, nothing to generate code for

    # --- Read Existing Codebase for Context ---
    existing_frontend_code_context = ""
    if 'frontend' in copied_output_dirs:
        # Pass the actual copied path to read from
        existing_frontend_code_context = read_existing_project_code(copied_output_dirs['frontend'], logger)
        if not existing_frontend_code_context:
            logger.warning("No existing frontend code found to provide as context. AI will generate from scratch.")
        else:
            logger.info("Existing frontend code loaded for AI context.")

    existing_backend_code_context = ""
    if 'backend' in copied_output_dirs:
        # Pass the actual copied path to read from
        existing_backend_code_context = read_existing_project_code(copied_output_dirs['backend'], logger)
        if not existing_backend_code_context:
            logger.warning("No existing backend code found to provide as context. AI will generate from scratch.")
        else:
            logger.info("Existing backend code loaded for AI context.")
    
    # Step 1: Extract relevant BRD features using the first AI call
    # This will pass the FULL BRD to the extractor AI, along with the specific feature.
    # The result will be a SUBSET of the BRD relevant to the feature.
    relevant_brd_context = extract_relevant_brd_features(
        full_brd_analysis_json=brd_analysis_json,
        specific_feature_request_text=specific_feature_prompt_content
    )
    #TEMPORARY DEBUG
    logger.info(f"DEBUG: Content of relevant_brd_context (extracted BRD):\n{json.dumps(relevant_brd_context, indent=2)}")

    # Check if extraction was successful enough to proceed
    if not relevant_brd_context or not relevant_brd_context.get('user_stories'):
        logger.error("Failed to extract relevant BRD context. Aborting code generation.")
        return {} # Exit if we can't get relevant BRD info

    logger.info(f"\nAI code generation initiated for project at: {current_project_root}. AI will now add/modify code.")

    # Step 2: Call the main Code Generation AI (this is the second AI call)
    # Pass the *extracted* BRD context to the main code generation function
    ai_raw_response = generate_code_from_requirements( # generate_code_from_requirements must be defined
        brd_analysis_json=relevant_brd_context, # <--- IMPORTANT: Pass the extracted subset here
        tech_stack_json=tech_stack_json,
        specific_feature_prompt=specific_feature_prompt_content,
        default_design_prompt=default_design_prompt_content,
        system_prompt_architecture=system_prompt_content,
        existing_frontend_code_context=existing_frontend_code_context, 
        existing_backend_code_context=existing_backend_code_context,   
        logger=logger
    )

    if ai_raw_response:
        logger.info("AI response received. Saving generated code...")
        # Save generated code using the *single* response and the copied_output_dirs
        save_generated_code(ai_raw_response, output_base_dirs=copied_output_dirs, logger=logger) # save_generated_code must be defined
        logger.info("Generated code saved successfully.")
        return copied_output_dirs # Return the paths if other parts of your script need them
    else:
        logger.error("AI response was empty or malformed. No code saved.")
        return {}
    

# --- Code Generation Function ---
def generate_code_from_requirements(brd_analysis_json, tech_stack_json, specific_feature_prompt, default_design_prompt, system_prompt_architecture, existing_frontend_code_context: str = "", existing_backend_code_context: str = "", logger=None):
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

    # <--- ADD THIS NEW SECTION HERE ---
    --- CURRENT PROJECT CODEBASE CONTEXT ---
    The following are the existing files in the project. You MUST analyze this code to understand the current state, existing components, and established patterns.
    If a file needs modification, you MUST provide its full, updated content. If a new file is needed, create it.

    --- Frontend Codebase ---
    {existing_frontend_code_context if existing_frontend_code_context else "No existing frontend code provided for this iteration."}
    --- End Frontend Codebase ---

    --- Backend Codebase ---
    {existing_backend_code_context if existing_backend_code_context else "No existing backend code provided for this iteration."}
    --- End Backend Codebase ---
    # <--- END NEW SECTION ---

    --- **RELEVANT** User Stories & Tasks for the Current Feature ---
    The following is a flattened list of user stories and their tasks, extracted from the full BRD, that are directly relevant to the feature you need to implement. Focus your code generation on these specific items.
    {json.dumps(brd_analysis_json, indent=2)}
    --- End **RELEVANT** User Stories & Tasks ---


    Based on the above information, generate the necessary code for the following specific feature(s):
    "{specific_feature_prompt}"

    """

    logger.info(f"Generating code for: {specific_feature_prompt}")
    return get_ai_response(prompt)

# --- Function to Save Generated Code to Files ---
def save_generated_code(ai_response_json_str: str, output_base_dirs: dict, logger): # Added logger, renamed project_paths to output_base_dirs for clarity
    logger.info(f"\nCode generation complete. Files saved/updated in project directories.")
    if 'frontend' in output_base_dirs:
        logger.info(f"Frontend code in: {os.path.abspath(output_base_dirs['frontend'])}")
    if 'backend' in output_base_dirs:
        logger.info(f"Backend code in: {os.path.abspath(output_base_dirs['backend'])}")
    """
    Parses the AI's JSON response and saves the code content into respective files.
    Supports boilerplate-integrated saving and intelligent package.json updates.

    Args:
        ai_response_json_str (str): The raw JSON string received from the AI.
        output_base_dirs (dict): Dictionary of base paths for frontend/backend
                                 (e.g., {'frontend': '/path/to/WizRD/frontend', 'backend': '/path/to/WizRD/backend'}).
        logger: The logger instance for output.
    """
    try:
        logger.info("DEBUG: Entering save_generated_code function.")
        response_data = json.loads(ai_response_json_str)

        # Check for the main 'files' array
        if "files" not in response_data or not isinstance(response_data["files"], list):
            logger.error("AI response is not in the expected 'files' JSON format.")
            logger.debug(f"Raw AI Response:\n{ai_response_json_str}") # Use debug for full raw response
            return

        # Process individual files
        for file_info in response_data["files"]:
            file_path = file_info.get("file_path")
            content = file_info.get("content")
            overwrite = file_info.get("overwrite", True) # Default to overwrite if not specified

            if not file_path or content is None:
                logger.warning(f"Skipping malformed file entry (missing path or content): {file_info}")
                continue

            # Determine the full path based on the file_path prefix (frontend/ or backend/)
            full_path = None
            target_base_dir = None

            if file_path.startswith("frontend/") and 'frontend' in output_base_dirs:
                relative_file_path = file_path[len("frontend/"):]
                target_base_dir = output_base_dirs['frontend']
                full_path = os.path.join(target_base_dir, relative_file_path)
            elif file_path.startswith("backend/") and 'backend' in output_base_dirs:
                relative_file_path = file_path[len("backend/"):]
                target_base_dir = output_base_dirs['backend']
                full_path = os.path.join(target_base_dir, relative_file_path)
            else:
                logger.warning(f"Skipping file with invalid or unhandled path prefix: {file_path}")
                continue

            if full_path:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
                logger.info(f"Saved: {full_path}")

        # --- Handle new_npm_dependencies (CRUCIAL NEW LOGIC) ---
        if "new_npm_dependencies" in response_data:
            new_deps_info = response_data["new_npm_dependencies"]
            logger.info("Processing new npm dependencies suggested by AI...")

            # Assume new_npm_dependencies applies to the backend's package.json for now
            # You might need to refine this if the AI specifies frontend/backend separately for deps
            backend_package_json_path = os.path.join(output_base_dirs.get('backend', ''), 'package.json')
            frontend_package_json_path = os.path.join(output_base_dirs.get('frontend', ''), 'package.json')


            # Process Backend package.json
            if os.path.exists(backend_package_json_path):
                try:
                    with open(backend_package_json_path, 'r+', encoding='utf-8') as f:
                        pkg_json = json.load(f)
                        updated = False

                        if 'dependencies' in new_deps_info and new_deps_info['dependencies']:
                            pkg_json.setdefault('dependencies', {}).update(new_deps_info['dependencies'])
                            updated = True
                        if 'devDependencies' in new_deps_info and new_deps_info['devDependencies']:
                            pkg_json.setdefault('devDependencies', {}).update(new_deps_info['devDependencies'])
                            updated = True

                        if updated:
                            f.seek(0) # Rewind to the beginning
                            json.dump(pkg_json, f, indent=2)
                            f.truncate() # Truncate any remaining old content
                            logger.info(f"Updated backend package.json with new dependencies: {backend_package_json_path}")
                        else:
                            logger.info("No new backend dependencies to add.")
                except Exception as e:
                    logger.error(f"Failed to update backend package.json: {e}", exc_info=True)
            else:
                logger.warning(f"Backend package.json not found at {backend_package_json_path}. Cannot add new dependencies.")

            # Process Frontend package.json (similar logic, if AI suggests frontend deps)
            # You might need to add logic here if AI starts suggesting frontend deps in new_npm_dependencies
            # For now, assuming it's primarily for backend based on your earlier prompt discussion.
            # If the AI ever provides a "frontend_new_npm_dependencies" or similar, you'd extend this.

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response as JSON: {e}", exc_info=True)
        logger.error("Error: Invalid JSON response from AI.") # Changed print to logger
        logger.debug(f"Raw Response:\n{ai_response_json_str}") # Use debug for full raw response
    except Exception as e:
        logger.critical(f"Error while saving files: {e}", exc_info=True)

PROJECT_NAME = "WizRD"
GENERATED_CODE_BASE_DIR = "generated_code"

# --- Main Execution Block ---
if __name__ == "__main__":
    logger.info("--- Starting Code Generation Test Script ---")

    # --- Load your prompts from .j2 files ---
    # brd_analysis_from_app.j2 and tech_stack_identified_prompt.j2 should contain pure JSON
    # so we json.loads them after loading.
    BRD_ANALYSIS_DICT = json.loads(load_prompt_template("brd_analysis_from_app.j2"))
    #TEMPORARY DEBUG
    logger.debug(f"Type of BRD_ANALYSIS_DICT: {type(BRD_ANALYSIS_DICT)}")
    logger.debug(f"Content of BRD_ANALYSIS_DICT (first 500 chars): {str(BRD_ANALYSIS_DICT)[:500]}")
    # If the dictionary is very large, you might need to inspect specific parts
    # logger.debug(f"First theme: {BRD_ANALYSIS_DICT.get('themes', [])[0] if BRD_ANALYSIS_DICT.get('themes') else 'No themes'}")

    TECH_STACK_IDENTIFIED_DICT = json.loads(load_prompt_template("tech_stack_identified.j2"))

    # Other prompts are just text strings
    SYSTEM_PROMPT_ARCHITECTURE_CONTENT = load_prompt_template(
        "system_prompt_architecture.j2",
        include_npm_dependencies_instruction=True # Pass True if you want this block in the prompt
    )
    DEFAULT_DESIGN_PROMPT_CONTENT = load_prompt_template("default_design_prompt.j2")
    FEATURE_ITERATIONS_ROADMAP = [
    "specific_feature_login_signup.j2",
    "specific_feature_landing_dashboard.j2",
    # Add more .j2 filenames here as you define more features
    # "specific_feature_job_posting.j2",
    # "specific_feature_candidate_management.j2",
]

    # Iterate through the feature roadmap, processing one feature at a time
    for i, feature_prompt_filename in enumerate(FEATURE_ITERATIONS_ROADMAP):
        logger.info(f"\n--- Starting Iteration {i+1}: Processing feature from '{feature_prompt_filename}' ---")

        # Load the content of the specific feature prompt for the current iteration
        specific_feature_prompt_content_for_this_iteration = load_prompt_template(feature_prompt_filename)

        # Call orchestrate_code_generation for the current feature
        # This function will read the *current state* of the project folder
        # and pass it as context to the AI for modification/addition.
        orchestrate_code_generation(
            brd_analysis_json=BRD_ANALYSIS_DICT, # Full BRD is always passed for context
            tech_stack_json=TECH_STACK_IDENTIFIED_DICT,
            project_output_base_dir=GENERATED_CODE_BASE_DIR, # Base directory for the project
            system_prompt_content=SYSTEM_PROMPT_ARCHITECTURE_CONTENT,
            default_design_prompt_content=DEFAULT_DESIGN_PROMPT_CONTENT,
            specific_feature_prompt_content=specific_feature_prompt_content_for_this_iteration # <--- Pass the loaded content for THIS iteration
        )

        logger.info(f"--- Finished Iteration {i+1} ---")
        # Optional: Add a small delay between iterations if making many API calls rapidly
        # import time
        # time.sleep(5)

    logger.info("--- Code Generation Test Script Finished ---")