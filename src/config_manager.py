"""
╔═════════════════════════════════════════════════════════════════════════════╗
║                  CONFIGURATION MANAGER SCRIPT - ver. 01.02                  ║
║ Purpose: Dynamic configuration management for Gemini-Agent                  ║
║ File:    config_manager.py                                                  ║
╠═════════════════════════════════════════════════════════════════════════════╣
║ Section 1: Initial Settings and Imports                                     ║
║ Purpose:   Configure initial settings, imports, and script variables        ║
╚═════════════════════════════════════════════════════════════════════════════╝
"""
import os
import json
import yaml
import threading
from pydantic import BaseModel, ValidationError

# --- PATH CORRECTION ---
# Build an absolute path to the project root to reliably find the config file.
# __file__ -> .../Gemini-Agent/src/config_manager.py
# os.path.dirname(__file__) -> .../Gemini-Agent/src
# os.path.dirname(...) -> .../Gemini-Agent

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
CONFIG_PATH = os.path.join(CONFIG_DIR, "app_settings.json")
AGENTS_CONFIG_PATH = os.path.join(CONFIG_DIR, "agents.json")
RULES_PATH = os.path.join(CONFIG_DIR, "rules.yaml")
WORKFLOWS_PATH = os.path.join(SRC_DIR, "workflows.yaml")


_config_lock = threading.Lock()
#
"""
╔═════════════════════════════════════════════════════════════════════════════╗
║ Section 2: Pydantic Configuration Models                                    ║
║ Purpose:   Define the data structure and validation for app settings        ║
╠═════════════════════════════════════════════════════════════════════════════╣
║ Class 2.1: GDriveConfig                                                     ║
║ Purpose:   Define the data structure and validation for Google Drive config ║
╚═════════════════════════════════════════════════════════════════════════════╝
 """
# Define a model for Google Drive configuration
class GDriveConfig(BaseModel):
     client_id: str = ''
     client_secret: str = ''
     refresh_token: str = ''
     root_folder_id: str = ''
# End class
"""
╔═════════════════════════════════════════════════════════════════════════════╗
║ Class 2.2: AppSettings                                                      ║
║ Purpose:   Define the data structure and validation for app settings        ║
╚═════════════════════════════════════════════════════════════════════════════╝
"""
# Define the main application settings model
class AppSettings(BaseModel):
     last_opened_project_path: str = ''
     asset_locations: dict
     gdrive: GDriveConfig
     default_llm: str
     llm_configurations: dict
# End class
#
"""
╔═════════════════════════════════════════════════════════════════════════════╗
║ Class 2.3: ConfigManager                                                    ║
║ Purpose:   Manages loading, validation, and saving of the app config        ║
╚═════════════════════════════════════════════════════════════════════════════╝
 """
