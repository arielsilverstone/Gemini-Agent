# ============================================================================
# File: gdrive_integration.py
# Purpose: Google Drive API integration for Gemini-Agent
# Date: 29JUL25
# Author: Gemini-Agent
# ============================================================================
# SECTION 1: Global Variable Definitions
# ============================================================================
import os
import json
import requests
import asyncio
from typing import Optional, Dict, Any, Union
from loguru import logger

GDRIVE_CLIENT_ID = os.getenv('GDRIVE_CLIENT_ID', '')
GDRIVE_CLIENT_SECRET = os.getenv('GDRIVE_CLIENT_SECRET', '')
GDRIVE_REFRESH_TOKEN = os.getenv('GDRIVE_REFRESH_TOKEN', '')
GDRIVE_ROOT_FOLDER_ID = os.getenv('GDRIVE_ROOT_FOLDER_ID', '')
#
# ============================================================================
# SECTION 2: Google Drive Auth and API Helpers
# ============================================================================
# Function 2.1: get_gdrive_access_token
# Purpose: Obtains access token using refresh token.
# ============================================================================
#
def get_gdrive_access_token() -> Optional[str]:
    """
    Returns:
        str: The access token if successful, None otherwise

    Raises:
        requests.exceptions.RequestException: If there's an error making the request
    """
    if not all([GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET, GDRIVE_REFRESH_TOKEN]):
        logger.error("Missing required Google Drive credentials")
        return None

    url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": GDRIVE_CLIENT_ID,
        "client_secret": GDRIVE_CLIENT_SECRET,
        "refresh_token": GDRIVE_REFRESH_TOKEN,
        "grant_type": "refresh_token"
    }

    try:
        resp = requests.post(url, data=data, timeout=10)
        resp.raise_for_status()

        token = resp.json().get("access_token")
        if not token:
            logger.error("No access token in Google Drive API response")
            return None

        return token

    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to get Google Drive access token: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            error_msg += f" | Status: {e.response.status_code} | Response: {e.response.text}"
        logger.error(error_msg)
        return None
#
# ============================================================================
# Function 2.2: gdrive_request
# Purpose: Helper for Google Drive API requests.
# ============================================================================
#
def gdrive_request(method, endpoint, headers=None, params=None, data=None, files=None) -> Dict[str, Any]:

    token = get_gdrive_access_token()
    if not token:
        return {"error": "No GDrive access token"}
    url = f"https://www.googleapis.com/drive/v3/{endpoint}"
    headers = headers or {}
    headers["Authorization"] = f"Bearer {token}"
    resp = requests.request(method, url, headers=headers, params=params, data=data, files=files)
    try:
        return resp.json()
    except Exception:
        return {"error": resp.text}
#
# ============================================================================
# Function 2.3: gdrive_read
# Purpose: Download file content from Google Drive.
# ============================================================================
#
def gdrive_read(file_id):
    token = get_gdrive_access_token()
    if not token:
        return None
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    return resp.content if resp.status_code == 200 else None
#
# ============================================================================
# Function 2.4: gdrive_write
# Purpose: Upload new file to Google Drive.
# ============================================================================
#
def gdrive_write(name, parent_id, content) -> Optional[Dict[str, Any]]:
    token = get_gdrive_access_token()
    if not token:
        return None
    metadata = {"name": name, "parents": [parent_id]}
    files = {
        'data': ('metadata', json.dumps(metadata), 'application/json'),
        'file': (name, content)
    }
    url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(url, headers=headers, files=files)
    return resp.json() if resp.status_code in (200, 201) else {"error": resp.text}
#
# ============================================================================
# Function 2.5: gdrive_update
# Purpose: Update file content in Google Drive.
# ============================================================================
#
def gdrive_update(file_id: str, content: Union[str, bytes], content_type: str = "application/octet-stream") -> Dict[str, Any]:
    """x
    Args:
        file_id: The ID of the file to update
        content: The new content to write to the file
        content_type: MIME type of the content (default: "application/octet-stream")

    Returns:
        dict: The updated file metadata on success, or an error dictionary
    """
    if not file_id:
        return {"error": "File ID is required"}

    if not content:
        return {"error": "Content cannot be empty"}

    token = get_gdrive_access_token()
    if not token:
        return {"error": "Failed to obtain Google Drive access token"}

    url = f"https://www.googleapis.com/upload/drive/v3/files/{file_id}?uploadType=media"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": content_type
    }

    try:
        resp = requests.patch(url, headers=headers, data=content, timeout=30)
        resp.raise_for_status()
        return resp.json()

    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to update file {file_id}"
        if hasattr(e, 'response') and e.response is not None:
            error_msg += f" | Status: {e.response.status_code} | Response: {e.response.text}"
        logger.error(error_msg)
        return {"error": error_msg}

