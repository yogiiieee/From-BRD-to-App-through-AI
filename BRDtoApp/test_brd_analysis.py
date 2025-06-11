# test_brd_analysis.py
import os
import django
import sys
import json
import logging

# Configure logging for this script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Django Setup ---
# Add your project's root directory to the Python path
# Assuming this script is in the same directory as manage.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'BRDtoApp.settings') # <--- IMPORTANT: Replace 'myproject' with your actual Django project name!
django.setup()

# --- Import your BRD analysis function ---
# Make sure this path is correct based on your apps/core structure
from core.services.gemini_client import analyze_brd

# --- Example BRD Content ---
# IMPORTANT: Replace this with the actual BRD text you want to test.
# Start with small, focused BRDs to iterate on prompt quality.
example_brd_content = """
Project Name: Employee Onboarding System

1. Project Summary:
   Develop a web-based system to streamline the onboarding process for new employees at Tech Solutions Inc. This system will manage pre-boarding tasks, document collection, and initial HR workflows.

2. Theme: Pre-boarding & Document Management
   This theme focuses on tasks and information required before an employee's first day and managing essential documents.

   2.1 Epic: New Hire Data Collection
       Enables the collection of personal and essential information from new hires before their start date.

       2.1.1 User Story: US-PB-001 - Submit Personal Information
           As a new employee, I want to securely submit my personal details (full name, address, contact info) online, so that HR can prepare my records.
           Acceptance Criteria:
           - All fields are validated for correct format (e.g., email format, phone number digits).
           - Required fields are clearly marked and prevent submission if empty.
           - Data is encrypted during transmission.
           Tasks:
           - Create a frontend form for personal information.
           - Implement backend API endpoint for saving personal data.
           - Design database table for employee personal details.
           - Add data validation on server-side.

       2.1.2 User Story: US-PB-002 - Upload Required Documents
           As a new employee, I want to upload my necessary documents (ID, passport, education certificates) securely, so that HR has all required paperwork.
           Acceptance Criteria:
           - Supports PDF, JPG, and PNG formats.
           - Maximum file size per document is 5MB.
           - Documents are associated with my employee profile.
           - Confirmation message displayed upon successful upload.
           Tasks:
           - Develop file upload component on frontend.
           - Implement secure file storage on backend (e.g., cloud storage).
           - Update employee database schema to link documents.
           - Implement virus scanning for uploaded files.

3. Theme: HR Workflow Integration
   This theme covers automating HR tasks and connecting with other internal systems.

   3.1 Epic: HR Task Automation
       Automates various HR tasks related to new employee setup.

       3.1.1 User Story: US-HR-001 - Automate Payroll Setup
           As an HR administrator, I want the system to automatically initiate payroll setup upon employee onboarding completion, so that manual data entry is minimized.
           Acceptance Criteria:
           - Triggers a call to the external payroll system API.
           - Provides error logging if payroll setup fails.
           - Updates employee status to 'Payroll Initiated'.
           Tasks:
           - Implement API integration with external payroll system.
           - Design error handling and logging for API calls.
           - Update employee status in database.
"""

if __name__ == "__main__":
    logger.info("--- Starting BRD Analysis Test Script ---")
    print(f"BRD content size: {len(example_brd_content)} characters")

    try:
        analysis_output = analyze_brd(example_brd_content)
        
        if isinstance(analysis_output, dict) and analysis_output.get('error'):
            logger.error("AI Analysis encountered an error:")
            print(json.dumps(analysis_output, indent=2))
        else:
            logger.info("AI Analysis Successful (JSON Output):")
            print(json.dumps(analysis_output, indent=2)) # Pretty print the JSON for readability
            
            # --- Basic Post-Analysis Validation Checks ---
            print("\n--- Basic Validation Checks ---")
            if "project_summary" not in analysis_output or not analysis_output.get("project_summary"):
                logger.warning("Validation Warning: 'project_summary' is missing or empty.")
            else:
                logger.info(f"Project Summary: {analysis_output['project_summary'][:70]}...")

            themes = analysis_output.get("themes", [])
            if not themes:
                logger.warning("Validation Warning: No 'themes' were identified.")
            else:
                logger.info(f"Identified {len(themes)} theme(s).")
                for theme in themes:
                    logger.info(f"  Theme: {theme.get('theme_name', 'Unnamed')}")
                    epics = theme.get('epics', [])
                    if not epics:
                        logger.warning(f"  Validation Warning: No epics found for theme '{theme.get('theme_name', 'Unnamed')}'.")
                    else:
                        logger.info(f"    Identified {len(epics)} epic(s) for theme.")
                        for epic in epics:
                            user_stories = epic.get('user_stories', [])
                            if not user_stories:
                                logger.warning(f"    Validation Warning: No user stories found for epic '{epic.get('epic_name', 'Unnamed')}'.")
                            else:
                                logger.info(f"      Identified {len(user_stories)} user story(s) for epic.")
                                for story in user_stories:
                                    story_id = story.get('story_id', 'N/A')
                                    logger.info(f"        User Story ID: {story_id}")
                                    if not story.get('title'):
                                        logger.warning(f"          Validation Warning: User story '{story_id}' has no title.")
                                    if not story.get('acceptance_criteria'):
                                        logger.warning(f"          Validation Warning: User story '{story_id}' has no acceptance criteria.")
                                    if not story.get('tasks'):
                                        logger.warning(f"          Validation Warning: User story '{story_id}' has no tasks.")
            logger.info("--- Validation Checks Complete ---")

    except Exception as e:
        logger.critical(f"An unexpected script error occurred: {e}", exc_info=True)
    
    logger.info("--- BRD Analysis Test Script Finished ---")
