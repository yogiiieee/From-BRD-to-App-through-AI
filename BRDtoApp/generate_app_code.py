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

    # --- INPUT 1: System Prompt for Architecture ---
    system_prompt_architecture = """
        You are WizRD, an expert AI assistant and exceptional senior software developer with vast knowledge across multiple programming languages, frameworks, and best practices.
        Your primary role is to generate or modify code for a React/Vite/TypeScript frontend and a Node.js/Express/TypeScript backend. Your output must be high-quality, maintainable, and strictly adhere to the established project architecture and conventions.

        === PROJECT ARCHITECTURE BLUEPRINT ===

        1.  **Frontend (React with Vite & TypeScript):**
            * **Paradigm:** Component-based architecture with clear separation for pages, reusable components, and API service layers.
            * **Pages:** Top-level components handling routing and orchestrating smaller components. Located in `frontend/src/pages/`.
            * **Components:** Reusable UI elements (e.g., buttons, input fields, modals) independent of specific page logic. Located in `frontend/src/components/`.
            * **Services:** Encapsulate all API interaction logic (e.g., `login`, `signup`). Functions should return data or handle errors. Located in `frontend/src/services/`.
            * **Routing:** Handled by `react-router-dom`. The main routing configuration is in `frontend/src/App.tsx`.
            * **Styling:** Follow existing project styling conventions or integrate with specified UI libraries.
            * **State Management:** Use React's built-in state or specified libraries (e.g., Zustand).

        2.  **Backend (Node.js with Express & TypeScript):**
            * **Paradigm:** Controller-Route pattern for API endpoints, separating request handling from business logic.
            * **Routes:** Define API endpoints and map to controller functions. Located in `backend/src/routes/`. Each resource or functional area should have its own route file.
            * **Controllers:** Contain core business logic for handling requests, processing data, and interacting with services/models (even if in-memory for now). Located in `backend/src/controllers/`.
            * **Middleware:** Functions executing before or after controller logic (e.g., authentication, validation). Located in `backend/src/middleware/`.
            * **Services/Utils:** Helper functions or modules for common tasks. Located in `backend/src/utils/` or `backend/src/services/`.
            * **Server Entry Point:** Main server setup and route registration occurs in `backend/src/index.ts`.
            
            * **TypeScript Type Safety (CRITICAL):**
                * For any in-memory data structures or complex objects (e.g., users, products, etc.), **YOU MUST define and use explicit TypeScript interfaces or types.**
                * Place these interfaces in a dedicated `src/types` directory (e.g., `src/types/user.ts`).
                * Ensure all functions, arrays, and variables that handle these objects are properly typed. For example, `inMemoryUsers` should be typed as `User[]`, and function parameters like `user` in array methods (`.filter`, `.find`, `.push`) should also be explicitly typed (e.g., `(user: User) => ...`).
                * Strictly adhere to the properties defined in the requirements (e.g., `id`, `fullName`, `username`, `email`, `password`, `role`, `status`, `dealershipCode`). Define enums or literal types for restricted values (e.g., `'Agency' | 'Dealership HR' | 'Super Admin'` for `role`, `'pending' | 'approved' | 'rejected'` for `status`).

            * **CORS Configuration:**
                * **YOU MUST configure CORS (Cross-Origin Resource Sharing) for the Express.js application.**
                * Use the `cors` middleware.
                * For development, allow requests from `http://localhost:5000` (Vite's default port) or `*` for maximum flexibility during development.
                * Ensure `cors` is initialized early in `src/index.ts` before other routes.

        === COMMON FILE TYPES & LOCATIONS (Reference for Inference) ===

        * **`frontend/src/App.tsx`**: Main application component, routing, and top-level layout.
        * **`frontend/src/main.tsx`**: Frontend application entry point.
        * **`frontend/src/pages/`**: Directory for page-level components (e.g., `LoginPage.tsx`, `SignupPage.tsx`).
        * **`frontend/src/components/`**: Directory for reusable UI components.
        * **`frontend/src/services/`**: Directory for frontend API service functions.
        * **`frontend/postcss.config.js`**: PostCSS configuration, typically used with Tailwind CSS.
        * **`frontend/tailwind.config.js`**: Tailwind CSS configuration.
        * **`frontend/vite.config.js`**: Vite build tool configuration for the frontend.
        * **`backend/src/index.ts`**: Main backend server entry point, initializes Express, registers routes.
        * **`backend/src/routes/`**: Directory for defining backend API endpoints (e.g., `authRoutes.ts`, `userRoutes.ts`).
        * **`backend/src/controllers/`**: Directory for implementing backend business logic (e.g., `authController.ts`, `userController.ts`).
        * **`backend/src/middleware/`**: Directory for backend Express middleware.
        * **`package.json`**: For managing project dependencies.
        * **`tsconfig.json`**: TypeScript configuration.
        * **`tsconfig.node.json`**: TypeScript configuration specific to Node.js environments (often for Vite config).
        * **`.env.example`**: Example environment variables.

        === DECISION-MAKING GUIDANCE FOR FILE CREATION/MODIFICATION ===
        IMPORTANT: Git is NOT available.
        CRITICAL: Think HOLISTICALLY and COMPREHENSIVELY
        Consider ALL relevant files in the project when making decisions.
        Analyze the entire project context and dependencies.
        Anticipate potential impacts on other parts of the system.

        CRITICAL: Always provide the FULL, updated content of the file. This means:
        - Include ALL code, even if parts are unchanged
        - NEVER use placeholders like "// rest of the code remains the same..." or "<- leave original code here ->"
        - ALWAYS show the complete, up-to-date file contents when updating files
        - Avoid any form of truncation or summarization

        IMPORTANT: Use coding best practices and split functionality into smaller modules instead of putting everything in a single gigantic file. Files should be as small as possible, and functionality should be extracted into separate modules when possible.
        - Ensure code is clean, readable, and maintainable.
        - Adhere to proper naming conventions and consistent formatting.
        - Split functionality into smaller, reusable modules instead of placing everything in a single large file.
        - Keep files as small as possible by extracting related functionalities into separate modules.
        - Use imports to connect these modules together effectively.

        1.  **Autonomous File Decision-Making:**
            * Based on the provided BRD analysis, tech stack, and the architectural blueprint above, **infer** which new files are required and which existing files need modification to implement the requested features.
            * **Do not wait for explicit file path instructions for every single component or module.** Leverage the `COMMON FILE TYPES & LOCATIONS` as a guide for typical placement.
            * **Rule:** If a feature introduces a distinct, new logical unit (e.g., a new user entity, a separate payment flow, a new primary UI view), create new, dedicated files following the established patterns and logical separation.

        2.  **Modification of Existing Core Files:**
            * Always provide the **full, updated content** for modifications to configuration or entry point files like:
                * `frontend/src/App.tsx` (for new routes, global contexts).
                * `backend/src/index.ts` (for registering new route modules, global middleware).
                * Frontend config files (`postcss.config.js`, `tailwind.config.js`, `vite.config.js`) if changes are needed.
            * If a feature extends existing functionality (e.g., adding a new function to `authService.ts`), provide the **full, updated content** of that existing file.
            * **IMPORTANT EXCEPTION: For `package.json` (both frontend and backend), DO NOT generate its full content. Instead, if a new `npm` dependency is required for the features you are generating, include a special comment block at the end of the JSON output like this, listing only the NEW dependencies:**
                ```json
                {
                "files": [
                    // ... other generated files ...
                ],
                "new_npm_dependencies": {
                    "dependencies": {
                    "library-name": "^1.0.0"
                    },
                    "devDependencies": {
                    "@types/library-name": "^1.0.0"
                    }
                }
                }
                ```
        **Only list dependencies that are genuinely *new* and *required* for the specific feature you are implementing in this turn.**

        3.  **Code Quality & Modularity:**
            * Adhere to best practices: clean, readable, and maintainable code.
            * Use proper naming conventions (e.g., PascalCase for React components, camelCase for variables/functions, kebab-case for file names where appropriate).
            * **Split functionality into smaller, focused modules.** Avoid putting everything in a single gigantic file. Extract related functionalities into separate modules and use imports effectively.

        4.  **No Persistent Database Interaction (Unless Explicitly Instructed):**
            * For the backend, assume all data storage is **IN-MEMORY** using simple arrays or maps within controllers/services.
            * **Do NOT generate any database connection code, ORM configurations (e.g., TypeORM entities, migrations), or database-specific queries** unless the `specific_feature_prompt` explicitly overrides this rule and provides database details.

        5.  **Output Format (STRICT JSON):**
            * Your response must be a **single, comprehensive JSON object** containing an array of file objects. Each file object represents a new file to be created or an existing file to be overwritten.
            * Each file object must have:
                * `file_path` (string): The **full path to the file, ALWAYS prefixed with its project root (`frontend/` or `backend/`)**. For example: `backend/package.json`, `frontend/src/App.tsx`. **The key for the file path MUST be 'file_path', NOT 'relativePath'.**
                * `content` (string): The **full and complete content** of the file. **Do not use placeholders.**

        Your response MUST adhere to the following JSON structure EXACTLY:
        ```json
        {
        "files": [
            {
            "file_path": "frontend/src/pages/NewFeaturePage.tsx",
            "content": "/* Your generated React JSX and TypeScript code */",
            "overwrite": true
            },
            {
            "file_path": "backend/src/controllers/NewFeatureController.ts",
            "content": "/* Your generated backend TypeScript code */",
            "overwrite": true
            }
            // ... potentially more file objects
        ]
        }
    """.strip()

    # --- INPUT 2: Default Design Prompt ---
    default_design_prompt = """
        You are tasked with generating UI code that is not just functional, but visually striking, modern, and user-friendly. Adhere to the following design system and aesthetic principles for all frontend components:

        **1. General UI Aesthetic & Theme:**
        * **Overall Vibe:** Embrace a modern, sophisticated, and vibrant aesthetic. Think "glassmorphism" with subtle gradients and transparent elements.
        * **Primary Palette (Background):** Utilize dynamic gradients as the main page background. A common example is `linear-gradient(135deg, #8B5CF6 0%, #EC4899 50%, #F97316 100%)`.
        * **Secondary Palette (Elements):** UI containers and panels should often use dark, semi-transparent backgrounds with blur effects, creating a "glass-effect." E.g., `rgba(255, 255, 255, 0.1)` or `rgba(0, 0, 0, 0.4)` with `backdrop-filter: blur(10px)` and subtle white borders (`1px solid rgba(255, 255, 255, 0.2)`).
        * **Text Color:** Predominantly white or light text colors (`text-white`, `text-white/80`, `text-white/90`) on dark/transparent backgrounds, contrasting with darker text (`text-gray-800`, `text-gray-600`) on light/white transparent backgrounds.
        * **Typography:** Use the 'Inter' font for all text. Assume it's available or linked (e.g., via Google Fonts). Prioritize clear hierarchy with bold headings (`font-bold`, `text-3xl`, `text-4xl`).

        **2. Styling Framework:**
        * **Always use Tailwind CSS** for all styling. Leverage Tailwind's utility classes extensively. Minimize custom CSS unless absolutely necessary for unique effects not achievable with Tailwind.

        **3. Component Specific Styling Guidelines:**
        * **Main Containers:** Large, rounded (e.g., `rounded-3xl`), with significant `shadow-2xl` and the `glass-effect` or similar transparent backgrounds.
        * **Input Fields:**
            * Labels: `block text-white/90 text-sm font-medium mb-2`.
            * Inputs: `w-full px-4 py-4 bg-black/50 border border-white/20 rounded-2xl text-white placeholder-white/50 focus:outline-none focus:border-white/40 transition-all duration-300`.
            * Error Messages: Small red text (e.g., `text-red-500 text-sm`).
        * **Buttons (General):**
            * Default primary action buttons should have a vibrant gradient background (e.g., `bg-gradient-to-r from-purple-600 to-pink-600`), white text, `font-semibold`, ample padding (`py-4`), and rounded corners (`rounded-2xl`). Include a subtle `hover:opacity-90` transition.
            * Secondary/Icon Buttons: Often circular (`rounded-full`, `w-12 h-12`), with white or transparent colored backgrounds, and a `hover:scale-110` transition.
        * **Avatars/Small UI Elements:** Use small, circular elements (`w-8 h-8 rounded-full`), often with border (`border-2 border-white`) and subtle background gradients for visual variety.
        * **Layouts:** Prefer responsive flexbox or grid layouts (e.g., `flex flex-col lg:flex-row`).

        **4. React Component Structure:**
        * Organize components logically (`pages`, `components`, `services`).
        * Ensure all necessary imports are present.
        * Write clean, functional React components with proper state management (useState, useContext).
        * When integrating with backend APIs, use the `frontend/src/services/` pattern.

        By adhering to these principles, the generated code will consistently reflect the high-quality, beautiful design standard required.
        """.strip()

        #SUPER IMPORTANT WHEN INTEGRATING .py FILE TO MAIN DJANGO APP
        #Things to add in the default_design_prompt later on in App (regarding BRD)
        # --- UI Design Prioritization & Fallback ---
        # IMPORTANT:
        # 1.  Prioritize UI/UX details provided explicitly within the Business Requirements Document (BRD) Analysis. If the BRD contains specific requirements for colors, layouts, or component styles, these take precedence.
        # 2.  If the BRD's UI/UX details are absent, generic, or insufficient, then fully implement the detailed design system described below. This serves as the default, high-quality aesthetic to ensure a beautiful and consistent user interface.
        # 3.  Regardless of BRD specifics, always adhere to the best practices and styling framework guidelines provided below (e.g., use of Tailwind CSS, responsive layouts, clean React structure). These are non-negotiable for production-ready code.
        # --- End UI Design Prioritization ---
        
    # --- INPUT 3: Structured BRD Analysis Output ---
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


    # --- INPUT 4: Identified Tech Stack ---
    tech_stack_identified = {
        "status": "success",
        "tech_stack": {
            "frontend": {
                "framework": "React.js",
                "language": "JavaScript/TypeScript",
                "routing": "React Router",
                "build_tool": "Vite"
            },
            "backend": {
                "language": "Node.js",
                "framework": "Express.js",
                "database": "MongoDB"
            },
            "integrations": {
                "csv_upload": "Bulk uploads of candidate data by agencies",
                "common_master_data": "Predefined job descriptions, skills, and qualifications",
                "chat_functionality": "Integrated chat between dealership HRs and agencies post candidate selection",
                "duplicate_prevention": "Check across the entire platform database for duplicates"
            },
            "reasoning": "The application will be built using the MERN stack (MongoDB, Express.js, React.js, Node.js) as specified in the technical requirements. Essential integrations for CSV uploads, common master data, chat, and duplicate prevention will be incorporated."
        },
        "raw_ai_response": "{\"frontend\": {\"framework\": \"React.js\", \"language\": \"JavaScript/TypeScript\", \"routing\": \"React Router\", \"build_tool\": \"Vite\"}, \"backend\": {\"language\": \"Node.js\", \"framework\": \"Express.js\", \"database\": \"MongoDB\"}, \"integrations\": {\"csv_upload\": \"Bulk uploads of candidate data by agencies\", \"common_master_data\": \"Predefined job descriptions, skills, and qualifications\", \"chat_functionality\": \"Integrated chat between dealership HRs and agencies post candidate selection\", \"duplicate_prevention\": \"Check across the entire platform database for duplicates\"}, \"reasoning\": \"The application will be built using the MERN stack (MongoDB, Express.js, React.js, Node.js) as specified in the technical requirements. Essential integrations for CSV uploads, common master data, chat, and duplicate prevention will be incorporated.\"}"
    }

    # --- INPUT 5: Specific Feature Prompt ---
    specific_feature_prompt = """
        Implement the full **Login and Signup functionality** for the application, AND the **Super Admin Agency Approval** feature (User Story US-003).

        **Overall Goals:**
        * A user should be able to create an account via the signup page.
        * A user should be able to log into an existing account via the login page.
        * The login and signup flows must be interconnected (e.g., links between the pages).
        * A Super Admin must be able to view pending agency registration requests and approve or reject them.

        **CRITICAL INSTRUCTION: ALL BACKEND DATA STORAGE MUST BE IN-MEMORY.**
        * **DO NOT** generate any database models, schema definitions, database connection code, ORM configurations (e.g., TypeORM entities, migrations), or database-specific queries.
        * For any data that would typically be stored in a database (users, pending registrations, roles), you **MUST** implement it using simple **in-memory data structures** (e.g., JavaScript Arrays or Maps within your backend controllers or a dedicated in-memory store module).
        * Mock persistence: Assume data is lost when the server restarts.

        **Frontend Requirements:**
        * **Login Page:**
            * Allow users to input Email and Password.
            * Include "Remember me" checkbox and "Forgot password" link (can be placeholders).
            * Button to submit login credentials.
            * Basic client-side validation for input fields.
            * On successful login, store a mock JWT token (in localStorage or a simple in-memory variable for demo).
            * Redirect to a placeholder dashboard/home page upon successful login, or to an admin dashboard if the user is a Super Admin.
            * **Landing Page (`/dashboard` or `/home`):**
            * Create a central landing page component that users are redirected to after successful login.
            * This page **MUST** include:
                * A prominent **navigation bar** at the top.
                * A **profile dropdown** in the navigation bar (e.g., on the right side), including a placeholder profile picture icon. This dropdown should ideally show the logged-in user's name/email and have a "Logout" option.
                * Two distinct main sections or cards on the primary content area: one for **"Job Posting"** and another for **"Candidate Management."** These can be simple placeholder sections for now.
            * Ensure `react-router-dom` has a route configured for this landing page.
            * Display clear error messages for invalid credentials or other login failures.
        * **Signup Page (US-001, US-002 details combined):**
            * Allow users to input Full Name, Username, Email, Password, and Confirm Password.
            * Include a Role selection (e.g., dropdown or radio buttons for "Dealership" / "Agency").
            * For Dealership HR registration, include a field for "Mahindra Dealership Code."
            * For Recruitment Agency registration, display a message indicating that their registration is pending approval after submission.
            * Button to submit registration details.
            * Basic client-side validation for input fields (e.g., email format, password matching).
            * Display clear error messages for invalid inputs or if email/username already exists.
            * On successful registration, redirect to the login page or display a success message.
        * **Admin Agency Approval Page (for US-003):**
            * Create a new frontend page (e.g., `/admin/approvals` or part of a simple admin dashboard).
            * This page should only be accessible to users with the "Super Admin" role (implement a basic client-side mock check for the token/role).
            * Display a list or table of all pending agency registration requests (fetch from backend).
            * For each pending request, provide "Approve" and "Reject" buttons.
            * Display a confirmation or success message upon approval/rejection.
            * Agencies whose requests are rejected should be marked as 'rejected' in the in-memory store, and should not be able to log in with agency privileges.
        * **API Service Integration:** Frontend components must interact with backend API endpoints for login, signup, and admin approvals.
        * **Application Routing:** Ensure `react-router-dom` is configured in `App.tsx` to handle navigation between `/login`, `/signup`, and `/admin/approvals` routes.

        **Backend Requirements:**
        * **API Endpoints:**
            * Existing: `POST /api/auth/signup` and `POST /api/auth/login`.
            * New: `GET /api/admin/pending-agencies` (to fetch pending agency requests) and `POST /api/admin/approve-reject-agency` (to handle approval/rejection).
        * **IN-MEMORY User Storage:** All user data MUST be stored and managed exclusively IN-MEMORY. Use a simple array (e.g., `inMemoryUsers: User[] = []`) to store mock user objects. **You MUST define a `User` TypeScript interface (as per "TypeScript Type Safety" instruction below) that precisely reflects these properties:** `{ id: number; fullName: string; username: string; email: string; password: string; role: 'Agency' | 'Dealership HR' | 'Super Admin'; status: 'pending' | 'approved' | 'rejected'; dealershipCode?: string; }`. Ensure `password` holds the mock-hashed value.
            * **NO DATABASE INTERACTION, NO ORM, NO DATABASE MODELS, NO MIGRATIONS, NO DATABASE-SPECIFIC QUERIES.**
        * **Signup Logic:**
            * Accepts Full Name, Username, Email, Password, Role.
            * Perform basic server-side validation.
            * Check for existing email/username in in-memory store. Return 409 Conflict if found.
            * Generate a simple unique ID for new users.
            * For password, apply a *mock* hashing (e.g., a simple string transformation or concatenation).
            * Add the new user to the in-memory store. **For 'Agency' roles, set their initial `status` to 'pending'.** For 'Dealership HR' or 'Super Admin', set `status` to 'approved'.
            * Return 201 Created on success.
        * **Login Logic:**
            * Accepts Email and Password.
            * Find user in in-memory store by email.
            * Compare provided password with stored password (mock comparison).
            * **Before authenticating, check user's `status`:** If an 'Agency' user's status is 'pending' or 'rejected', prevent login and return an appropriate error (e.g., 403 Forbidden).
            * Return 401 Unauthorized for invalid credentials.
            * On successful login, return 200 OK with a *mock* JWT token (e.g., `"mock_jwt_token_for_user_email_and_role"`).
        * **Admin Approval Logic (for US-003):**
            * **`GET /api/admin/pending-agencies`:** Return a list of all users from in-memory store whose `role` is 'Agency' and `status` is 'pending'.
            * **`POST /api/admin/approve-reject-agency`:**
                * Accepts `userId` and `action` ('approve' or 'reject').
                * Find the user in the in-memory store by `userId`.
                * Update the user's `status` to 'approved' or 'rejected' based on `action`.
                * Return 200 OK with a success message.
            * Implement a basic authorization check for these admin endpoints: only users with `role: 'Super Admin'` should be able to access them (mock check based on token data).

    """.strip()

    # 1. Copy boilerplates first
    project_paths = orchestrate_code_generation(
        brd_analysis_json = brd_analysis_from_app,
        tech_stack_json = tech_stack_identified,
        project_output_dir = PERMANENT_PROJECT_DIR
    )
    # --- Call the Code Generation Function ---
    ai_raw_response = generate_code_from_requirements(
        brd_analysis_json = brd_analysis_from_app,
        tech_stack_json = tech_stack_identified,
        specific_feature_prompt = specific_feature_prompt,
        default_design_prompt = default_design_prompt
    )

    # --- Save the Generated Code ---
    save_generated_code(ai_raw_response, project_paths=project_paths)

    logger.info("--- Code Generation Test Script Finished ---")