# Define the main configuration manager
class ConfigManager:
     """
     Manages dynamic loading, validation, and saving of the application config.
     This class is thread-safe and uses Pydantic for data validation.
     """
     def __init__(self):
          # Initialize the manager with the absolute path to the config file
          self.config_path = CONFIG_PATH
          self.agents_config_path = AGENTS_CONFIG_PATH
          self.workflows_path = WORKFLOWS_PATH
          self._settings = None
          self._workflows = {}
          self.reload()
     # End function

     # =========================================================================
     # Function 2.3.1: reload
     # =========================================================================
     def reload(self):
        """Reloads and re-validates all configurations from their respective files."""
        # Lock to ensure thread safety for all file operations
        with _config_lock:
            # Load main application settings and agent configurations
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    main_data = json.load(f)
                with open(self.agents_config_path, 'r', encoding='utf-8') as f:
                    agents_data = json.load(f)
                # Merge agent configurations into the main settings
                main_data['llm_configurations'] = agents_data.get('llm_configurations', {})
                self._settings = AppSettings(**main_data)
            except FileNotFoundError as e:
                if e.filename == self.config_path:
                    raise RuntimeError(f"FATAL: Main configuration file not found at {self.config_path}")
                elif e.filename == self.agents_config_path:
                    raise RuntimeError(f"FATAL: Agent configuration file not found at {self.agents_config_path}")
                else:
                    raise RuntimeError(f"FATAL: Configuration file not found: {e.filename}")
            except ValidationError as e:
                raise RuntimeError(f"Configuration validation error: {e}")
            except Exception as e:
                raise RuntimeError(f"Failed to load or parse configuration: {e}")

            # Load workflow configurations
            try:
                with open(self.workflows_path, 'r', encoding='utf-8') as f:
                    self._workflows = yaml.safe_load(f)
                if self._workflows is None:
                    self._workflows = {}
            except FileNotFoundError:
                print(f"[WARNING] Workflow configuration file not found at {self.workflows_path}. Dynamic workflows will be unavailable.")
                self._workflows = {}
            except yaml.YAMLError as e:
                raise RuntimeError(f"Failed to parse workflow configuration from {self.workflows_path}: {e}")
            except Exception as e:
                raise RuntimeError(f"Failed to load workflow configuration from {self.workflows_path}: {e}")
     # End function

     # =========================================================================
     # Function 2.3.2: get
     # =========================================================================
     def get(self) -> AppSettings:
          """Returns the current, validated settings object."""
          # Lock to ensure thread safety
          with _config_lock:
               if self._settings is None:
                    self.reload()

               if self._settings is None:
                    raise RuntimeError("Configuration could not be loaded, and settings are unavailable.")
               return self._settings
     # End function

     # =========================================================================
     # Function 2.3.3: get_workflow
     # =========================================================================
     def get_workflow(self, workflow_name: str):
          """Returns a specific workflow configuration by name."""
          with _config_lock:
               return self._workflows.get(workflow_name)

     # =========================================================================
     # Function 2.3.4: get_rules_path
     # =========================================================================
     def get_rules_path(self) -> str:
          """Returns the absolute path to the rules configuration file."""
          return RULES_PATH

     # =========================================================================
     # Function 2.3.5: get_templates_dir
     # =========================================================================
     def get_templates_dir(self) -> str:
          """Returns the absolute path to the templates directory."""
          return os.path.join(PROJECT_ROOT, "config", "templates")

     # =========================================================================
     # Function 2.3.6: get_template_content
     # =========================================================================
     def get_template_content(self, template_name: str):
          """
          Retrieves the content of a specific template file from config/templates.
          """
          template_path = os.path.join(self.get_templates_dir(), template_name)
          if not os.path.exists(template_path):
               print(f"[ERROR] Template file not found: {template_path}")
               return None
          try:
               with open(template_path, 'r', encoding='utf-8') as f:
                    return f.read()
          except Exception as e:
               print(f"[ERROR] Failed to read template {template_path}: {e}")
               return None
     # End function

     # =========================================================================
     # Function 2.3.7: save
     # =========================================================================
     def save(self, new_settings: dict):
          """
          Validates and saves a new settings dictionary to the JSON file.

          Args:
              new_settings (dict): Dictionary containing the new settings to be saved

          Returns:
              bool: True if save was successful, False otherwise
          """
          # Lock to ensure thread safety
          with _config_lock:
               try:
                    # Validate the new settings
                    validated_settings = AppSettings(**new_settings)

                    # Convert the validated settings back to a dictionary
                    settings_dict = validated_settings.dict()

                    # Ensure the config directory exists
                    os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

                    # Write the settings to the config file
                    with open(self.config_path, 'w', encoding='utf-8') as f:
                         json.dump(settings_dict, f, indent=4)

                    # Update the in-memory settings
                    self._settings = validated_settings
                    return True

               except Exception as e:
                    print(f"[ERROR] Failed to save settings: {e}")
                    return False
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║ Section 4: Singleton Instance Creation                                       ║
║ Purpose:   Ensures only one instance of ConfigManager exists                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
# Create a single, globally accessible instance of the ConfigManager
config_manager = ConfigManager()
#
#
## End of script
