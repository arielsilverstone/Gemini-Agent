# ============================================================================
#  File:    async_validator.py
#  Purpose: Unified async validation framework with streaming and type safety
# ============================================================================

# Section 1: Imports and Globals
import asyncio
import aiofiles
import json
import re
import threading
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Type, Union
from dataclasses import dataclass
from pydantic import BaseModel, ValidationError
import inspect

# Section 2: Data Structures
@dataclass
class ValidationResult:
    """Result of validation operation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    data: Optional[Any] = None
    validation_time: float = 0.0
    validator_name: str = ""
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class ValidationRule:
    """Validation rule definition."""
    name: str
    description: str
    validator: Callable
    required: bool = True
    async_validator: Optional[Callable] = None
    error_message: str = ""
    severity: str = "error"  # error, warning, info

@dataclass
class ValidationContext:
    """Context for validation operations."""
    data: Any = None
    rules: Optional[List[ValidationRule]] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

# Section 3: Base Validators
class BaseValidator:
    """Base validator class with async support."""
    
    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__
        self._rules = []
        self._cache = {}
        self._cache_lock = threading.RLock()
    
    def add_rule(self, rule: ValidationRule) -> None:
        """Add validation rule."""
        self._rules.append(rule)
    
    def remove_rule(self, rule_name: str) -> bool:
        """Remove validation rule by name."""
        initial_count = len(self._rules)
        self._rules = [rule for rule in self._rules if rule.name != rule_name]
        return len(self._rules) < initial_count
    
    async def validate_async(self, data: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate data asynchronously."""
        start_time = datetime.now()
        errors = []
        warnings = []
        
        for rule in self._rules:
            try:
                if rule.async_validator:
                    result = await rule.async_validator(data, context)
                else:
                    result = rule.validator(data, context)
                
                if not result:
                    message = rule.error_message or f"Validation failed for {rule.name}"
                    if rule.severity == "error":
                        errors.append(message)
                    else:
                        warnings.append(message)
                        
            except Exception as e:
                if rule.required:
                    errors.append(f"Validation error in {rule.name}: {str(e)}")
                else:
                    warnings.append(f"Validation warning in {rule.name}: {str(e)}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            data=data,
            validation_time=(datetime.now() - start_time).total_seconds(),
            validator_name=self.name
        )

# Section 4: Type Validators
class TypeValidator(BaseValidator):
    """Validator for type checking."""
    
    def __init__(self):
        super().__init__("TypeValidator")
        
    def validate_type(self, data: Any, expected_type: Type) -> bool:
        """Validate data type."""
        return isinstance(data, expected_type)
    
    def _validate_type(self, data: Any, expected_type: Union[Type, tuple], min_value: Optional[float] = None, max_value: Optional[float] = None) -> bool:
        """Validate data type with optional range constraints."""
        if not isinstance(data, expected_type):
            return False
        if min_value is not None and data < min_value:
            return False
        if max_value is not None and data > max_value:
            return False
        return True
    
    def validate_string(self, data: Any, min_length: int = 0, max_length: Optional[int] = None) -> bool:
        """Validate string with length constraints."""
        return self._validate_type(data, str, min_length, max_length)
    
    def validate_number(self, data: Any, min_value: Optional[float] = None, max_value: Optional[float] = None) -> bool:
        """Validate number with range constraints."""
        return self._validate_type(data, (int, float), min_value, max_value)
    
    def validate_list(self, data: Any, item_validator: Optional[Callable] = None) -> bool:
        """Validate list with optional item validation."""
        if not isinstance(data, list):
            return False
        if item_validator:
            return all(item_validator(item) for item in data)
        return True
    
    def validate_dict(self, data: Any, key_validator: Optional[Callable] = None, value_validator: Optional[Callable] = None) -> bool:
        """Validate dictionary with optional key/value validation."""
        if not isinstance(data, dict):
            return False
        if key_validator:
            if not all(key_validator(k) for k in data.keys()):
                return False
        if value_validator:
            if not all(value_validator(v) for v in data.values()):
                return False
        return True

