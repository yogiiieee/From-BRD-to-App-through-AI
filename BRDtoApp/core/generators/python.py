# core/generators/python.py
import json
from .base import BaseGenerator

class PythonGenerator(BaseGenerator):
    """
    Generates Python/Django specific code components.
    """

    def generate_django_model(self, user_story_json, project_context_json):
        """
        Generates a Django model class based on a user story.
        """
        prompt_template = self.gemini_client.load_prompt_template('python_prompt.txt')
        
        # Prepare context for the prompt
        prompt = prompt_template.format(
            user_story=json.dumps(user_story_json, indent=2), # Pass structured story
            context=json.dumps(project_context_json, indent=2) # Pass relevant context
        )
        
        raw_code = self.gemini_client.generate_text(prompt)
        
        # You might add post-processing here (e.g., linting, formatting)
        
        # Assuming the AI gives back just the code, no markdown block
        return {
            'file_path': f"models/{user_story_json['story_id'].replace('-', '_').lower()}_model.py", # Example path
            'content': raw_code,
            'language': 'python',
            'component_type': 'django_model'
        }

    def generate_django_view(self, user_story_json, project_context_json):
        # Implement logic for generating Django views/APIs
        # This will use another prompt template (e.g., 'django_view_prompt.txt')
        # Similar structure to generate_django_model
        return {} # Placeholder

    def generate_component(self, component_type, user_story_json, project_context_json, tech_stack=None):
        """
        Main entry point for Python code generation.
        Routes to specific generation methods based on component_type.
        """
        if component_type == 'django_model':
            return self.generate_django_model(user_story_json, project_context_json)
        # Add more component types here (e.g., 'django_view', 'django_serializer')
        
        raise ValueError(f"Unsupported Python component type: {component_type}")