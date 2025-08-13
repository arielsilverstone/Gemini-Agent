# ============================================================================
#  File: secure_secrets.py
#  Version: 1.1 (Fixed & Complete)
#  Purpose: Load and manage sensitive secrets like API keys.
#  Created: 30JUL25 | Fixed: 31JUL25
# ============================================================================
# SECTION 1: Global Variable Definitions & Imports
# ============================================================================
import os
from typing import Dict, Optional
from dotenv import load_dotenv
from loguru import logger

# ============================================================================
# SECTION 2: Function Definition - load_secrets
# ============================================================================
# Function 2.1: load_secrets
# ============================================================================
def load_secrets() -> Dict[str, Optional[str]]:
    """
    Loads secrets from a .env file and the environment.

    This function first loads the .env file from the project root,
    then retrieves specific keys required by the application.

    Returns:
        A dictionary containing the loaded secrets.
    """
    try:
        # Load environment variables from .env file in the project root
        load_dotenv()

        secrets = {
            "google_api_key": os.getenv("GOOGLE_API_KEY"),
            "openai_api_key": os.getenv("OPENAI_API_KEY"),
            "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY"),
            "codestral_api_key": os.getenv("CODESTRAL_API_KEY"),
            "deepseek_api_key": os.getenv("DEEPSEEK_API_KEY"),
            "grok_api_key": os.getenv("GROK_API_KEY"),
            "huggingface_api_key": os.getenv("HUGGINGFACE_API_KEY"),
            "kimi_api_key": os.getenv("KIMI_API_KEY"),
            "mistral_api_key": os.getenv("MISTRAL_API_KEY"),
            "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
            "together_api_key": os.getenv("TOGETHER_API_KEY"),
            "azure_secret_id": os.getenv("AZURE_SECRET_ID"),
            "azure_value": os.getenv("AZURE_VALUE"),
            "apify_api_key": os.getenv("APIFY_API_KEY"),
            "gdrive_client_id": os.getenv("GDRIVE_CLIENT_ID"),
            "gdrive_client_secret": os.getenv("GDRIVE_CLIENT_SECRET"),
            "gdrive_refresh_token": os.getenv("GDRIVE_REFRESH_TOKEN"),
            "gdrive_root_folder_id": os.getenv("GDRIVE_ROOT_FOLDER_ID"),
        }

        # Log warnings for missing critical secrets
        critical_secrets = ["google_api_key"]
        for secret in critical_secrets:
            if not secrets.get(secret):
                logger.warning(
                    f"{secret.upper()} not found in environment variables or .env file"
                )

        return secrets

    except Exception as e:
        logger.error(f"Failed to load secrets: {e}")
        return {}