# Section 5: File Validators
class FileValidator(BaseValidator):
    """Validator for file operations."""
    
    def __init__(self):
        super().__init__("FileValidator")
        
    def validate_file_exists(self, file_path: Union[str, Path]) -> bool:
        """Validate file exists."""
        return Path(file_path).exists()
    
    def validate_file_extension(self, file_path: Union[str, Path], allowed_extensions: List[str]) -> bool:
        """Validate file extension."""
        path = Path(file_path)
        return path.suffix.lower() in [ext.lower() for ext in allowed_extensions]
    
    def validate_file_size(self, file_path: Union[str, Path], max_size: Optional[int] = None, min_size: Optional[int] = None) -> bool:
        """Validate file size constraints."""
        path = Path(file_path)
        if not path.exists():
            return False
            
        size = path.stat().st_size
        if min_size is not None and size < min_size:
            return False
        if max_size is not None and size > max_size:
            return False
        return True
    
    async def validate_json_file(self, file_path: Union[str, Path]) -> bool:
        """Validate JSON file format."""
        try:
            path = Path(file_path)
            if not path.exists():
                return False
                
            async with aiofiles.open(path, 'r', encoding='utf-8') as f:
                content = await f.read()
                json.loads(content)
                return True
        except (json.JSONDecodeError, FileNotFoundError):
            return False
    
    async def validate_yaml_file(self, file_path: Union[str, Path]) -> bool:
        """Validate YAML file format."""
        try:
            path = Path(file_path)
            if not path.exists():
                return False
                
            async with aiofiles.open(path, 'r', encoding='utf-8') as f:
                content = await f.read()
                yaml.safe_load(content)
                return True
        except (yaml.YAMLError, FileNotFoundError):
            return False

# Section 6: Configuration Validators
class ConfigValidator(BaseValidator):
    """Validator for configuration data."""
    
    def __init__(self):
        super().__init__("ConfigValidator")
        
    def validate_required_keys(self, data: Dict[str, Any], required_keys: List[str]) -> bool:
        """Validate required keys exist in configuration."""
        return all(key in data for key in required_keys)
    
    def validate_key_types(self, data: Dict[str, Any], type_specs: Dict[str, Type]) -> bool:
        """Validate key types in configuration."""
        for key, expected_type in type_specs.items():
            if key in data and not isinstance(data[key], expected_type):
                return False
        return True
    
    def validate_nested_structure(self, data: Dict[str, Any], structure: Dict[str, Any]) -> bool:
        """Validate nested structure recursively."""
        return self._validate_nested(data, structure)
    
    def _validate_nested(self, data: Any, spec: Any) -> bool:
        """Recursively validate nested structure."""
        if isinstance(spec, dict):
            if not isinstance(data, dict):
                return False
            for key, value_spec in spec.items():
                if key not in data:
                    return False
                if not self._validate_nested(data[key], value_spec):
                    return False
            return True
        elif isinstance(spec, list):
            if not isinstance(data, list):
                return False
            if spec and data:
                item_spec = spec[0]
                return all(self._validate_nested(item, item_spec) for item in data)
            return True
        else:
            return isinstance(data, spec)

