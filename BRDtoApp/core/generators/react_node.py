# core/generators/react_node.py
import json
from .base import BaseGenerator

class ReactNodeGenerator(BaseGenerator):
    """
    Generates React/Node.js specific code components.
    """

    def generate_react_component(self, user_story_json, ui_requirements_json, project_context_json):
        """
        Generates a React functional component based on a user story and UI requirements.
        """
        prompt_template = self.gemini_client.load_prompt_template('react_node_prompt.txt')
        
        prompt = prompt_template.format(
            user_story=json.dumps(user_story_json, indent=2),
            ui_requirements=json.dumps(ui_requirements_json, indent=2),
            context=json.dumps(project_context_json, indent=2)
        )
        
        raw_code = self.gemini_client.generate_text(prompt)
        
        # Post-processing like Prettier formatting can go here
        
        return {
            'file_path': f"src/components/{user_story_json['story_id'].replace('US-', '')}_Component.js", # Example path
            'content': raw_code,
            'language': 'javascript',
            'component_type': 'react_component'
        }

    def generate_node_api_endpoint(self, user_story_json, project_context_json):
        # Implement logic for generating Node.js API endpoints
        # This will use another prompt template (e.g., 'node_api_prompt.txt')
        return {} # Placeholder

    def generate_component(self, component_type, user_story_json, project_context_json, tech_stack=None):
        """
        Main entry point for React/Node code generation.
        Routes to specific generation methods based on component_type.
        """
        if component_type == 'react_component':
            # You'll need to pass UI requirements specifically
            ui_requirements = project_context_json.get('ui_requirements', {}) # Or wherever you store them
            return self.generate_react_component(user_story_json, ui_requirements, project_context_json)
        # Add more component types here (e.g., 'node_api', 'react_hook')

        raise ValueError(f"Unsupported React/Node component type: {component_type}")