# ============================================================================
# Function 2.2: get_secret
# ============================================================================
def get_secret(secret_name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Retrieve a specific secret by name.

    Args:
        secret_name: Name of the secret to retrieve
        default: Default value if secret is not found

    Returns:
        The secret value or default if not found or on error
    """
    try:
        # Ensure .env is loaded and log if it's a new load
        if not load_dotenv(override=False):
            logger.debug("No .env file found, using existing environment variables")

        secret_value = os.getenv(secret_name.upper(), default)

        if secret_value is None:
            logger.debug(f"Secret '{secret_name.upper()}' not found in environment, returning default value")

        return secret_value if secret_value is not None else default

    except Exception as e:
        logger.error(f"Failed to get secret '{secret_name}': {str(e)}", exc_info=True)
        logger.debug(f"Returning default value for secret '{secret_name}'")

# ============================================================================
# Function 2.3: validate_secrets
# ============================================================================
def validate_secrets() -> Dict[str, bool]:
    """
    Validate that required secrets are available.

    Returns:
        Dictionary mapping secret names to availability status
    """
    secrets = load_secrets()
    validation_status = {}

    required_secrets = [
        "google_api_key",
        "gdrive_client_id",
        "gdrive_client_secret",
        "gdrive_refresh_token",
        "gdrive_root_folder_id",
    ]

    for secret in required_secrets:
        validation_status[secret] = bool(secrets.get(secret))

    return validation_status

# ============================================================================
# Function 2.4: mask_secret
# ============================================================================
def mask_secret(secret_value: Optional[str]) -> str:
    """
    Mask a secret value for safe display.

    Args:
        secret_value: The secret value to mask

    Returns:
        Masked version of the secret
    """
    try:
        if not secret_value:
            logger.debug("No secret value provided, returning 'Not Set'")
            return "Not Set"

        masked_value = "****" + (secret_value[-4:] if len(secret_value) > 4 else "")
        logger.debug(f"Successfully masked secret value (length: {len(secret_value)})")
        return masked_value

    except Exception as e:
        logger.error(f"Error masking secret: {str(e)}", exc_info=True)
        return "[Error: Could not mask secret]"

# ============================================================================
# SECTION 3: Environment Setup Helpers
# ============================================================================
# Function 3.1: setup_environment
# ============================================================================
def setup_environment() -> bool:
    """
    Set up the environment with loaded secrets.

    Returns:
        True if setup successful, False otherwise
    """
    try:
        secrets = load_secrets()

        # Set environment variables for any missing ones
        for key, value in secrets.items():
            if value and not os.getenv(key.upper()):
                os.environ[key.upper()] = value

        return True

    except Exception as e:
        logging.error(f"Failed to setup environment: {e}")
        return False

# ============================================================================
# Function 3.2: create_env_template
# ============================================================================

def create_env_template() -> str:
    """
    Create a template .env file content.

    Returns:
        Template content as string
    """
    try:
        # ====================================================================
        # ENV Template
        # ====================================================================
        template = """# Gemini-Agent Environment Variables
# Copy this file to .env and fill in your credentials

# API Keys
GOOGLE_API_KEY=your_google_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
CODESTRAL_API_KEY=your_codestral_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here
GROK_API_KEY=your_grok_api_key_here
HUGGINGFACE_API_KEY=your_huggingface_api_key_here
KIMI_API_KEY=your_kimi_api_key_here
MISTRAL_API_KEY=your_mistral_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
TOGETHER_API_KEY=your_together_api_key_here

# Azure Credentials (optional)
AZURE_SECRET_ID=your_azure_secret_id_here
AZURE_VALUE=your_azure_value_here

# Google Drive Integration
GDRIVE_CLIENT_ID=your_gdrive_client_id_here
GDRIVE_CLIENT_SECRET=your_gdrive_client_secret_here
GDRIVE_REFRESH_TOKEN=your_gdrive_refresh_token_here
GDRIVE_ROOT_FOLDER_ID=your_gdrive_root_folder_id_here
"""
        logger.debug("Successfully generated .env template")
        return template

    except Exception as e:
        logger.error(f"Failed to generate .env template: {str(e)}", exc_info=True)
        return "# Error: Could not generate template"

# ============================================================================
# SECTION 4: Main Execution - Test Secrets Management
# ============================================================================

if __name__ == "__main__":
    """Test the secrets loading functionality."""
    try:
        logger.info("Starting secrets management test")
        print("🔐 Testing Secrets Management")
        print("=" * 40)

        logger.debug("Loading secrets...")
        secrets = load_secrets()
        secret_count = len(secrets)
        logger.info(f"Successfully loaded {secret_count} secret definitions")
        print(f"Loaded {secret_count} secret definitions")

        logger.debug("Validating secrets...")
        validation = validate_secrets()
        valid_count = sum(1 for v in validation.values() if v)
        logger.info(f"Validation complete: {valid_count}/{len(validation)} secrets are valid")

        print("\n📋 Secret Validation Status:")
        for secret, is_valid in sorted(validation.items()):
            status = "✅" if is_valid else "❌"
            masked_value = mask_secret(secrets.get(secret))
            log_msg = f"{secret}: {'Valid' if is_valid else 'Missing'}"
            logger.debug(log_msg)
            print(f"  {status} {log_msg} - Value: {masked_value}")

        logger.debug("Test completed successfully")
        print("\n📝 Environment template available via create_env_template()")

    except Exception as e:
        logger.critical(f"Fatal error in secrets management test: {str(e)}", exc_info=True)
        print("❌ An error occurred during testing. Check the logs for details.")
        raise


#
#
## End of Script