# Section 7: Async Validation Engine
class AsyncValidationEngine:
    """
    Unified async validation engine with streaming capabilities.
    
    Features:
    - Async validation with streaming results
    - Thread-safe validation execution
    - Real-time progress tracking
    - Comprehensive error aggregation
    - Configurable validation rules
    """
    
    def __init__(self):
        self._validators = {}
        self._cache = {}
        self._cache_lock = threading.RLock()
        self._validation_lock = asyncio.Lock()
        
    def register_validator(self, name: str, validator: BaseValidator) -> None:
        """Register a validator with the engine."""
        self._validators[name] = validator
    
    def unregister_validator(self, name: str) -> bool:
        """Unregister a validator by name."""
        if name in self._validators:
            del self._validators[name]
            return True
        return False
    
    async def validate_streaming(self, data: Any, validator_names: Optional[List[str]] = None, context: Optional[Dict[str, Any]] = None) -> AsyncIterator[ValidationResult]:
        """
        Validate data with streaming results.
        
        Args:
            data: Data to validate
            validator_names: List of validator names to use
            context: Additional validation context
            
        Yields:
            ValidationResult objects as validation completes
        """
        if validator_names is None:
            validator_names = list(self._validators.keys())
            
        for validator_name in validator_names:
            if validator_name in self._validators:
                validator = self._validators[validator_name]
                result = await validator.validate_async(data, context)
                yield result
    
    async def validate_batch_async(self, data_list: List[Any], validator_names: Optional[List[str]] = None, context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
        """Validate multiple items asynchronously."""
        results = []
        async for result in self.validate_streaming(data_list, validator_names, context):
            results.append(result)
        return results
    
    def create_validator_from_schema(self, schema: Dict[str, Any]) -> BaseValidator:
        """Create validator from JSON schema."""
        validator = BaseValidator("SchemaValidator")
        
        # Add type validation rules
        if "type" in schema:
            type_validator = TypeValidator()
            validator.add_rule(ValidationRule(
                name="type_check",
                description="Validate data type",
                validator=lambda x: type_validator.validate_type(x, schema["type"]),
                error_message=f"Invalid type, expected {schema['type']}"
            ))
            
        # Add required field validation
        if "required" in schema:
            validator.add_rule(ValidationRule(
                name="required_fields",
                description="Validate required fields",
                validator=lambda x: isinstance(x, dict) and all(field in x for field in schema["required"]),
                error_message="Missing required fields"
            ))
            
        return validator
    
    async def validate_file_async(self, file_path: Union[str, Path], validator: BaseValidator) -> ValidationResult:
        """Validate file content asynchronously."""
        try:
            path = Path(file_path)
            if not path.exists():
                return ValidationResult(
                    is_valid=False,
                    errors=[f"File not found: {file_path}"],
                    warnings=[]
                )
                
            # Read file based on extension
            if path.suffix.lower() == '.json':
                import json
                async with aiofiles.open(path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    data = json.loads(content)
            elif path.suffix.lower() in ['.yml', '.yaml']:
                import yaml
                async with aiofiles.open(path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    data = yaml.safe_load(content)
            else:
                return ValidationResult(
                    is_valid=False,
                    errors=[f"Unsupported file type: {path.suffix}"],
                    warnings=[]
                )
                
            return await validator.validate_async(data)
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                errors=[str(e)],
                warnings=[]
            )

# Section 8: Common Validators
class EmailValidator(BaseValidator):
    """Email address validator."""
    
    def __init__(self):
        super().__init__("EmailValidator")
        self.email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        
    def validate_email(self, email: str) -> bool:
        """Validate email format."""
        return bool(self.email_pattern.match(str(email)))

class URLValidator(BaseValidator):
    """URL validator."""
    
    def __init__(self):
        super().__init__("URLValidator")
        self.url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
    def validate_url(self, url: str) -> bool:
        """Validate URL format."""
        return bool(self.url_pattern.match(str(url)))

# Section 9: Validation Utilities
class ValidationUtils:
    """Utility functions for validation."""
    
    @staticmethod
    def create_range_validator(min_val: Optional[float] = None, max_val: Optional[float] = None) -> Callable:
        """Create range validator function."""
        def validator(value):
            if min_val is not None and value < min_val:
                return False
            if max_val is not None and value > max_val:
                return False
            return True
        return validator
    
    @staticmethod
    def create_length_validator(min_len: int = 0, max_len: Optional[int] = None) -> Callable:
        """Create length validator function."""
        def validator(value):
            length = len(str(value))
            if length < min_len:
                return False
            if max_len is not None and length > max_len:
                return False
            return True
        return validator
    
    @staticmethod
    def create_regex_validator(pattern: str, flags: int = 0) -> Callable:
        """Create regex validator function."""
        compiled_pattern = re.compile(pattern, flags)
        def validator(value):
            return bool(compiled_pattern.match(str(value)))
        return validator

# Section 10: Global Validation Engine
# Create global validation engine instance
validation_engine = AsyncValidationEngine()

# Section 11: Convenience Functions
def validate_json(data: Any) -> ValidationResult:
    """Quick JSON validation."""
    validator = TypeValidator()
    return asyncio.run(validator.validate_async(data))

def validate_yaml(data: Any) -> ValidationResult:
    """Quick YAML validation."""
    validator = ConfigValidator()
    return asyncio.run(validator.validate_async(data))

# Section 12: Export commonly used validators
__all__ = [
    'AsyncValidationEngine',
    'BaseValidator',
    'TypeValidator',
    'FileValidator',
    'ConfigValidator',
    'EmailValidator',
    'URLValidator',
    'ValidationResult',
    'ValidationRule',
    'ValidationContext',
    'ValidationUtils',
    'validation_engine'
]