# ============================================================================
# Function 2.6: gdrive_delete
# ============================================================================
def gdrive_delete(file_id):
    """
    Delete file from Google Drive.
    """
    token = get_gdrive_access_token()
    if not token:
        return None
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.delete(url, headers=headers)
    return resp.status_code == 204

# ============================================================================
# Function 2.7: gdrive_move
# ============================================================================
def gdrive_move(file_id: str, new_parent_id: str) -> Dict[str, Any]:
    """
    Move file to new folder in Google Drive.

    Args:
        file_id: ID of the file to move
        new_parent_id: ID of the destination folder

    Returns:
        dict: The updated file metadata on success, or an error dictionary
    """
    if not file_id or not new_parent_id:
        return {"error": "File ID and new parent ID are required"}

    token = get_gdrive_access_token()
    if not token:
        return {"error": "Failed to obtain Google Drive access token"}

    try:
        # Get current parents
        meta = gdrive_request('GET', f'files/{file_id}', params={'fields': 'parents'})
        if 'error' in meta:
            return meta

        if 'parents' not in meta:
            return {"error": "No parent information available for the file"}

        prev_parents = ",".join(meta['parents'])
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?addParents={new_parent_id}&removeParents={prev_parents}&fields=id,parents"

        resp = requests.patch(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()

    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to move file {file_id}"
        if hasattr(e, 'response') and e.response is not None:
            error_msg += f" | Status: {e.response.status_code} | Response: {e.response.text}"
        logger.error(error_msg)
        return {"error": error_msg}

# ============================================================================
# Function 2.8: gdrive_copy
# ============================================================================
def gdrive_copy(file_id: str, new_name: str, parent_id: str) -> Dict[str, Any]:
    """
    Copy file in Google Drive.

    Args:
        file_id: ID of the file to copy
        new_name: New name for the copied file
        parent_id: ID of the destination folder

    Returns:
        dict: The new file's metadata on success, or an error dictionary
    """
    if not all([file_id, new_name, parent_id]):
        return {"error": "File ID, new name, and parent ID are required"}

    token = get_gdrive_access_token()
    if not token:
        return {"error": "Failed to obtain Google Drive access token"}

    url = f"https://www.googleapis.com/drive/v3/files/{file_id}/copy"
    headers = {"Authorization": f"Bearer {token}"}
    data = {"name": new_name, "parents": [parent_id]}

    try:
        resp = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()

    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to copy file {file_id}"
        if hasattr(e, 'response') and e.response is not None:
            error_msg += f" | Status: {e.response.status_code} | Response: {e.response.text}"
        logger.error(error_msg)
        return {"error": error_msg}

# ============================================================================
# Function 2.9: find_file_by_name
# ============================================================================
def find_file_by_name(name: str, parent_id: str) -> Optional[str]:
    """
    Find a file by name within a specific parent folder.

    Args:
        name: Name of the file to find
        parent_id: ID of the parent folder to search in

    Returns:
        str: The file ID if found, None otherwise

    Note:
        Returns None if no file is found or if there's an error
    """
    if not name or not parent_id:
        logger.warning("Name and parent ID are required for file search")
        return None

    try:
        query = f"name = '{name}' and '{parent_id}' in parents and trashed = false"
        params = {'q': query, 'fields': 'files(id, name)'}
        response = gdrive_request('GET', 'files', params=params)

        if 'error' in response:
            logger.error(f"Error finding file '{name}': {response['error']}")
            return None

        if 'files' in response and response['files']:
            return response['files'][0]['id']

        logger.debug(f"File '{name}' not found in folder {parent_id}")
        return None

    except Exception as e:
        logger.error(f"Error in find_file_by_name: {str(e)}")
        return None

# ============================================================================
# Function 2.10: gdrive_rename
# ============================================================================
def gdrive_rename(file_id: str, new_name: str) -> Dict[str, Any]:
    """
    Rename a file in Google Drive.

    Args:
        file_id: ID of the file to rename
        new_name: New name for the file

    Returns:
        dict: The updated file metadata on success, or an error dictionary
    """
    if not file_id or not new_name:
        return {"error": "File ID and new name are required"}

    token = get_gdrive_access_token()
    if not token:
        return {"error": "Failed to obtain Google Drive access token"}

    url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
    headers = {"Authorization": f"Bearer {token}"}
    data = {"name": new_name}

    try:
        resp = requests.patch(
            url,
            headers=headers,
            json=data,
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()

    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to rename file {file_id}"
        if hasattr(e, 'response') and e.response is not None:
            error_msg += f" | Status: {e.response.status_code} | Response: {e.response.text}"
        logger.error(error_msg)
        return {"error": error_msg}

# ============================================================================
# SECTION 3: GDriveManager Class
# ============================================================================
class GDriveManager:
    """Manages context persistence in Google Drive."""

    def __init__(self, root_folder_id: str):
        """
        Initializes the GDriveManager with the root folder ID for context files.
        """
        if not root_folder_id:
            raise ValueError("GDRIVE_ROOT_FOLDER_ID is not set.")
        self.root_folder_id = root_folder_id
        logger.info(f"GDriveManager initialized with root folder: {self.root_folder_id}")

    # ============================================================================
    # Async Function 3.1: save_context
    # ============================================================================
    async def save_context(self, context: dict, workflow_id: str):
        """
        Saves the workflow context to a JSON file in Google Drive.
        Updates the file if it exists, otherwise creates a new one.
        """
        context_filename = f"context_{workflow_id}.json"
        context_json = json.dumps(context, indent=4)

        try:
            # Check if file exists
            file_id = await asyncio.to_thread(find_file_by_name, context_filename, self.root_folder_id)

            if file_id:
                logger.info(f"Updating context file for workflow {workflow_id} (File ID:           {file_id}).")
                result = await asyncio.to_thread(gdrive_update, file_id, context_json.encode('utf-8'))
            else:
                logger.info(f"Creating new context file for workflow {workflow_id} in folder {self.root_folder_id}.")
                result = await asyncio.to_thread(gdrive_write, context_filename, self.root_folder_id, context_json.encode('utf-8'))

            if result is None or (isinstance(result, dict) and "error" in result):
                error_message = result.get('error', 'GDrive operation failed') if isinstance(result, dict) else 'GDrive operation returned no result'
                logger.error(
                    f"Failed to save context for workflow {workflow_id} | "
                    f"Error: {error_message} | "
                    f"File: {context_filename} | "
                    f"Folder: {self.root_folder_id}"
                )
                return False

            logger.success(f"Successfully saved context for workflow {workflow_id}.")
            return True
        except Exception as e:
            error_details = {
                'workflow_id': workflow_id,
                'context_file': context_filename,
                'error_type': type(e).__name__,
                'error_message': str(e),
                'root_folder': self.root_folder_id,
                'context_size': len(context_json) if 'context_json' in locals() else 0
            }
            logger.error(
                f"Unexpected error in save_context | "
                f"Workflow: {workflow_id} | "
                f"Error: {type(e).__name__}: {str(e)} | "
                f"Context size: {error_details['context_size']} chars"
            )
            logger.debug(f"Error details: {error_details}")
            return False

    # ============================================================================
    # Async Function 3.2: load_context
    # ============================================================================
    async def load_context(self, workflow_id: str) -> dict:
        """
        Loads the workflow context from a JSON file in Google Drive.
        """
        context_filename = f"context_{workflow_id}.json"

        try:
            file_id = await asyncio.to_thread(find_file_by_name, context_filename, self.root_folder_id)

            if not file_id:
                logger.info(
                    f"No context file found | "
                    f"Workflow: {workflow_id} | "
                    f"File: {context_filename} | "
                    f"Folder: {self.root_folder_id}"
                )
                return {}

            logger.info(
                f"Loading context | "
                f"Workflow: {workflow_id} | "
                f"File ID: {file_id} | "
                f"File: {context_filename}"
            )

            content = await asyncio.to_thread(gdrive_read, file_id)
            if not content:
                logger.error(
                    f"Empty content received | "
                    f"Workflow: {workflow_id} | "
                    f"File ID: {file_id} | "
                    f"File: {context_filename}"
                )
                return {}

            try:
                return json.loads(content)
            except json.JSONDecodeError as je:
                logger.error(
                    f"Failed to parse JSON content | "
                    f"Workflow: {workflow_id} | "
                    f"File ID: {file_id} | "
                    f"Error: {str(je)} | "
                    f"Content length: {len(content)} chars"
                )
                return {}

        except Exception as e:
            error_details = {
                'workflow_id': workflow_id,
                'context_file': context_filename,
                'error_type': type(e).__name__,
                'error_message': str(e),
                'root_folder': self.root_folder_id
            }
            error_message = f"{type(e).__name__}: {str(e)}"
            logger.error(
                f"Unexpected error in load_context | "
                f"Workflow: {workflow_id} | "
                f"Error: {error_message}"
            )
            logger.debug(f"Error details: {error_details}")
            return {
                "_error": True,
                "error_type": type(e).__name__,
                "error_message": error_message,
                "workflow_id": workflow_id,
                "context_file": context_filename
            }

#
#
## End Script
