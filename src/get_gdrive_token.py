# ============================================================================
#  File: get_gdrive_token.py
#  Version: 1.00
#  Purpose: Script to obtain Google Drive API refresh token
#  Created: 30JUL25
# ============================================================================
# SECTION 1: Global Variable Definitions & Imports
# ============================================================================
#
# Prerequisites:
# 1. A .env file in your project root with GDRIVE_CLIENT_ID and GDRIVE_CLIENT_SECRET.
# 2. You have a "Desktop app" credential type set up in Google Cloud Console.
# 3. You have run 'pip install google-auth-oauthlib google-api-python-client' in your venv.

import os
import sys
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from dotenv import load_dotenv
from loguru import logger

# ============================================================================
# SECTION 2: Loguru Configuration
# ============================================================================

LOG_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"

# Create logs directory if it doesn't exist
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Add file handler
logger.add(
    log_dir / "gdrive_token_{time:YYYY-MM-DD}.log",
    rotation="10 MB",
    retention="30 days",
    level="DEBUG",
    format=LOG_FORMAT,
    compression="zip"
)

# Add console handler with colors
logger.add(
    sys.stderr,
    level="INFO",
    format=LOG_FORMAT,
    colorize=True
)

# ============================================================================
# SECTION 3: Token Retrieval Function
# ============================================================================
def get_refresh_token():
    try:
        # Load environment variables
        if not load_dotenv():
            logger.warning("No .env file found. Using system environment variables")

        # Get client credentials from environment
        client_id = os.getenv("GDRIVE_CLIENT_ID")
        client_secret = os.getenv("GDRIVE_CLIENT_SECRET")

        if not client_id or not client_secret:
            error_msg = (
                "Missing required environment variables. "
                "Please ensure both GDRIVE_CLIENT_ID and GDRIVE_CLIENT_SECRET are set "
                "either in your .env file or system environment variables."
            )
            logger.error(error_msg)
            return None

    except Exception as e:
        logger.error("Error loading environment variables")
        if "No such file or directory" in str(e):
            logger.error("No .env file found in the project root")
            logger.info("Please create a .env file or set the environment variables directly")
        elif "Permission denied" in str(e):
            logger.error("Permission denied when trying to read the .env file")
            logger.info("Please check file permissions")
        else:
            logger.error(f"Unexpected error: {str(e)}")

        logger.info("Make sure you have a .env file in your project root with:")
        logger.info("GDRIVE_CLIENT_ID=your_client_id")
        logger.info("GDRIVE_CLIENT_SECRET=your_client_secret")
        return None

    # Scopes needed for Google Drive API access
    SCOPES = ["https://www.googleapis.com/auth/drive"]

    try:
        logger.info("Setting up OAuth 2.0 flow...")
        # Set up the flow using the credentials from your .env file
        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uris": ["http://localhost:5000/callback"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://accounts.google.com/o/oauth2/token",
                }
            },
            scopes=SCOPES,
        )

        logger.info("Starting OAuth 2.0 authentication flow...")
        logger.info("This will open your default web browser to complete the authorization.")
        logger.info("If the browser doesn't open, please visit the URL shown below.")

        try:
            # Run the flow to get credentials
            credentials = flow.run_local_server(
                port=0,
                authorization_prompt_message="\n🔑 Please visit this URL to authorize the application:\n{url}\n\n",
                success_message="\n✅ Authentication successful! You may close this window.\n",
                open_browser=True,
                timeout=300  # 5 minute timeout
            )

            if not credentials:
                raise Exception("No credentials returned from OAuth flow")

        except Exception as e:
            logger.error(f"Error during OAuth authentication: {str(e)}")
            if "invalid_grant" in str(e):
                logger.error("The authorization code may have expired")
                logger.info("Please try running the script again")
            elif "connection" in str(e).lower():
                logger.error("Network connection error")
                logger.info("Please check your internet connection and try again")
            return None

        # Check if a refresh token was obtained
        if not credentials or not credentials.refresh_token:
            logger.error("No refresh token was provided by Google")
            logger.info("Please ensure you've granted all requested permissions")
            return None

        logger.success("Successfully obtained Google Drive API Refresh Token")
        logger.info("=" * 60)
        logger.info(f"REFRESH_TOKEN: {credentials.refresh_token}")
        logger.info("=" * 60)
        logger.info("Next steps:")
        logger.info("1. Copy the REFRESH_TOKEN above")
        logger.info("2. Add it to your .env file as GDRIVE_REFRESH_TOKEN")
        logger.info("3. Restart your application")
        logger.warning("🔒 Keep this token secure and do not share it!")

        return credentials.refresh_token

    except Exception as e:
        logger.error(f"Error during OAuth flow: {str(e)}")
        logger.info("Please check your internet connection and try again.")
        return None

# ============================================================================
# SECTION 4: Main Script Execution
# ============================================================================
def main():
    """Main function to run the Google Drive token retrieval process."""
    try:
        logger.info("=" * 60)
        logger.info("🔐 Google Drive API Token Setup")
        logger.info("=" * 60)
        logger.info("This script will help you obtain a Google Drive API refresh token")

        refresh_token = get_refresh_token()
        if not refresh_token:
            logger.error("Failed to obtain refresh token. Please check the error messages above.")
            return 1

        logger.success("Script completed successfully!")
        return 0

    except KeyboardInterrupt:
        logger.warning("Operation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())

#
#
## End Of Script
