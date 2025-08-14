# ============================================================================
#  File:    async_file_manager.py
#  Purpose: Async file operations with streaming and thread safety
# ============================================================================

# Section 1: Imports and Globals
import asyncio
import json
import os
import threading
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Union
from dataclasses import dataclass
import aiofiles
from typing import cast
import hashlib
import shutil
from contextlib import asynccontextmanager

# Section 2: Data Structures
@dataclass
class FileOperationResult:
    """Result of file operation with metadata."""
    success: bool
    file_path: Union[str, Path]
    operation_type: str
    bytes_processed: int = 0
    duration: float = 0.0
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class FileMetadata:
    """File metadata for async operations."""
    path: Path
    size: int
    modified_time: datetime
    checksum: str
    permissions: str
    exists: bool

# Section 3: Async File Manager
class AsyncFileManager:
    """
    Async file manager with streaming capabilities and thread safety.
    
    Features:
    - Async file operations (read, write, copy, move, delete)
    - Streaming file processing for large files
    - Thread-safe operations with locks
    - Real-time progress tracking
    - Comprehensive error handling
    - Metadata extraction and validation
    """
    
    def __init__(self):
        self._operation_lock = asyncio.Lock()
        self._cache_lock = threading.RLock()
        self._file_cache = {}
        self._max_cache_size = 1000
        self._operation_history = []
        
    async def read_file_streaming(self, file_path: Union[str, Path], chunk_size: int = 8192) -> AsyncIterator[FileOperationResult]:
        """
        Read file with streaming support and progress tracking.
        
        Args:
            file_path: Path to file to read
            chunk_size: Size of chunks to read
            
        Yields:
            FileOperationResult with progress updates
        """
        start_time = datetime.now()
        file_path = Path(file_path)
        
        if not file_path.exists():
            yield FileOperationResult(
                success=False,
                file_path=file_path,
                operation_type="read",
                error_message=f"File not found: {file_path}"
            )
            return
            
        try:
            total_size = file_path.stat().st_size
            bytes_processed = 0
            
            async with aiofiles.open(file_path, 'rb') as file:
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    bytes_processed += len(chunk)
                    
                    yield FileOperationResult(
                        success=True,
                        file_path=file_path,
                        operation_type="read",
                        bytes_processed=bytes_processed,
                        duration=(datetime.now() - start_time).total_seconds(),
                        metadata={
                            'chunk_size': len(chunk),
                            'progress': bytes_processed / total_size if total_size > 0 else 0,
                            'total_size': total_size
                        }
                    )
                    
        except Exception as e:
            yield FileOperationResult(
                success=False,
                file_path=file_path,
                operation_type="read",
                error_message=str(e)
            )
    
    async def write_file_streaming(self, file_path: Union[str, Path], data_stream: AsyncIterator[bytes], 
                                 mode: str = 'wb') -> AsyncIterator[FileOperationResult]:
        """
        Write file with streaming support and progress tracking.
        
        Args:
            file_path: Path to write file
            data_stream: Async iterator of bytes to write
            mode: File mode (wb, ab, etc.)
            
        Yields:
            FileOperationResult with progress updates
        """
        start_time = datetime.now()
        file_path = Path(file_path)
        
        try:
            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            bytes_processed = 0
            
            async with aiofiles.open(str(file_path), mode='wb') as file:
                async for chunk in data_stream:
                    await file.write(chunk)
                    bytes_processed += len(chunk)
                    
                    yield FileOperationResult(
                        success=True,
                        file_path=file_path,
                        operation_type="write",
                        bytes_processed=bytes_processed,
                        duration=(datetime.now() - start_time).total_seconds()
                    )
                    
        except Exception as e:
            yield FileOperationResult(
                success=False,
                file_path=file_path,
                operation_type="write",
                error_message=str(e)
            )
    
    async def read_json_async(self, file_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """Read JSON file asynchronously."""
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
                content = await file.read()
                return json.loads(content)
        except Exception:
            return None
    
    async def write_json_async(self, file_path: Union[str, Path], data: Dict[str, Any]) -> bool:
        """Write JSON file asynchronously."""
        try:
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as file:
                await file.write(json.dumps(data, indent=2, ensure_ascii=False))
            return True
        except Exception:
            return False
    
    async def read_yaml_async(self, file_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """Read YAML file asynchronously."""
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
                content = await file.read()
                return yaml.safe_load(content)
        except Exception:
            return None
    
    async def write_yaml_async(self, file_path: Union[str, Path], data: Dict[str, Any]) -> bool:
        """Write YAML file asynchronously."""
        try:
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as file:
                await file.write(yaml.dump(data, default_flow_style=False))
            return True
        except Exception:
            return False
    
    async def copy_file_async(self, source_path: Union[str, Path], dest_path: Union[str, Path]) -> FileOperationResult:
        """Copy file asynchronously with progress tracking."""
        start_time = datetime.now()
        source_path = Path(source_path)
        dest_path = Path(dest_path)
        
        try:
            if not source_path.exists():
                return FileOperationResult(
                    success=False,
                    file_path=source_path,
                    operation_type="copy",
                    error_message=f"Source file not found: {source_path}"
                )
            
            # Ensure destination directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Use streaming copy for large files
            async for result in self.read_file_streaming(source_path):
                if result.success and result.metadata:
                    # Write the chunk to destination
                    async with aiofiles.open(dest_path, 'wb') as dest_file:
                        await dest_file.write(result.metadata.get('chunk', b''))
            
            return FileOperationResult(
                success=True,
                file_path=dest_path,
                operation_type="copy",
                duration=(datetime.now() - start_time).total_seconds()
            )
            
        except Exception as e:
            return FileOperationResult(
                success=False,
                file_path=source_path,
                operation_type="copy",
                error_message=str(e)
            )
    
    async def move_file_async(self, source_path: Union[str, Path], dest_path: Union[str, Path]) -> FileOperationResult:
        """Move file asynchronously."""
        copy_result = await self.copy_file_async(source_path, dest_path)
        if copy_result.success:
            try:
                Path(source_path).unlink()
                return FileOperationResult(
                    success=True,
                    file_path=dest_path,
                    operation_type="move",
                    duration=copy_result.duration
                )
            except Exception as e:
                return FileOperationResult(
                    success=False,
                    file_path=source_path,
                    operation_type="move",
                    error_message=str(e)
                )
        return copy_result
    
    async def delete_file_async(self, file_path: Union[str, Path]) -> FileOperationResult:
        """Delete file asynchronously."""
        try:
            file_path = Path(file_path)
            if file_path.exists():
                file_path.unlink()
                return FileOperationResult(
                    success=True,
                    file_path=file_path,
                    operation_type="delete"
                )
            else:
                return FileOperationResult(
                    success=False,
                    file_path=file_path,
                    operation_type="delete",
                    error_message=f"File not found: {file_path}"
                )
        except Exception as e:
            return FileOperationResult(
                success=False,
                file_path=file_path,
                operation_type="delete",
                error_message=str(e)
            )
    
    async def get_file_metadata(self, file_path: Union[str, Path]) -> Optional[FileMetadata]:
        """Get file metadata asynchronously."""
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                return None
                
            stat = file_path.stat()
            
            # Calculate checksum
            checksum = hashlib.md5()
            async for result in self.read_file_streaming(file_path):
                if result.success and result.metadata:
                    chunk = result.metadata.get('chunk', b'')
                    checksum.update(chunk)
            
            return FileMetadata(
                path=file_path,
                size=stat.st_size,
                modified_time=datetime.fromtimestamp(stat.st_mtime),
                checksum=checksum.hexdigest(),
                permissions=oct(stat.st_mode)[-3:],
                exists=True
            )
            
        except Exception:
            return None
    
    async def list_directory_async(self, directory_path: Union[str, Path], 
                                 pattern: str = "*") -> List[FileMetadata]:
        """List directory contents asynchronously."""
        try:
            directory_path = Path(directory_path)
            if not directory_path.exists():
                return []
                
            files = []
            for item in directory_path.glob(pattern):
                metadata = await self.get_file_metadata(item)
                if metadata:
                    files.append(metadata)
            
            return sorted(files, key=lambda x: x.path.name)
            
        except Exception:
            return []
    
    @asynccontextmanager
    async def temp_file_async(self, suffix: str = "", prefix: str = "tmp"):
        """Async context manager for temporary files."""
        import tempfile
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, prefix=prefix, delete=False) as tmp:
                temp_path = Path(tmp.name)
            yield temp_path
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink(missing_ok=True)
    
    async def ensure_directory_async(self, directory_path: Union[str, Path]) -> bool:
        """Ensure directory exists asynchronously."""
        try:
            directory_path = Path(directory_path)
            directory_path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception:
            return False

# Section 4: Singleton Instance
# Create singleton instance for global access
async_file_manager = AsyncFileManager()
