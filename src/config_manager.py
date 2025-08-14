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
import asyncio
from typing import Any, Dict, Optional, Union, AsyncIterator, Type
from pathlib import Path
from pydantic import BaseModel, ValidationError
from dataclasses import dataclass

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
# Section 4: Async Configuration Manager
# Purpose: Async configuration management with streaming and validation

@dataclass
class ConfigValidationResult:
    """Result of configuration validation with streaming support."""
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    config_data: Optional[Dict[str, Any]] = None
    validation_time: float = 0.0

class AsyncConfigManager:
    """Async configuration manager with streaming capabilities."""
    
    def __init__(self):
        self.config_path = CONFIG_PATH
        self.agents_config_path = AGENTS_CONFIG_PATH
        self.workflows_path = WORKFLOWS_PATH
        self._settings = None
        self._workflows = {}
        self._config_lock = asyncio.Lock()
        self._cache_lock = threading.RLock()
        self._config_cache = {}
        self._validation_cache = {}
    
    async def load_config_streaming(self, config_path: Union[str, Path]) -> AsyncIterator[ConfigValidationResult]:
        """
        Load configuration with streaming validation results.
        
        Args:
            config_path: Path to configuration file
            
        Yields:
            ConfigValidationResult: Streaming validation results
        """
        config_path = Path(config_path)
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Initial validation result
            yield ConfigValidationResult(
                is_valid=True,
                errors=[],
                warnings=[],
                validation_time=0.0
            )
            
            if not config_path.exists():
                error_result = ConfigValidationResult(
                    is_valid=False,
                    errors=[f"Configuration file not found: {config_path}"],
                    warnings=[],
                    validation_time=asyncio.get_event_loop().time() - start_time
                )
                yield error_result
                return
            
            # Load configuration based on file extension
            if config_path.suffix.lower() == '.json':
                async with self._config_lock:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
            elif config_path.suffix.lower() in ['.yml', '.yaml']:
                async with self._config_lock:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = yaml.safe_load(f)
            else:
                error_result = ConfigValidationResult(
                    is_valid=False,
                    errors=[f"Unsupported configuration format: {config_path.suffix}"],
                    warnings=[],
                    validation_time=asyncio.get_event_loop().time() - start_time
                )
                yield error_result
                return
            
            # Validate configuration
            validation_result = await self._validate_config_async(config_data)
            validation_result.config_data = config_data
            validation_result.validation_time = asyncio.get_event_loop().time() - start_time
            
            # Cache validation result
            async with self._config_lock:
                self._validation_cache[str(config_path)] = validation_result
            
            yield validation_result
            
        except Exception as e:
            error_result = ConfigValidationResult(
                is_valid=False,
                errors=[f"Error loading configuration: {str(e)}"],
                warnings=[],
                validation_time=asyncio.get_event_loop().time() - start_time
            )
            yield error_result
    
    async def _validate_config_async(self, config_data: Dict[str, Any]) -> ConfigValidationResult:
        """Async configuration validation with type casting."""
        errors = []
        warnings = []
        
        try:
            # Validate required fields
            required_fields = ['last_opened_project_path', 'asset_locations']
            for field in required_fields:
                if field not in config_data:
                    errors.append(f"Missing required field: {field}")
            
            # Validate gdrive configuration
            if 'gdrive' in config_data:
                gdrive_config = config_data['gdrive']
                if not isinstance(gdrive_config, dict):
                    errors.append("gdrive must be a dictionary")
                else:
                    # Type casting for gdrive config
                    for key, value in gdrive_config.items():
                        cast_value = self.cast_config_value(value, str)
                        if cast_value is None and key in ['client_id', 'client_secret']:
                            warnings.append(f"Empty {key} in gdrive configuration")
                        gdrive_config[key] = cast_value
            
            # Validate LLM configurations
            if 'llm_configurations' in config_data:
                llm_configs = config_data['llm_configurations']
                if not isinstance(llm_configs, dict):
                    errors.append("llm_configurations must be a dictionary")
                else:
                    for llm_name, llm_config in llm_configs.items():
                        if not isinstance(llm_config, dict):
                            errors.append(f"LLM configuration for {llm_name} must be a dictionary")
                        else:
                            # Type casting for LLM config
                            for key, value in llm_config.items():
                                if key in ['temperature', 'max_tokens']:
                                    cast_value = self.cast_config_value(value, float)
                                    llm_config[key] = cast_value
            
            return ConfigValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            return ConfigValidationResult(
                is_valid=False,
                errors=[f"Validation error: {str(e)}"],
                warnings=warnings
            )
    
    def cast_config_value(self, value: Any, target_type: Type) -> Any:
        """
        Type-safe configuration value casting.
        
        Args:
            value: Value to cast
            target_type: Target type for casting
            
        Returns:
            Casted value or None if casting fails
        """
        try:
            if target_type is str:
                return str(value)
            elif target_type is int:
                return int(value)
            elif target_type is float:
                return float(value)
            elif target_type is bool:
                if isinstance(value, str):
                    return value.lower() in ('true', '1', 'yes', 'on')
                return bool(value)
            elif isinstance(target_type, tuple):
                # Handle union types
                for t in target_type:
                    try:
                        return t(value)
                    except (ValueError, TypeError):
                        continue
                return None
            else:
                return value
        except (ValueError, TypeError):
            return None
    
    async def get_config_async(self, config_path: Optional[Union[str, Path]] = None) -> Optional[Dict[str, Any]]:
        """
        Get configuration with async caching.
        
        Args:
            config_path: Optional custom config path
            
        Returns:
            Configuration dictionary or None if not found
        """
        if config_path is None:
            config_path = self.config_path
        
        config_path = Path(config_path)
        cache_key = str(config_path)
        
        # Check cache first
        async with self._config_lock:
            if cache_key in self._config_cache:
                return self._config_cache[cache_key]
        
        # Load configuration
        async for result in self.load_config_streaming(config_path):
            if result.is_valid and result.config_data:
                async with self._config_lock:
                    self._config_cache[cache_key] = result.config_data
                return result.config_data
        
        return None
    
    async def update_config_async(self, config_path: Union[str, Path], new_config: Dict[str, Any]) -> bool:
        """
        Update configuration with async validation and caching.
        
        Args:
            config_path: Path to configuration file
            new_config: New configuration data
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            config_path = Path(config_path)
            
            # Validate new configuration
            validation_result = await self._validate_config_async(new_config)
            if not validation_result.is_valid:
                return False
            
            # Save configuration
            async with self._config_lock:
                if config_path.suffix.lower() == '.json':
                    with open(config_path, 'w', encoding='utf-8') as f:
                        json.dump(new_config, f, indent=2)
                elif config_path.suffix.lower() in ['.yml', '.yaml']:
                    with open(config_path, 'w', encoding='utf-8') as f:
                        yaml.safe_dump(new_config, f, default_flow_style=False)
            
            # Update cache
            cache_key = str(config_path)
            async with self._config_lock:
                self._config_cache[cache_key] = new_config
                self._validation_cache[cache_key] = validation_result
            
            return True
            
        except Exception:
            return False
    
    async def get_workflow_config_async(self, workflow_name: str) -> Optional[Dict[str, Any]]:
        """Get workflow configuration with async loading."""
        workflows_config = await self.get_config_async(self.workflows_path)
        if workflows_config and workflow_name in workflows_config:
            return workflows_config[workflow_name]
        return None
    
    async def get_agents_config_async(self) -> Optional[Dict[str, Any]]:
        """Get agents configuration with async loading."""
        return await self.get_config_async(self.agents_config_path)

# Section 4: Singleton Instance Creation
# Purpose: Ensures only one instance of ConfigManager exists

# Create a single, globally accessible instance of the ConfigManager
config_manager = ConfigManager()
#
#
## End of script
