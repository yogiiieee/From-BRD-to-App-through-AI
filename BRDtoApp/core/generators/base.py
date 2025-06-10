# core/generators/base.py
from abc import ABC, abstractmethod

class BaseGenerator(ABC):
    """
    Abstract Base Class for all code generators.
    Defines the common interface for generating different types of code.
    """

    def __init__(self, gemini_client):
        self.gemini_client = gemini_client

    @abstractmethod
    def generate_component(self, user_story_json, project_context_json, tech_stack):
        """
        Generates a specific code component (e.g., model, view, component)
        based on a user story and overall project context.
        Returns a dictionary or list of dictionaries representing generated files/snippets.
        Example: {'path': 'path/to/file.py', 'content': '...', 'language': 'python'}
        """
        pass

    # You might add other common methods here, e.g., to load prompt templates,
    # or handle common post-generation processing.
    
    # For now, this is simple, but it will grow.