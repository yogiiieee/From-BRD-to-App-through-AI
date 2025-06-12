# test_tech_stack_id.py
import os
import django
import sys
import json
import logging

# Configure logging for this script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Django Setup ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'BRDtoApp.settings') # <--- IMPORTANT: Replace 'myproject' with your actual Django project name!
django.setup()

# --- Import your new tech stack identification function ---
from core.services.gemini_client import identify_tech_stack

# --- Mock BRD Analysis Data ---
# This is what your `analyze_brd` function would return.
# MODIFY THIS JSON to simulate different BRDs and test tech stack identification.
mock_brd_analysis_output = {
    "project_summary": "Develop a cutting-edge e-commerce platform with a highly interactive user interface and a robust backend API for managing products and orders.",
    "themes": [
        {
            "theme_name": "Frontend User Experience",
            "description": "Focus on creating a dynamic and responsive user interface.",
            "epics": [
                {
                    "epic_name": "Product Catalog Display",
                    "description": "Display products with rich details and search capabilities.",
                    "user_stories": [
                        {
                            "story_id": "US-FE-001",
                            "title": "As a shopper, I want to browse products with React components, so that I can easily find what I'm looking for.",
                            "acceptance_criteria": ["Uses React.js for UI rendering.", "Responsive design."],
                            "tasks": ["Develop React components for product cards.", "Integrate with RESTful API."]
                        }
                    ]
                }
            ]
        },
        {
            "theme_name": "Backend Services & API",
            "description": "Building scalable and secure backend services.",
            "epics": [
                {
                    "epic_name": "Order Processing",
                    "description": "Handle customer orders and payment gateways.",
                    "user_stories": [
                        {
                            "story_id": "US-BE-001",
                            "title": "As a customer, I want to submit my order through a secure API, so that my purchase is processed correctly using Node.js.",
                            "acceptance_criteria": ["Node.js API endpoint for orders.", "Secure payment integration."],
                            "tasks": ["Implement Node.js Express route for order submission.", "Connect to MongoDB for order storage."]
                        }
                    ]
                }
            ]
        },
        {
            "theme_name": "Database Management",
            "description": "Ensuring efficient and reliable data storage.",
            "epics": [
                {
                    "epic_name": "Data Storage for Products",
                    "description": "Store product information, including images and inventory.",
                    "user_stories": [
                        {
                            "story_id": "US-DB-001",
                            "title": "As an admin, I want to store product details in a MongoDB database, so that product information is easily retrievable and scalable.",
                            "acceptance_criteria": ["Product data stored in MongoDB."],
                            "tasks": ["Define MongoDB schema for products.", "Implement data access layer."]
                        }
                    ]
                }
            ]
        }
    ]
}


# Example for a BRD that implies different tech or no tech
mock_brd_analysis_output_2 = {
    "project_summary": "A simple blogging platform where users can post articles and comment. Focus on traditional web development.",
    "themes": [
        {
            "theme_name": "Content Management",
            "description": "Manage blog posts and comments.",
            "epics": [
                {
                    "epic_name": "Article Posting",
                    "description": "Users can create and publish articles.",
                    "user_stories": [
                        {
                            "story_id": "US-BLOG-001",
                            "title": "As a blogger, I want to write and publish articles using a Django admin interface, so that I can easily manage my content.",
                            "acceptance_criteria": ["Django admin for content editing.", "Markdown support."],
                            "tasks": ["Implement Django models for Post and Comment.", "Configure Django admin."]
                        }
                    ]
                }
            ]
        },
        {
            "theme_name": "User Interaction",
            "description": "Allow users to comment on posts.",
            "epics": [
                {
                    "epic_name": "Commenting System",
                    "description": "Enable users to leave comments.",
                    "user_stories": [
                        {
                            "story_id": "US-BLOG-002",
                            "title": "As a reader, I want to leave comments on blog posts, so that I can share my thoughts. This will be a server-rendered page.",
                            "acceptance_criteria": ["Comments save to database.", "No JavaScript framework dependency."],
                            "tasks": ["Create Django view for comment submission.", "Update Post detail template."]
                        }
                    ]
                }
            ]
        }
    ]
}


# Example for a BRD that is very vague or implies no specific tech
mock_brd_analysis_output_3 = {
    "project_summary": "Develop a system to track daily expenses.",
    "themes": [
        {
            "theme_name": "Expense Tracking",
            "description": "Record daily spending.",
            "epics": [
                {
                    "epic_name": "Expense Entry",
                    "description": "Allow users to input new expenses.",
                    "user_stories": [
                        {
                            "story_id": "US-EXP-001",
                            "title": "As a user, I want to enter my daily expenses.",
                            "acceptance_criteria": ["Records amount and category."],
                            "tasks": ["Create data structure.", "Develop input mechanism."]
                        }
                    ]
                }
            ]
        }
    ]
}


if __name__ == "__main__":
    logger.info("--- Starting Tech Stack Identification Test Script ---")

    test_cases = [
        {"name": "React/Node Explicit", "data": mock_brd_analysis_output},
        {"name": "Django/Server-Rendered Implied", "data": mock_brd_analysis_output_2},
        {"name": "Vague/No Explicit Tech", "data": mock_brd_analysis_output_3},
    ]

    for test_case in test_cases:
        print(f"\n--- Running Test Case: {test_case['name']} ---")
        try:
            tech_stack_result = identify_tech_stack(test_case['data'])
            
            if isinstance(tech_stack_result, dict) and tech_stack_result.get('error'):
                logger.error(f"Tech Stack Identification failed for {test_case['name']}:")
                print(json.dumps(tech_stack_result, indent=2))
            else:
                logger.info(f"Tech Stack Identified for {test_case['name']}:")
                print(json.dumps(tech_stack_result, indent=2))
                
                # --- Specific Validation for this test case ---
                if test_case['name'] == "React/Node Explicit":
                    if tech_stack_result.get('frontend') == 'React' and tech_stack_result.get('backend') == 'Node.js':
                        print("  Validation: PASSED (Expected React/Node.js)")
                    else:
                        print(f"  Validation: FAILED (Expected React/Node.js, got {tech_stack_result.get('frontend')}/{tech_stack_result.get('backend')})")
                elif test_case['name'] == "Django/Server-Rendered Implied":
                    # AI might say 'Django' or 'Python' for backend, 'None' or 'Plain HTML/CSS/JS' for frontend
                    if 'Django' in tech_stack_result.get('backend', '') and \
                       (tech_stack_result.get('frontend') in ['None', 'Plain HTML/CSS/JS', '']):
                        print("  Validation: PASSED (Expected Django/Server-Rendered)")
                    else:
                        print(f"  Validation: FAILED (Expected Django/Server-Rendered, got {tech_stack_result.get('frontend')}/{tech_stack_result.get('backend')})")
                elif test_case['name'] == "Vague/No Explicit Tech":
                    # AI might return empty strings or very generic terms
                    if tech_stack_result.get('frontend', '') in ['None', ''] and \
                       tech_stack_result.get('backend', '') in ['None', '']:
                        print("  Validation: PASSED (Expected vague/no tech)")
                    else:
                        print(f"  Validation: FAILED (Expected vague/no tech, got {tech_stack_result.get('frontend')}/{tech_stack_result.get('backend')})")


        except Exception as e:
            logger.critical(f"An unexpected script error occurred for {test_case['name']}: {e}", exc_info=True)
    
    logger.info("--- Tech Stack Identification Test Script Finished ---")