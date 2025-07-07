# langchain_refactor.py
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnableSequence
from langchain.chains import LLMChain # We'll use RunnableSequence primarily, but LLMChain is good to know
import os
import json
import logging
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
PROJECT_NAME = "WizRD"
GENERATED_CODE_BASE_DIR = "generated_code"

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Gemini API Configuration ---
load_dotenv() # Load from .env file if it exists in the same directory or parent

# Initialize the LangChain LLM instance globally
llm = None # Initialize to None
GEMINI_MODEL_NAME = "gemini-1.5-flash" # Keep model name if you want to log it

try:
    # os.environ.get is safer as it won't raise KeyError if not set,
    # but your current logic explicitly raises it, so we'll stick to that.
    api_key = os.environ["GEMINI_API_KEY"]
    llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL_NAME, temperature=0.7, api_key=api_key)
    logger.info("Gemini API configured successfully.")
    logger.info(f"Using Gemini model: {llm.model}") # Log the model name from the LLM instance
except KeyError:
    logger.error("GEMINI_API_KEY environment variable not set. Please set it in your .env file or system environment.")
    raise EnvironmentError("GEMINI_API_KEY not found. Cannot proceed without API key.")
except Exception as e:
    logger.critical(f"Failed to initialize LangChain ChatGoogleGenerativeAI model: {e}", exc_info=True)
    raise # Re-raise to stop execution if model init fails

jinja_env = Environment(
    loader=FileSystemLoader(PROMPT_TEMPLATES_DIR),
    trim_blocks=True,
    lstrip_blocks=True
)

#Helper functions (small resuable utilities)
def load_prompt_template(template_name: str, context: dict = None, include_npm_dependencies_instruction: bool = False, raw_content_only: bool = False) -> str:
    """
    Loads a Jinja2 template, optionally renders it with context,
    and can return raw content if specified.

    Args:
        template_name (str): The name of the template file (e.g., "my_prompt.j2").
        context (dict, optional): A dictionary of variables to pass to the template. Defaults to None.
        include_npm_dependencies_instruction (bool): Special flag for system_prompt_architecture.j2.
        raw_content_only (bool): If True, returns the raw template content without rendering.

    Returns:
        str: The rendered template string or raw template content.
    """
    try:
        if raw_content_only:
            # Read the raw content of the template file
            # Assuming PROMPTS_DIR is defined globally for your prompt templates directory
            template_path = os.path.join(PROMPT_TEMPLATES_DIR, template_name)
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read().strip() # Added .strip() for consistency

        template = jinja_env.get_template(template_name)
        # Ensure context is always a dict, even if None is passed
        context = context if context is not None else {}

        # Special handling for system_prompt_architecture.j2 (if needed, based on your template's internal logic)
        # This part assumes your system_prompt_architecture.j2 uses the 'include_npm_dependencies_instruction' variable
        # to conditionally include/exclude a section. If not, this 'pass' is fine.
        if template_name == "system_prompt_architecture.j2" and include_npm_dependencies_instruction:
            # No direct change to rendering here, as the variable is passed in context.
            # The template itself should handle the conditional logic based on this variable.
            pass

        rendered_string = template.render(**context)
        logger.info(f"Loaded and rendered template: {template_name}")
        return rendered_string.strip() # Added .strip() for consistency
    except Exception as e:
        logger.error(f"Error loading or rendering template '{template_name}': {e}", exc_info=True)
        raise # Re-raise the exception to stop execution

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
    specific_feature_request_text: str,
    brd_extraction_chain: RunnableSequence,
    ) -> dict:
    """
    Calls the BRD feature extraction chain to get relevant BRD themes/user stories.
    """
    logger.info(f"Extracting relevant BRD features for: '{specific_feature_request_text[:80]}...'")

    try:
        # Extract project summary from BRD analysis
        project_summary = full_brd_analysis_json.get('project_summary', '')
        
        # Create the dynamic context messages
        dynamic_context = f"""--- Full BRD Analysis ---
        {json.dumps(full_brd_analysis_json, indent=2)}
        --- End Full BRD Analysis ---

        --- Specific Feature Request to Extract ---
        {specific_feature_request_text}
        --- End Specific Feature Request ---
        """
        # Invoke the LangChain BRD extraction chain
        # The input keys must match the input variables defined in BRD_EXTRACTOR_PROMPT_TEMPLATE
        relevant_brd_context = brd_extraction_chain.invoke({
            "project_summary": project_summary,
            "dynamic_brd_context": dynamic_context
        })

        # The JsonOutputParser already attempts to parse it.
        # relevant_brd_context will be a dict if successful, or raise error if not.

        logger.info("Successfully extracted relevant BRD features.")
        return relevant_brd_context

    except Exception as e:
        logger.error(f"Error during BRD feature extraction AI call: {e}", exc_info=True)
        return {"project_summary": "Error during extraction, check logs.", "user_stories": []}

