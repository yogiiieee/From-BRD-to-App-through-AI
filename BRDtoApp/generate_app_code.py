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
# This assumes generate_app_code.py is at the same level as boilerplate_templates/
BOILERPLATE_TEMPLATES_DIR = "boilerplate_templates"

def copy_boilerplate(template_name: str, destination_path: str):
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
        print(f"Successfully copied boilerplate from '{source_path}' to '{destination_path}'")
        return True
    except shutil.Error as e:
        print(f"Error copying boilerplate: {e}")
        return False
    except FileExistsError: # Catch this specifically if dirs_exist_ok is not available or desired for specific logic
        print(f"Destination '{destination_path}' already exists and is not empty. Skipping copy.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during boilerplate copy: {e}")
        return False

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

# --- Helper Function to Call AI ---
def get_ai_response(prompt_text):
    """
    Sends a prompt to the configured Gemini model and returns the response text,
    stripping potential markdown code block wrappers more robustly.
    """
    try:
        response = gemini_model.generate_content(prompt_text)
        raw_text = response.text
        
        # --- FIX STARTS HERE ---
        # Robustly remove leading/trailing markdown code block fences (```json, ```)
        # re.DOTALL ensures '.' matches newlines as well
        # re.IGNORECASE makes it case-insensitive for 'json'
        # re.MULTILINE allows ^ and $ to match start/end of lines, but we use it more for the general pattern.
        cleaned_text = re.sub(r'^\s*```json\s*\n|\n\s*```\s*$', '', raw_text, flags=re.DOTALL | re.IGNORECASE).strip()
        
        if cleaned_text != raw_text.strip(): # Check if any stripping actually occurred
            logger.info("Stripped markdown JSON wrapper from AI response.")
            
        # --- FIX ENDS HERE ---
        
        return cleaned_text # Return the cleaned string
    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}", exc_info=True)
        return f"Error: Failed to get response from AI - {e}"

import re

def strip_indents_and_format(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("Input to strip_indents_and_format must be a string.")

    lines = value.split('\n')
    trimmed_lines = [line.strip() for line in lines]
    rejoined_string = '\n'.join(trimmed_lines)
    result_without_leading_block_indent = rejoined_string.lstrip()
    final_result = re.sub(r'[\r\n]$', '', result_without_leading_block_indent)

    return final_result

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
def save_generated_code(ai_response_json_str, output_base_dir="generated_code"):
    """
    Parses the AI's JSON response and saves the code content into respective files.
    
    Args:
        ai_response_json_str (str): The raw JSON string received from the AI (after stripping markdown).
        output_base_dir (str): The base directory where generated code will be saved.
    """
    try:
        response_data = json.loads(ai_response_json_str)
        if "files" not in response_data or not isinstance(response_data["files"], list):
            logger.error("AI response is not in the expected 'files' JSON format after stripping markdown.")
            print("AI Response was not in expected JSON format. Please check the model output.")
            print(f"Raw AI Response (after stripping):\n{ai_response_json_str}")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Sanitize feature prompt for directory name.
        # Use a more robust sanitization if needed, but this is a good start.
        feature_dir_name = specific_feature_prompt.replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "").replace('"', '').replace("'", "")[:60]
        # Ensure it doesn't end with an underscore if there were trailing special chars
        feature_dir_name = feature_dir_name.strip('_') 
        
        full_output_dir = os.path.join(output_base_dir, f"{feature_dir_name}_{timestamp}")
        os.makedirs(full_output_dir, exist_ok=True)
        logger.info(f"Saving generated code to: {full_output_dir}")

        for file_info in response_data["files"]:
            file_path = file_info.get("file_path")
            content = file_info.get("content")

            if not file_path or content is None: # content can be empty string, but not None
                logger.warning(f"Skipping malformed file entry: {file_info}")
                continue

            # Ensure the full path is within the output directory (security check)
            # This is crucial to prevent the AI from writing files anywhere on your system.
            # Convert both paths to absolute and then check if the file path starts with the output directory path
            abs_output_dir = os.path.abspath(full_output_dir)
            abs_file_path = os.path.abspath(os.path.join(full_output_dir, file_path))
            
            if not abs_file_path.startswith(abs_output_dir):
                logger.warning(f"Skipping potentially malicious path outside output directory: {file_path}")
                continue

            os.makedirs(os.path.dirname(abs_file_path), exist_ok=True)
            with open(abs_file_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Saved: {abs_file_path}")
        
        print(f"\nCode generation complete. Files saved to: {os.path.abspath(full_output_dir)}")
        print("You can now navigate to this directory to test the generated code.")

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response as JSON: {e}", exc_info=True)
        print("Error: AI did not return valid JSON. This might mean the cleaning failed or the AI itself broke the JSON structure.")
        print(f"Raw AI Response (after potential cleaning, before JSON parsing):\n{ai_response_json_str}")
    except Exception as e:
        logger.critical(f"An unexpected error occurred while saving files: {e}", exc_info=True)

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
        Generate the complete production-ready code for user login and registration for all user roles (Dealership HR, Recruitment Agency, Super Admin),
        including:
        1.  **Full Project Setup:**
            * **Frontend (React, Material-UI):** Include all necessary files to initialize a standard React project,
                such as `package.json`, `vite.config.js` (since you're using Vite), `index.html`, `App.js` (or `App.tsx`),
                and any other essential configuration files. The frontend should be immediately runnable with `npm install` and `npm start`.
            * **Backend API (Node.js, Express.js with TypeScript and TypeORM, PostgreSQL):** Include all necessary files
                to initialize a standard Node.js/Express.js project using TypeScript and TypeORM,
                such as `package.json`, `tsconfig.json`, `ormconfig.json` (or database configuration in `index.ts`),
                a main server entry file (e.g., `src/index.ts` or `app.ts`), and basic routing setup.
                The backend should be immediately runnable with `npm install` and `npm start` (or `npm run dev`).
                Ensure basic database connection setup for PostgreSQL is included (e.g., in `index.ts` or a dedicated `database.ts`).
        2.  **User Login and Registration Feature Implementation:**
            * **Frontend:** `LoginPage.jsx` and `RegistrationPage.jsx` with Material-UI components,
                handling state, form submission, and API calls.
            * **Backend:** API endpoints for `/auth/register` and `/auth/login` (or similar).
                Implement user creation (with password hashing), user authentication, and JWT token generation.
            * **Database Models:** `User.ts` (with roles: DEALERSHIP, AGENCY, SUPER_ADMIN), `Dealership.ts`.
                Ensure TypeORM decorators are correctly used for entities and relationships.
        3.  **Basic Setup Instructions:** Provide a `README.md` file in the root of each generated project (frontend and backend)
            with clear, concise steps to install dependencies and run the application.
            This includes commands like `npm install`, `npm start` (or `npm run dev`), and any database setup steps.
        """.strip()
    # --- Call the Code Generation Function ---
    ai_raw_response = generate_code_from_requirements(
        brd_analysis_json=brd_analysis_from_app,
        tech_stack_json=tech_stack_identified,
        specific_feature_prompt=specific_feature_prompt,
        default_design_prompt=default_design_prompt
    )

    # --- Save the Generated Code ---
    save_generated_code(ai_raw_response)

    logger.info("--- Code Generation Test Script Finished ---")