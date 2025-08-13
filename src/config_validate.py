# ============================================================================
#  File: config_validate.py
#  Version: 1.1 (Fixed & Complete)
#  Purpose: Centralized config validation for Gemini-Agent (JSON schema)
#  Created: 29JUL25 | Fixed: 31JUL25
# ============================================================================
# SECTION 1: Imports and Globals
# ============================================================================

import os
import json
import jsonschema
from typing import Tuple, Optional

CONFIG_PATH = os.path.join("config", "app_settings.json")
SCHEMA_PATH = os.path.join("config", "config_schema.json")

# ============================================================================
# SECTION 2: Functions
# ============================================================================
# Function 2.1: validate_config
# ============================================================================
def validate_config(
    config_path: str = CONFIG_PATH, schema_path: str = SCHEMA_PATH
) -> Tuple[bool, Optional[str]]:
    """
    Validates the application configuration against the JSON schema.

    Args:
        config_path: Path to the configuration file
        schema_path: Path to the JSON schema file

    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    try:
        # Load configuration file
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # Load schema file
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        # Validate configuration against schema
        jsonschema.validate(instance=config, schema=schema)

        return True, None

    except FileNotFoundError as e:
        return False, f"Configuration file not found: {e}"
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON format: {e}"
    except jsonschema.ValidationError as e:
        return False, f"Configuration validation error: {e.message}"
    except jsonschema.SchemaError as e:
        return False, f"Schema validation error: {e.message}"
    except Exception as e:
        return False, f"Unexpected validation error: {e}"

# ============================================================================
# Function 2.2: validate_config_data
# ============================================================================
def validate_config_data(
    config_data: dict, schema_path: str = SCHEMA_PATH
) -> Tuple[bool, Optional[str]]:
    """
    Validates configuration data (dict) against the JSON schema.

    Args:
        config_data: Configuration data as dictionary
        schema_path: Path to the JSON schema file

    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    try:
        # Load schema file
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        # Validate configuration data against schema
        jsonschema.validate(instance=config_data, schema=schema)

        return True, None

    except FileNotFoundError as e:
        return False, f"Schema file not found: {e}"
    except json.JSONDecodeError as e:
        return False, f"Invalid schema JSON format: {e}"
    except jsonschema.ValidationError as e:
        return False, f"Configuration validation error: {e.message}"
    except jsonschema.SchemaError as e:
        return False, f"Schema validation error: {e.message}"
    except Exception as e:
        return False, f"Unexpected validation error: {e}"

# ============================================================================
# Function 2.3: get_validation_errors
# ============================================================================
def get_validation_errors(config_data: dict, schema_path: str = SCHEMA_PATH) -> list[dict]:
    """
    Get detailed validation errors for configuration data.

    Args:
        config_data: Configuration data as dictionary to validate
        schema_path: Path to the JSON schema file (default: config/config_schema.json)

    Returns:
        list[dict]: List of error dictionaries, each containing:
            - path (list): Path to the invalid field (e.g., ['settings', 'timeout'])
            - message (str): Description of the validation error
            - invalid_value (any): The problematic value that failed validation

    Example:
        >>> errors = get_validation_errors({"timeout": "not-a-number"})
        >>> if errors:
        ...     for error in errors:
        ...         print(f"Error at {'.'.join(error['path'])}: {error['message']}")
    """
    errors = []

    # Input validation
    if not isinstance(config_data, dict):
        return [{
            "path": [],
            "message": f"Expected dict for config_data, got {type(config_data).__name__}",
            "invalid_value": config_data
        }]

    if not os.path.isfile(schema_path):
        return [{
            "path": [],
            "message": f"Schema file not found: {os.path.abspath(schema_path)}",
            "invalid_value": None
        }]

    try:
        # Load and parse schema file
        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                schema = json.load(f)
        except json.JSONDecodeError as e:
            return [{
                "path": [],
                "message": f"Invalid JSON in schema file: {e}",
                "invalid_value": None
            }]
        except OSError as e:
            return [{
                "path": [],
                "message": f"Error reading schema file: {e}",
                "invalid_value": None
            }]

        # Create validator and collect errors
        try:
            validator = jsonschema.Draft7Validator(schema)

            for error in validator.iter_errors(config_data):
                errors.append({
                    "path": list(error.path),
                    "message": error.message,
                    "invalid_value": error.instance if hasattr(error, "instance") else None,
                })

        except jsonschema.SchemaError as e:
            return [{
                "path": [],
                "message": f"Invalid schema: {e}",
                "invalid_value": None
            }]

    except Exception as e:
        return [{
            "path": [],
            "message": f"Unexpected error during validation: {e}",
            "invalid_value": None
        }]

    return errors

# ============================================================================
# SECTION 4: Main Execution
# ============================================================================
if __name__ == "__main__":
    """Test the validation functions."""
    is_valid, error = validate_config()
    if is_valid:
        print("✅ Configuration validation passed")
    else:
        print(f"❌ Configuration validation failed: {error}")
#
#
## END config_validate.py