#High-level orchestration functions
#orchestrate_code_generation
def orchestrate_code_generation(brd_analysis_json: dict,
    tech_stack_json: dict,
    project_output_base_dir: str,
    system_prompt_architecture_template: SystemMessagePromptTemplate,
    default_design_prompt_template: SystemMessagePromptTemplate,
    specific_feature_prompt_content: str,
    brd_extraction_chain: RunnableSequence,
    code_generation_chain: RunnableSequence,
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
        specific_feature_request_text=specific_feature_prompt_content,
        brd_extraction_chain=brd_extraction_chain,
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
    ai_raw_response_dict = generate_code_from_requirements( # generate_code_from_requirements must be defined
        brd_analysis_json=relevant_brd_context,
        tech_stack_json=tech_stack_json,
        specific_feature_prompt=specific_feature_prompt_content,
        system_prompt_architecture_template=system_prompt_architecture_template,
        default_design_prompt_template=default_design_prompt_template,
        existing_frontend_code_context=existing_frontend_code_context,
        existing_backend_code_context=existing_backend_code_context,
        code_generation_chain=code_generation_chain,
    )

    if ai_raw_response_dict: # Check if dictionary is not empty
        logger.info("AI response received. Saving generated code...")
        # Save generated code using the *single* response and the copied_output_dirs
        # save_generated_code expects a JSON string, so convert dict back to string
        save_generated_code(json.dumps(ai_raw_response_dict), output_base_dirs=copied_output_dirs, logger=logger)
        logger.info("Generated code saved successfully.")
        return copied_output_dirs
    else:
        logger.error("AI response was empty or malformed. No code saved.")
        return {}

# --- Code Generation Function ---
# Ensure code_generation_chain is accessible (e.g., passed as an argument or global)
def generate_code_from_requirements(
    brd_analysis_json: dict,
    tech_stack_json: dict,
    specific_feature_prompt: str,
    system_prompt_architecture_template: SystemMessagePromptTemplate, # Must be present
    default_design_prompt_template: SystemMessagePromptTemplate,
    code_generation_chain: RunnableSequence, 
    existing_frontend_code_context: str = "",
    existing_backend_code_context: str = "",
    ) -> dict: # Changed return type hint to dict as JsonOutputParser returns dict
    """
    Generates code based on the BRD analysis, identified tech stack,
    and a specific prompt for the feature to be coded, using LangChain.
    """

    logger.info(f"Generating code for: {specific_feature_prompt}")

    # Invoke the LangChain code generation chain
    # The input keys must match the input variables defined in CODE_GENERATION_PROMPT_TEMPLATE
    try:
        ai_response_dict = code_generation_chain.invoke({
            "brd_analysis_json": json.dumps(brd_analysis_json, indent=2), # Stringify JSON for prompt
            "tech_stack_json": json.dumps(tech_stack_json, indent=2),     # Stringify JSON for prompt
            "specific_feature_prompt": specific_feature_prompt,
            "system_prompt_architecture": system_prompt_architecture_template,
            "default_design_prompt": default_design_prompt_template,
            "existing_frontend_code_context": existing_frontend_code_context,
            "existing_backend_code_context": existing_backend_code_context,
        })
        return ai_response_dict
    except Exception as e:
        logger.error(f"Error during code generation AI call: {e}", exc_info=True)
        return {"files": [], "new_npm_dependencies": {"dependencies": {}, "devDependencies": {}}}

# --- Function to Save Generated Code to Files ---
def save_generated_code(ai_response_json_str: str, output_base_dirs: dict): # Added logger, renamed project_paths to output_base_dirs for clarity
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

    # ----------------------------------------------------------------------
    # LangChain Prompt Templates Initialization (replace .j2 loading for prompts)
    # ----------------------------------------------------------------------

    # 1. System Prompt (Architectural Guidelines)
    # This remains a SystemMessagePromptTemplate as it defines the AI's core rules.
    SYSTEM_PROMPT_ARCHITECTURE_TEMPLATE = SystemMessagePromptTemplate.from_template(
        load_prompt_template("system_prompt_architecture.j2", include_npm_dependencies_instruction=True)
    )

    # 2. Default Design Prompt
    # This also acts as a system-level instruction for design.
    DEFAULT_DESIGN_PROMPT_TEMPLATE = SystemMessagePromptTemplate.from_template(
        load_prompt_template("default_design_prompt.j2")
    )

    # 3. BRD Feature Extractor Prompt
    # This is a complex prompt with multiple input variables.
    BRD_EXTRACTOR_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(
        # Load the raw content of the BRD extractor prompt, let LangChain handle variables
        load_prompt_template("brd_feature_extractor_prompt.j2", raw_content_only=True)
    ),
    MessagesPlaceholder(variable_name="dynamic_brd_context"),
    HumanMessagePromptTemplate.from_template(
        """
        Your output MUST be a single, valid JSON object following this structure (excluding irrelevant fields for conciseness):
        ```json
        {
          "project_summary": "High-level summary of the entire project (from the BRD).",
          "user_stories": [
            {
              "story_id": "US-X.Y.Z",
              "title": "As a [role], I want to [action], so that [benefit].",
              "description": "Detailed description of the user story.",
              "acceptance_criteria": [
                "Criteria 1",
                "Criteria 2"
              ],
              "tasks": [
                "Task 1",
                "Task 2"
              ]
            }
          ]
        }
        ```	  
        """
    )
])

    # 4. Main Code Generation Prompt
