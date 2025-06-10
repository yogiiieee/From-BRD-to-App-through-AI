# core/services/file_writer.py
import os
import shutil
import logging

logger = logging.getLogger(__name__)

class FileWriter:
    """
    Utility to manage writing generated files to the filesystem.
    """
    def __init__(self, base_output_dir):
        # base_output_dir should be a path like os.path.join(settings.MEDIA_ROOT, 'generated_projects')
        self.base_output_dir = base_output_dir
        os.makedirs(self.base_output_dir, exist_ok=True) # Ensure base directory exists

    def _sanitize_path(self, relative_path):
        """
        Sanitizes a relative path to prevent directory traversal attacks.
        Ensures the path stays within the intended base directory.
        """
        if '..' in relative_path or relative_path.startswith('/') or relative_path.startswith('\\'):
            raise ValueError(f"Invalid relative path detected: {relative_path}")
        return relative_path

    def write_files(self, project_name, files_to_write):
        """
        Writes a list of files to a new project directory.

        Args:
            project_name (str): The name of the project, used for the output directory.
            files_to_write (list): A list of dictionaries, where each dict is:
                                    {'file_path': 'path/relative/to/project_root.py', 'content': 'file content'}
        Returns:
            str: The full path to the created project directory.
        """
        project_dir = os.path.join(self.base_output_dir, project_name)
        
        if os.path.exists(project_dir):
            logger.warning(f"Project directory already exists: {project_dir}. Overwriting.")
            # Option: Delete existing, or add timestamp, or prompt user
            # For now, let's just proceed and overwrite
            # shutil.rmtree(project_dir) # Uncomment if you want to delete before writing
            
        os.makedirs(project_dir, exist_ok=True) # Create main project directory

        for file_data in files_to_write:
            try:
                relative_path = self._sanitize_path(file_data['file_path'])
                full_path = os.path.join(project_dir, relative_path)
                
                # Ensure parent directories exist for the file
                os.makedirs(os.path.dirname(full_path), exist_ok=True)

                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(file_data['content'])
                logger.info(f"Successfully wrote: {full_path}")
            except ValueError as e:
                logger.error(f"Security Warning: Attempted to write file with invalid path: {file_data.get('file_path')}. Error: {e}")
            except Exception as e:
                logger.error(f"Error writing file {file_data.get('file_path')}: {e}", exc_info=True)
                raise # Re-raise to indicate generation failure

        return project_dir

    def cleanup_project(self, project_name):
        """
        Removes a generated project directory. Use with caution!
        """
        project_dir = os.path.join(self.base_output_dir, project_name)
        if os.path.exists(project_dir):
            shutil.rmtree(project_dir)
            logger.info(f"Cleaned up project directory: {project_dir}")
        else:
            logger.warning(f"Attempted to clean up non-existent project directory: {project_dir}")