CODE_GENERATION_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
        SYSTEM_PROMPT_ARCHITECTURE_TEMPLATE, # Re-use the system template
        DEFAULT_DESIGN_PROMPT_TEMPLATE,      # Re-use the design template
        MessagesPlaceholder(variable_name="dynamic_brd_context"),
        MessagesPlaceholder(variable_name="dynamic_code_context"),
        HumanMessagePromptTemplate.from_template(
            """
            --- Project Technology Stack ---
            {tech_stack_json}
            --- End Project Technology Stack ---

            Based on the above information, generate the necessary code for the following specific feature(s):
            "{specific_feature_prompt}"

            Your output MUST be a single, valid JSON object with the 'files' array and 'new_npm_dependencies' object as described in the System Prompt.
            """
        )
    ])

llm = None # Initialize to None
GEMINI_MODEL_NAME = "gemini-1.5-flash" # Keep model name if you want to log it

try:
    api_key = os.environ["GEMINI_API_KEY"] # Retrieve API key from environment variable
    llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL_NAME, temperature=0.7, api_key=api_key) # <--- ADD api_key=api_key HERE
    logger.info("Gemini API configured successfully.")
    logger.info(f"Using Gemini model: {llm.model}")
except KeyError:
    logger.error("GEMINI_API_KEY environment variable not set. Please set it in your .env file or system environment.")
    raise EnvironmentError("GEMINI_API_KEY not found. Cannot proceed without API key.")
except Exception as e:
    logger.critical(f"Failed to initialize LangChain ChatGoogleGenerativeAI model: {e}", exc_info=True)
    raise # Re-raise to stop execution if model init fails


    # Define the LangChain Chains

    # Chain for BRD Feature Extraction
    # This chain takes BRD_EXTRACTOR_PROMPT_TEMPLATE, passes it to the LLM,
    # and then tries to parse the output as JSON.
brd_extraction_chain = BRD_EXTRACTOR_PROMPT_TEMPLATE | llm | JsonOutputParser()

    # Chain for Main Code Generation
    # This chain takes CODE_GENERATION_PROMPT_TEMPLATE, passes it to the LLM,
    # and then tries to parse the output as JSON.
code_generation_chain = CODE_GENERATION_PROMPT_TEMPLATE | llm | JsonOutputParser()

FEATURE_ITERATIONS_ROADMAP = [
        "specific_feature_login_signup.j2",
        "specific_feature_landing_dashboard.j2",
        # Add more .j2 filenames here as you define more features
    ]

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
        system_prompt_architecture_template=SYSTEM_PROMPT_ARCHITECTURE_TEMPLATE, 
        default_design_prompt_template=DEFAULT_DESIGN_PROMPT_TEMPLATE,         
        specific_feature_prompt_content=specific_feature_prompt_content_for_this_iteration,
        brd_extraction_chain=brd_extraction_chain,   
        code_generation_chain=code_generation_chain, 
    )

    logger.info(f"--- Finished Iteration {i+1} ---")
    # Optional: Add a small delay between iterations if making many API calls rapidly
    # import time
    # time.sleep(5)

logger.info("--- Code Generation Test Script Finished ---")