# ============================================================================
#  File: rule_engine.py
#  Version: 2.0 (Complete Implementation)
#  Purpose: Advanced rule engine with action execution for Gemini-Agent
#  Created: 04AUG25
# ============================================================================
# SECTION 1: Global Variable Definitions & Imports
# ============================================================================
#
import re
import threading
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import yaml
from loguru import logger
#
# ============================================================================
# SECTION 2: Data Classes and Enums
# ============================================================================
# Class 2.1: ActionType
# ============================================================================
class ActionType(Enum):
    """Enumeration of all supported rule actions"""

    REJECT = "reject"
    AUTOFIX = "autofix"
    REFIX = "refix"
    RE_QA = "re-qa"
    DOC = "doc"
    PLAN = "plan"
    TEMPLATE_OVERRIDE = "template_override"
    RETRY_WITH_CONSTRAINT = "retry_with_constraint"
    UPDATE = "update"
    FLAG = "flag"
#
# ============================================================================
# Class 2.2: SeverityLevel
# ============================================================================
#
class SeverityLevel(Enum):
    """Rule severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
#
# ============================================================================
# Class 2.3: RuleViolation
# ============================================================================
#
@dataclass
class RuleViolation:
    """Represents a rule violation with context"""

    rule_id: str
    rule_name: str
    rule_type: str
    message: str
    action: ActionType
    severity: SeverityLevel
    llm_guidance: Optional[Dict[str, Any]] = None
    template_override: Optional[str] = None
    template_modifications: Optional[List[Dict]] = None
    template_chain: Optional[List[str]] = None
    violation_context: Optional[Dict[str, Any]] = None
#
# ============================================================================
# Class 2.4: ActionResult
# ============================================================================
#
@dataclass
class ActionResult:
    """Result of executing a rule action"""

    success: bool
    action_type: ActionType
    new_content: Optional[str] = None
    new_template: Optional[str] = None
    retry_prompt: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
#
# ============================================================================
# Class 2.5: ProcessingResult
# ============================================================================
#
@dataclass
class ProcessingResult:
    """Result of processing multiple rule violations"""

    violations_processed: int
    actions_executed: List[ActionResult]
    final_content: Optional[str] = None
    final_template: Optional[str] = None
    should_retry: bool = False
    retry_prompt: Optional[str] = None
    processing_errors: List[str] = None
#
# ============================================================================
# Class 2.6: RuleEngine
# ============================================================================
#
class RuleEngine:
    """
    Advanced rule engine with action execution, template management,
    and LLM guidance integration for Gemini-Agent.
    """

    _instance: Optional["RuleEngine"] = None
    _initialized: bool = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(RuleEngine, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        config_manager: Optional[Any] = None,
        agent_configs: Optional[Dict[str, Any]] = None,
    ):
        if self._initialized:
            return

        self._agent_rules: Dict[str, List[Dict[str, Any]]] = {}
        self._global_rules: List[Dict[str, Any]] = []
        self._config_manager = config_manager
        self._template_cache: Dict[str, str] = {}
        self._processing_config: Dict[str, Any] = {}
        self._lock = threading.Lock()

        # Load rules and configuration
        self._load_rules(agent_configs)
        self._load_processing_config()
        self._initialized = True

    # ========================================================================
    # Method 2.6.1: load_rules
    # ========================================================================
    def _load_rules(self, agent_configs: Optional[Dict[str, Any]] = None) -> None:
        """Enhanced rule loading with validation and error handling"""
        if not self._config_manager or not hasattr(
            self._config_manager, "get_rules_path"
        ):
            logger.warning(
                "RuleEngine: ConfigManager not available, using minimal rules"
            )
            self._load_minimal_rules()
            return

        rules_path = self._config_manager.get_rules_path()
        try:
            with open(rules_path, "r", encoding="utf-8") as f:
                rules_data = yaml.safe_load(f)

            if not rules_data:
                logger.warning(f"Empty rules data in file: {rules_path}")
                self._load_minimal_rules()
                return

            # Load and validate agent rules
            agent_rules_list = rules_data.get("agent_rules", [])
            if isinstance(agent_rules_list, list) and agent_configs:
                for item in agent_rules_list:
                    agent_name = item.get("agent_name")
                    if agent_name in agent_configs:
                        rules = item.get("rules", [])
                        if isinstance(rules, list):
                            # Validate each rule
                            validated_rules = []
                            for rule in rules:
                                if self._validate_rule_structure(rule):
                                    validated_rules.append(rule)
                                else:
                                    logger.warning(
                                        f"Invalid rule structure for {agent_name}: {rule.get('id', 'unknown')}"
                                    )
                            self._agent_rules[agent_name] = validated_rules

            # Load and validate global rules
            global_rules = rules_data.get("global_rules", [])
            if isinstance(global_rules, list):
                validated_global_rules = []
                for rule in global_rules:
                    if self._validate_rule_structure(rule):
                        validated_global_rules.append(rule)
                    else:
                        logger.warning(
                            f"Invalid global rule structure: {rule.get('id', 'unknown')}"
                        )
                self._global_rules = validated_global_rules

            # Load processing configuration
            self._processing_config = rules_data.get("rule_processing", {})

            # Load template inheritance configuration
            self._template_inheritance = rules_data.get("template_inheritance", {})

            logger.info(
                f"Successfully loaded rules: {len(self._agent_rules)} agent rule sets, {len(self._global_rules)} global rules"
            )

        except FileNotFoundError:
            logger.warning(
                f"Rules file not found at {rules_path}. Loading minimal rules."
            )
            self._load_minimal_rules()
        except (yaml.YAMLError, AttributeError, TypeError) as e:
            logger.error(f"Error parsing rules file {rules_path}: {e}")
            self._load_minimal_rules()
    #
    # ========================================================================
    # Method 2.6.2: _load_minimal_rules
    # ========================================================================
    #
    def _load_minimal_rules(self) -> None:
        """Load minimal fallback rules when main rules file is unavailable"""
        self._global_rules = [
            {
                "id": "GL_FALLBACK_001",
                "rule_name": "output-minimum-length",
                "description": "Ensure outputs meet minimum length",
                "type": "output_structure_check",
                "min_length": 50,
                "action": "retry_with_constraint",
                "severity": "medium",
                "message": "Output too brief, needs more detail",
                "llm_guidance": {
                    "primary": "Expand the response with more detailed explanations"
                },
            }
        ]
        self._processing_config = {
            "max_retries": 3,
            "auto_fix_enabled": True,
            "action_priorities": {
                "reject": 1,
                "template_override": 2,
                "retry_with_constraint": 3,
                "flag": 4,
            },
        }
        logger.info("Loaded minimal fallback rules")
    #
    # ========================================================================
    # Method 2.6.3: _validate_rule_structure
    # ========================================================================
    #
    def _validate_rule_structure(self, rule: Dict[str, Any]) -> bool:
        """Validate that a rule has required fields"""
        required_fields = ["id", "rule_name", "type", "action", "severity", "message"]
        return all(field in rule for field in required_fields)
    #
    # ========================================================================
    # Method 2.6.4: _load_processing_config
    # ========================================================================
    #
    def _load_processing_config(self) -> None:
        """Load processing configuration with defaults"""
        default_config = {
            "max_retries": 3,
            "retry_delay": 2,
            "escalation_threshold": 2,
            "auto_fix_enabled": True,
            "template_cache_enabled": True,
            "action_priorities": {
                "reject": 1,
                "template_override": 2,
                "retry_with_constraint": 3,
                "autofix": 4,
                "refix": 5,
                "re-qa": 6,
                "update": 7,
                "flag": 8,
            },
            "severity_handling": {
                "high": "immediate_action",
                "medium": "next_iteration",
                "low": "background_processing",
            },
        }

        # Merge with loaded config
        for key, value in default_config.items():
            if key not in self._processing_config:
                self._processing_config[key] = value
    #
    # ========================================================================
    # Method 2.6.5: get_global_rules
    # ========================================================================
    #
    def get_global_rules(self) -> List[Dict[str, Any]]:
        """Retrieve all global rules"""
        with self._lock:
            return self._global_rules.copy()
    #
    # ========================================================================
    # Method 2.6.6: get_agent_rules
    # ========================================================================
    #
    def get_agent_rules(self, agent_name: str) -> List[Dict[str, Any]]:
        """Retrieve all applicable rules for a given agent"""
        with self._lock:
            agent_specific_rules = self._agent_rules.get(agent_name, [])
            return agent_specific_rules + self._global_rules
    #
    # ========================================================================
    # Async Function 2.6.7: validate_output
    # ========================================================================
    #
    async def validate_output(
        self, output: str, agent_name: str, task: str, context: Optional[Dict] = None
    ) -> List[RuleViolation]:
        """
        Validate output against all applicable rules and return violations
        """
        violations = []
        applicable_rules = self.get_agent_rules(agent_name)

        for rule in applicable_rules:
            try:
                violation_found, violation_message = await self._check_rule_violation(
                    output, rule, task, context
                )
                if violation_found:
                    violation = RuleViolation(
                        rule_id=rule.get("id", "unknown"),
                        rule_name=rule.get("rule_name", "Unknown Rule"),
                        rule_type=rule.get("type", "unknown"),
                        message=violation_message,
                        action=ActionType(rule.get("action", "flag")),
                        severity=SeverityLevel(rule.get("severity", "medium")),
                        llm_guidance=rule.get("llm_guidance"),
                        template_override=rule.get("template_override"),
                        template_modifications=rule.get("template_modifications"),
                        template_chain=rule.get("template_chain"),
                        violation_context={
                            "agent_name": agent_name,
                            "task": task,
                            "context": context,
                            "output_preview": (
                                output[:200] + "..." if len(output) > 200 else output
                            ),
                        },
                    )
                    violations.append(violation)
            except Exception as e:
                logger.error(f"Error checking rule {rule.get('id', 'unknown')}: {e}")
                continue

        # Sort violations by action priority
        action_priorities = self._processing_config.get("action_priorities", {})
        violations.sort(key=lambda v: action_priorities.get(v.action.value, 99))

        return violations
    #
    # ========================================================================
    # Async Function 2.6.8: _check_rule_violation
    # ========================================================================
    #
    async def _check_rule_violation(
        self, output: str, rule: Dict[str, Any], task: str, context: Optional[Dict]
    ) -> Tuple[bool, str]:
        """Check if output violates a specific rule"""
        rule_type = rule.get("type", "")

        if rule_type == "content_check":
            return self._check_content_rule(output, rule)
        elif rule_type == "code_quality_check":
            return self._check_code_quality_rule(output, rule)
        elif rule_type == "output_structure_check":
            return self._check_output_structure_rule(output, rule)
        elif rule_type == "regex":
            return self._check_regex_rule(output, rule)
        elif rule_type == "security_check":
            return self._check_security_rule(output, rule)
        elif rule_type == "formatting_check":
            return self._check_formatting_rule(output, rule)
        elif rule_type == "documentation_check":
            return self._check_documentation_rule(output, rule)
        elif rule_type == "template_adherence":
            return self._check_template_adherence_rule(output, rule)
        else:
            logger.warning(f"Unknown rule type: {rule_type}")
            return False, ""
    #
    # ========================================================================
    # Method 2.6.9: _check_content_rule
    # ========================================================================
    #
    def _check_content_rule(
        self, output: str, rule: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Check content-based rules"""
        keywords_to_avoid = rule.get("keywords_to_avoid", [])
        keywords_to_detect = rule.get("keywords_to_detect", [])
        min_length = rule.get("min_length", 0)

        # Check forbidden keywords
        for keyword in keywords_to_avoid:
            if keyword.lower() in output.lower():
                return True, f"Forbidden keyword '{keyword}' found in output"

        # Check required keywords
        for keyword in keywords_to_detect:
            if keyword.lower() in output.lower():
                return True, f"Security-sensitive keyword '{keyword}' detected"

        # Check minimum length
        if len(output) < min_length:
            return True, f"Output too short ({len(output)} chars, minimum {min_length})"

        return False, ""
    #
    # ========================================================================
    # Method 2.6.10: _check_code_quality_rule
    # ========================================================================
    #
    def _check_code_quality_rule(
        self, output: str, rule: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Check code quality rules"""
        pattern = rule.get("pattern", "")
        min_coverage = rule.get("min_coverage", 0)
        required_metrics = rule.get("required_metrics", [])

        if pattern:
            if not re.search(pattern, output, re.MULTILINE | re.DOTALL):
                return True, f"Required code pattern not found: {pattern}"

        # Check for function docstrings (specific pattern)
        if "docstring" in rule.get("rule_name", "").lower():
            # Look for function definitions without docstrings
            func_pattern = r'def\s+\w+\([^)]*\):\s*\n(?!\s*""")'
            if re.search(func_pattern, output):
                return True, "Function definitions missing docstrings"

        return False, ""
    #
    # ========================================================================
    # Method 2.6.11: _check_output_structure_rule
    # ========================================================================
    #
    def _check_output_structure_rule(
        self, output: str, rule: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Check output structure rules"""
        required_sections = rule.get("required_sections", [])
        min_length = rule.get("min_length", 0)

        # Check required sections
        for section in required_sections:
            if section not in output:
                return True, f"Required section '{section}' missing from output"

        # Check minimum length
        if len(output) < min_length:
            return True, f"Output too brief ({len(output)} chars, minimum {min_length})"

        return False, ""
    #
    # ========================================================================
    # Method 2.6.12: _check_regex_rule
    # ========================================================================
    #
    def _check_regex_rule(self, output: str, rule: Dict[str, Any]) -> Tuple[bool, str]:
        """Check regex-based rules"""
        pattern = rule.get("pattern", "")
        if pattern:
            if re.search(pattern, output):
                return True, rule.get("message", f"Pattern '{pattern}' found in output")
        return False, ""
    #
    # ========================================================================
    # Method 2.6.13: _check_security_rule
    # ========================================================================
    #
    def _check_security_rule(
        self, output: str, rule: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Check security-related rules"""
        vulnerability_patterns = rule.get("vulnerability_patterns", [])

        for vuln_type in vulnerability_patterns:
            if vuln_type == "hardcoded_secrets":
                # Simple pattern for potential secrets
                secret_patterns = [
                    r'password\s*=\s*["\'][^"\']+["\']',
                    r'api_key\s*=\s*["\'][^"\']+["\']',
                    r'secret\s*=\s*["\'][^"\']+["\']',
                ]
                for pattern in secret_patterns:
                    if re.search(pattern, output, re.IGNORECASE):
                        return True, f"Potential hardcoded secret detected"

        return False, ""
    #
    # ========================================================================
    # Method 2.6.14: _check_formatting_rule
    # ========================================================================
    #
    def _check_formatting_rule(
        self, output: str, rule: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Check formatting rules"""
        checks = rule.get("checks", [])

        for check in checks:
            if check == "line_length":
                lines = output.split("\n")
                for i, line in enumerate(lines):
                    if len(line) > 79:  # PEP 8 standard
                        return (
                            True,
                            f"Line {i+1} exceeds 79 characters ({len(line)} chars)",
                        )

        return False, ""
    #
    # ========================================================================
    # Method 2.6.15: check_documentation_rule
    # ========================================================================
    #
    def check_documentation_rule(
        self, output: str, rule: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Check documentation rules"""
        api_requirements = rule.get("api_requirements", [])

        for requirement in api_requirements:
            if requirement == "parameters" and "Parameters:" not in output:
                return True, "API documentation missing parameters section"
            elif requirement == "return_values" and "Returns:" not in output:
                return True, "API documentation missing return values section"

        return False, ""
    #
    # ========================================================================
    # Method 2.6.16: check_template_adherence_rule
    # ========================================================================
    #
    def check_template_adherence_rule(
        self, output: str, rule: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Check template adherence rules"""
        template_requirements = rule.get("template_requirements", [])

        for requirement in template_requirements:
            if requirement == "consistent_formatting":
                # Basic check for consistent heading styles
                headings = re.findall(r"^#+\s+.+$", output, re.MULTILINE)
                if len(headings) > 1:
                    # Check if all headings start with proper spacing
                    for heading in headings:
                        if not re.match(r"^#+\s+\S", heading):
                            return True, "Inconsistent heading formatting detected"

        return False, ""
    #
    # ========================================================================
    # Async Method 2.6.17: process_violations (Main Action Execution Engine)
    # ========================================================================
    #
    async def process_violations(
        self,
        violations: List[RuleViolation],
        original_output: str,
        agent_name: str,
        task: str,
        context: Optional[Dict] = None,
    ) -> ProcessingResult:
        """
        Process rule violations by executing appropriate actions
        """
        if not violations:
            return ProcessingResult(
                violations_processed=0,
                actions_executed=[],
                final_content=original_output,
            )

        actions_executed = []
        current_content = original_output
        current_template = None
        processing_errors = []
        should_retry = False
        retry_prompt = None

        logger.info(f"Processing {len(violations)} rule violations for {agent_name}")

        for violation in violations:
            try:
                logger.debug(
                    f"Processing violation: {violation.rule_name} (action: {violation.action.value})"
                )

                action_result = await self._execute_action(
                    violation, current_content, agent_name, task, context
                )

                actions_executed.append(action_result)

                if action_result.success:
                    # Update content/template based on action result
                    if action_result.new_content:
                        current_content = action_result.new_content
                    if action_result.new_template:
                        current_template = action_result.new_template
                    if action_result.retry_prompt:
                        should_retry = True
                        retry_prompt = action_result.retry_prompt

                    logger.info(
                        f"Successfully executed {violation.action.value} for rule {violation.rule_name}"
                    )
                else:
                    error_msg = f"Failed to execute {violation.action.value} for rule {violation.rule_name}: {action_result.error_message}"
                    processing_errors.append(error_msg)
                    logger.error(error_msg)

            except Exception as e:
                error_msg = f"Exception executing action for rule {violation.rule_name}: {str(e)}"
                processing_errors.append(error_msg)
                logger.error(error_msg, exc_info=True)

        return ProcessingResult(
            violations_processed=len(violations),
            actions_executed=actions_executed,
            final_content=current_content,
            final_template=current_template,
            should_retry=should_retry,
            retry_prompt=retry_prompt,
            processing_errors=processing_errors if processing_errors else None,
        )
    #
    # ========================================================================
    # Async Method 2.6.18: _execute_action (Action Execution Router)
    # ========================================================================
    #
    async def _execute_action(
        self,
        violation: RuleViolation,
        content: str,
        agent_name: str,
        task: str,
        context: Optional[Dict],
    ) -> ActionResult:
        """Execute the appropriate action for a rule violation"""

        try:
            if violation.action == ActionType.REJECT:
                return await self._action_reject(
                    violation, content, agent_name, task, context
                )
            elif violation.action == ActionType.TEMPLATE_OVERRIDE:
                return await self._action_template_override(
                    violation, content, agent_name, task, context
                )
            elif violation.action == ActionType.RETRY_WITH_CONSTRAINT:
                return await self._action_retry_with_constraint(
                    violation, content, agent_name, task, context
                )
            elif violation.action == ActionType.AUTOFIX:
                return await self._action_autofix(
                    violation, content, agent_name, task, context
                )
            elif violation.action == ActionType.REFIX:
                return await self._action_refix(
                    violation, content, agent_name, task, context
                )
            elif violation.action == ActionType.RE_QA:
                return await self._action_re_qa(
                    violation, content, agent_name, task, context
                )
            elif violation.action == ActionType.DOC:
                return await self._action_doc(
                    violation, content, agent_name, task, context
                )
            elif violation.action == ActionType.PLAN:
                return await self._action_plan(
                    violation, content, agent_name, task, context
                )
            elif violation.action == ActionType.UPDATE:
                return await self._action_update(
                    violation, content, agent_name, task, context
                )
            elif violation.action == ActionType.FLAG:
                return await self._action_flag(
                    violation, content, agent_name, task, context
                )
            else:
                return ActionResult(
                    success=False,
                    action_type=violation.action,
                    error_message=f"Unknown action type: {violation.action.value}",
                )

        except Exception as e:
            logger.error(
                f"Error executing action {violation.action.value}: {e}", exc_info=True
            )
            return ActionResult(
                success=False,
                action_type=violation.action,
                error_message=f"Exception during action execution: {str(e)}",
            )
    #
    # ========================================================================
    # Async Method 2.6.19: _action_reject
    # ========================================================================
    #
    async def _action_reject(
        self,
        violation: RuleViolation,
        content: str,
        agent_name: str,
        task: str,
        context: Optional[Dict],
    ) -> ActionResult:
        """Execute REJECT action - prevent output and provide guidance"""
        guidance_prompt = self._construct_guidance_prompt(violation, "reject")

        return ActionResult(
            success=True,
            action_type=ActionType.REJECT,
            new_content="[REJECTED] " + violation.message,
            retry_prompt=guidance_prompt,
            metadata={"rejection_reason": violation.message},
        )
    #
    # ========================================================================
    # Async Method 2.6.20: _action_template_override
    # ========================================================================
    #
    async def _action_template_override(
        self,
        violation: RuleViolation,
        content: str,
        agent_name: str,
        task: str,
        context: Optional[Dict],
    ) -> ActionResult:
        """Execute TEMPLATE_OVERRIDE action - switch to different template"""

        # Handle different template override mechanisms
        if violation.template_override:
            # A: Simple template replacement
            new_template = violation.template_override
            logger.info(f"Applying template override: {new_template}")

        elif violation.template_modifications:
            # C: Dynamic template modifications
            new_template = await self._apply_template_modifications(
                content, violation.template_modifications, agent_name
            )
            logger.info("Applied dynamic template modifications")

        elif violation.template_chain:
            # D: Template inheritance chain
            new_template = await self._apply_template_chain(
                violation.template_chain, agent_name
            )
            logger.info(
                f"Applied template inheritance chain: {violation.template_chain}"
            )

        else:
            # Fallback to guidance-based template suggestion
            new_template = f"enhanced_{agent_name}_template"
            logger.warning(
                f"No template override specified, using fallback: {new_template}"
            )

        guidance_prompt = self._construct_guidance_prompt(
            violation, "template_override"
        )

        return ActionResult(
            success=True,
            action_type=ActionType.TEMPLATE_OVERRIDE,
            new_template=new_template,
            retry_prompt=guidance_prompt,
            metadata={"template_mechanism": "override", "new_template": new_template},
        )
    #
    # ========================================================================
    # Async Method 2.6.21: _action_retry_with_constraint
    # ========================================================================
    #
    async def _action_retry_with_constraint(
        self,
        violation: RuleViolation,
        content: str,
        agent_name: str,
        task: str,
        context: Optional[Dict],
    ) -> ActionResult:
        """Execute RETRY_WITH_CONSTRAINT action - retry with enhanced guidance"""

        guidance_prompt = self._construct_guidance_prompt(
            violation, "retry_with_constraint"
        )

        # Add specific constraints based on violation type
        constraint_prompt = self._build_constraint_prompt(violation, content)

        full_retry_prompt = (
            f"{guidance_prompt}\n\nSPECIFIC CONSTRAINTS:\n{constraint_prompt}"
        )

        return ActionResult(
            success=True,
            action_type=ActionType.RETRY_WITH_CONSTRAINT,
            retry_prompt=full_retry_prompt,
            metadata={
                "constraint_type": violation.rule_type,
                "original_violation": violation.message,
            },
        )
    #
    # ========================================================================
    # Async Method 2.6.22: _action_autofix
    # ========================================================================
    #
    async def _action_autofix(
        self,
        violation: RuleViolation,
        content: str,
        agent_name: str,
        task: str,
        context: Optional[Dict],
    ) -> ActionResult:
        """Execute AUTOFIX action - automatically fix simple issues"""

        fixed_content = content
        fix_applied = False

        # Apply automatic fixes based on rule type
        if violation.rule_type == "formatting_check":
            fixed_content = self._apply_formatting_fixes(content)
            fix_applied = True

        elif (
            violation.rule_type == "content_check"
            and "profanity" in violation.rule_name.lower()
        ):
            fixed_content = self._apply_profanity_fixes(content)
            fix_applied = True

        if fix_applied:
            return ActionResult(
                success=True,
                action_type=ActionType.AUTOFIX,
                new_content=fixed_content,
                metadata={
                    "fix_type": violation.rule_type,
                    "original_length": len(content),
                    "fixed_length": len(fixed_content),
                },
            )
        else:
            # Fallback to guided retry
            guidance_prompt = self._construct_guidance_prompt(violation, "autofix")
            return ActionResult(
                success=True,
                action_type=ActionType.AUTOFIX,
                retry_prompt=guidance_prompt,
                metadata={"fix_type": "guided_retry"},
            )
    #
    # ========================================================================
    # Async Method 2.6.23: _action_refix
    # ========================================================================
    #
    async def _action_refix(
        self,
        violation: RuleViolation,
        content: str,
        agent_name: str,
        task: str,
        context: Optional[Dict],
    ) -> ActionResult:
        """Execute REFIX action - comprehensive fix with analysis"""

        guidance_prompt = self._construct_guidance_prompt(violation, "refix")

        # Enhanced guidance for comprehensive fixing
        analysis_prompt = f"""
COMPREHENSIVE FIX REQUIRED:

ISSUE ANALYSIS:
- Rule Violated: {violation.rule_name}
- Problem: {violation.message}
- Severity: {violation.severity.value}

CURRENT OUTPUT ANALYSIS:
{content[:500]}...

{guidance_prompt}

REFIX REQUIREMENTS:
1. Address the root cause of the issue
2. Improve overall code quality
3. Ensure compliance with all relevant standards
4. Provide clear documentation of changes made
"""

        return ActionResult(
            success=True,
            action_type=ActionType.REFIX,
            retry_prompt=analysis_prompt,
            metadata={"fix_scope": "comprehensive", "analysis_included": True},
        )
    #
    # ========================================================================
    # Async Method 2.6.24: _action_re_qa
    # ========================================================================
    #
    async def _action_re_qa(
        self,
        violation: RuleViolation,
        content: str,
        agent_name: str,
        task: str,
        context: Optional[Dict],
    ) -> ActionResult:
        """Execute RE_QA action - re-analyze with QA focus"""

        guidance_prompt = self._construct_guidance_prompt(violation, "re_qa")

        qa_prompt = f"""
RE-QA ANALYSIS REQUIRED:

ORIGINAL QA ISSUE:
{violation.message}

{guidance_prompt}

RE-QA FOCUS AREAS:
1. Security vulnerability assessment
2. Code quality metrics
3. Compliance verification
4. Risk assessment
5. Comprehensive recommendations

Please provide a thorough QA analysis addressing these areas.
"""

        return ActionResult(
            success=True,
            action_type=ActionType.RE_QA,
            retry_prompt=qa_prompt,
            metadata={
                "qa_scope": "comprehensive",
                "focus_areas": ["security", "quality", "compliance", "risk"],
            },
        )
    #
    # ========================================================================
    # Async Method 2.6.25: _action_doc
    # ========================================================================
    #
    async def _action_doc(
        self,
        violation: RuleViolation,
        content: str,
        agent_name: str,
        task: str,
        context: Optional[Dict],
    ) -> ActionResult:
        """Execute DOC action - enhance documentation"""

        guidance_prompt = self._construct_guidance_prompt(violation, "doc")

        doc_prompt = f"""
DOCUMENTATION ENHANCEMENT REQUIRED:

DOCUMENTATION ISSUE:
{violation.message}

{guidance_prompt}

DOCUMENTATION REQUIREMENTS:
1. Complete API documentation
2. Usage examples
3. Parameter descriptions
4. Return value specifications
5. Error handling documentation

Please enhance the documentation to meet these requirements.
"""

        return ActionResult(
            success=True,
            action_type=ActionType.DOC,
            retry_prompt=doc_prompt,
            metadata={
                "doc_scope": "comprehensive",
                "requirements": ["api", "examples", "parameters", "returns", "errors"],
            },
        )
    #
    # ========================================================================
    # Async Method 2.6.26: _action_plan
    # ========================================================================
    #
    async def _action_plan(
        self,
        violation: RuleViolation,
        content: str,
        agent_name: str,
        task: str,
        context: Optional[Dict],
    ) -> ActionResult:
        """Execute PLAN action - create comprehensive plan"""

        guidance_prompt = self._construct_guidance_prompt(violation, "plan")

        plan_prompt = f"""
COMPREHENSIVE PLANNING REQUIRED:

PLANNING ISSUE:
{violation.message}

{guidance_prompt}

PLANNING REQUIREMENTS:
1. Clear objectives and scope
2. Realistic timeline with milestones
3. Resource requirements
4. Risk assessment and mitigation
5. Deliverables specification

Please create a comprehensive plan addressing these areas.
"""

        return ActionResult(
            success=True,
            action_type=ActionType.PLAN,
            retry_prompt=plan_prompt,
            metadata={"plan_scope": "comprehensive", "requirements": ["objectives", "timeline", "resources", "risks", "deliverables"]}
        )
    #
    # ========================================================================
    # Async Method 2.6.27: _action_update
    # ========================================================================
    #
    async def _action_update(self, violation: RuleViolation, content: str,
                           agent_name: str, task: str, context: Optional[Dict]) -> ActionResult:
        """Execute UPDATE action - incremental improvements"""

        # Construct guidance prompt for update action
        guidance_prompt = self._construct_guidance_prompt(violation, "update")

        # Build update-specific prompt with clear scope
        update_prompt = f"""
INCREMENTAL UPDATE REQUIRED:

UPDATE ISSUE:
{violation.message}

{guidance_prompt}

UPDATE SCOPE:
- Add missing elements
- Enhance existing content
- Maintain current structure
- Preserve working functionality

Please update the content to address the identified issues while preserving existing functionality.
"""

        return ActionResult(
            success=True,
            action_type=ActionType.UPDATE,
            retry_prompt=update_prompt,
            metadata={"update_scope": "incremental", "preserve_existing": True}
        )
    #
    # ========================================================================
    # Async Method 2.6.28: _action_flag
    # ========================================================================
    #
    async def _action_flag(self, violation: RuleViolation, content: str,
                         agent_name: str, task: str, context: Optional[Dict]) -> ActionResult:
        """Execute FLAG action - mark for review"""

        # Create flag message for manual review
        flag_message = f"""
[FLAGGED FOR REVIEW]

Rule Violation: {violation.rule_name}
Severity: {violation.severity.value}
Issue: {violation.message}

This output has been flagged for manual review due to rule violation.
Please review and address the identified issue before proceeding.
"""

        return ActionResult(
            success=True,
            action_type=ActionType.FLAG,
            new_content=content + "\n\n" + flag_message,
            metadata={"flag_reason": violation.message, "review_required": True}
        )
    #
    # ========================================================================
    # Async Method 2.6.29: _apply_template_modifications
    # ========================================================================
    #
    async def _apply_template_modifications(self, content: str, modifications: List[Dict],
                                          agent_name: str) -> str:
        """Apply dynamic template modifications (Mechanism C)"""

        # Check if config manager is available
        if not self._config_manager:
            logger.warning("ConfigManager not available for template modifications")
            return f"modified_{agent_name}_template"

        # Get base template for modifications
        base_template_name = f"base_{agent_name}_template"
        try:
            base_template = self._config_manager.get_template_content(base_template_name)
            # Check if base template exists
            if not base_template:
                logger.warning(f"Base template {base_template_name} not found")
                return f"modified_{agent_name}_template"

            modified_template = base_template

            # Apply modifications in order
            for mod in modifications:
                mod_type = mod.get("type")
                # Handle different modification types
                if not mod_type:
                    # Handle legacy format modifications
                    if "add_before" in mod:
                        target = mod["add_before"]
                        content_to_add = mod["content"]
                        modified_template = modified_template.replace(target, f"{content_to_add}\n{target}")
                    elif "add_after" in mod:
                        target = mod["add_after"]
                        content_to_add = mod["content"]
                        modified_template = modified_template.replace(target, f"{target}\n{content_to_add}")
                    elif "replace" in mod:
                        old_text = mod["replace"]
                        new_text = mod["with"]
                        modified_template = modified_template.replace(old_text, new_text)

            # Cache the modified template for reuse
            modified_template_name = f"modified_{agent_name}_{hash(str(modifications))}"
            self._template_cache[modified_template_name] = modified_template

            logger.debug(f"Applied {len(modifications)} template modifications")
            return modified_template_name

        except Exception as e:
            logger.error(f"Error applying template modifications: {e}")
            return f"modified_{agent_name}_template"
    #
    # ========================================================================
    # Async Method 2.6.30: _apply_template_chain
    # ========================================================================
    #
    async def _apply_template_chain(self, template_chain: List[str], agent_name: str) -> str:
        """Apply template inheritance chain (Mechanism D)"""

        # Check if config manager is available
        if not self._config_manager:
            logger.warning("ConfigManager not available for template chain")
            return f"chained_{agent_name}_template"

        try:
            final_template = ""

            # Process each template in the chain
            for template_name in template_chain:
                template_content = self._config_manager.get_template_content(template_name)
                # Add template content if found
                if template_content:
                    final_template += template_content + "\n\n"
                else:
                    logger.warning(f"Template {template_name} not found in chain")

            # Check if any templates were successfully loaded
            if final_template:
                # Cache the chained template for performance
                chained_template_name = f"chained_{agent_name}_{hash(str(template_chain))}"
                self._template_cache[chained_template_name] = final_template.strip()

                logger.debug(f"Applied template chain with {len(template_chain)} templates")
                return chained_template_name
            else:
                logger.error("No valid templates found in chain")
                return f"chained_{agent_name}_template"

        except Exception as e:
            logger.error(f"Error applying template chain: {e}")
            return f"chained_{agent_name}_template"
    #
    # ========================================================================
    # Method 2.6.31: _construct_guidance_prompt
    # ========================================================================
    #
    def _construct_guidance_prompt(self, violation: RuleViolation, action_context: str) -> str:
        """Construct LLM guidance prompt based on rule violation and action"""

        # Check if guidance is available
        if not violation.llm_guidance:
            return f"Please address the rule violation: {violation.message}"

        guidance = violation.llm_guidance
        prompt_parts = []

        # Add primary guidance if available
        primary = guidance.get("primary", "")
        if primary:
            prompt_parts.append(f"GUIDANCE: {primary}")

        # Add examples if available
        examples = guidance.get("examples", [])
        if examples:
            prompt_parts.append("\nEXAMPLES:")
            # Iterate through examples with numbering
            for i, example in enumerate(examples, 1):
                prompt_parts.append(f"{i}. {example}")

        # Add variations based on action context
        variations = guidance.get("variations", [])
        if variations:
            prompt_parts.append("\nALTERNATIVE APPROACHES:")
            # Iterate through variations with numbering
            for i, variation in enumerate(variations, 1):
                prompt_parts.append(f"{i}. {variation}")

        # Add action-specific additions based on context
        if action_context == "retry_with_constraint":
            prompt_parts.append(f"\nCONSTRAINT: Ensure your response addresses: {violation.message}")
        elif action_context == "template_override":
            prompt_parts.append(f"\nTEMPLATE NOTE: A specialized template will be used for this response.")
        elif action_context == "reject":
            prompt_parts.append(f"\nREJECTION REASON: {violation.message}")

        return "\n".join(prompt_parts)
    #
    # ========================================================================
    # Method 2.6.32: _build_constraint_prompt
    # ========================================================================
    #
    def _build_constraint_prompt(self, violation: RuleViolation, content: str) -> str:
        """Build specific constraints based on violation type"""

        constraints = []

        # Build constraints based on rule type
        if violation.rule_type == "content_check":
            # Check if this is a length-related violation
            if "length" in violation.message.lower():
                constraints.append("- Provide a more detailed and comprehensive response")
                constraints.append("- Include specific examples and explanations")
                constraints.append("- Ensure adequate coverage of all relevant aspects")

        elif violation.rule_type == "code_quality_check":
            constraints.append("- Include comprehensive docstrings for all functions")
            constraints.append("- Follow proper code formatting standards")
            constraints.append("- Add appropriate comments for complex logic")
            constraints.append("- Ensure code follows best practices")

        elif violation.rule_type == "output_structure_check":
            required_sections = getattr(violation, 'required_sections', [])
            # Try to extract required sections from the original rule if available
            if hasattr(violation, 'violation_context') and violation.violation_context:
                pass  # Future enhancement: extract from context
            constraints.append("- Include all required sections in your response")
            constraints.append("- Use clear headings and organization")
            constraints.append("- Ensure logical flow and structure")

        elif violation.rule_type == "security_check":
            constraints.append("- Handle all sensitive data securely")
            constraints.append("- Never expose credentials or secrets")
            constraints.append("- Follow security best practices")
            constraints.append("- Include proper input validation")

        # Fallback constraint if no specific ones apply
        if not constraints:
            constraints.append(f"- Address the specific issue: {violation.message}")

        return "\n".join(constraints)
    #
    # ========================================================================
    # Method 2.6.33: _apply_formatting_fixes
    # ========================================================================
    #
    def _apply_formatting_fixes(self, content: str) -> str:
        """Apply automatic formatting fixes"""

        lines = content.split('\n')
        fixed_lines = []

        # Process each line for formatting issues
        for line in lines:
            # Initialize with current line
            fixed_line = line

            # Fix excessive line length (basic wrapping)
            if len(line) > 79 and not line.strip().startswith('#'):
                # Simple line breaking for long lines
                if ' ' in line and not line.strip().startswith('"""'):
                    words = line.split()
                    current_line = ""
                    # Build line word by word within limit
                    for word in words:
                        if len(current_line + " " + word) <= 79:
                            current_line += (" " + word) if current_line else word
                        else:
                            # Add completed line and start new one
                            if current_line:
                                fixed_lines.append(current_line)
                            current_line = word
                    # Add remaining words as final line
                    if current_line:
                        fixed_line = current_line

            # Fix indentation issues (basic check)
            if line.strip() and not line.startswith(' ') and not line.startswith('\t'):
                # This is a very basic check - in practice, proper AST parsing would be needed
                pass

            fixed_lines.append(fixed_line)

        return '\n'.join(fixed_lines)
    #
    # ========================================================================
    # Method 2.6.34: _apply_profanity_fixes
    # ========================================================================
    #
    def _apply_profanity_fixes(self, content: str) -> str:
        """Apply automatic profanity fixes"""

        # Define profanity replacement mappings
        profanity_replacements = {
            'damn': 'unfortunate',
            'hell': 'trouble',
            'crap': 'poor quality',
            'stupid': 'suboptimal',
            'idiot': 'inexperienced'
        }

        fixed_content = content
        # Apply each replacement with case-insensitive matching
        for profanity, replacement in profanity_replacements.items():
            # Case-insensitive replacement using regex
            import re
            pattern = re.compile(re.escape(profanity), re.IGNORECASE)
            fixed_content = pattern.sub(replacement, fixed_content)

        return fixed_content
    #
    # ========================================================================
    # Method 2.6.35: reload_rules
    # ========================================================================
    #
    def reload_rules(self, agent_configs: Optional[Dict[str, Any]] = None) -> bool:
        """Reload rules from configuration files"""
        try:
            # Thread-safe rule reloading
            with self._lock:
                self._agent_rules.clear()
                self._global_rules.clear()
                self._template_cache.clear()
                self._load_rules(agent_configs)
                self._load_processing_config()
            logger.info("Rules reloaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to reload rules: {e}")
            return False
    #
    # ========================================================================
    # Method 2.6.36: get_rule_statistics
    # ========================================================================
    #
    def get_rule_statistics(self) -> Dict[str, Any]:
        """Get statistics about loaded rules"""
        # Thread-safe statistics generation
        with self._lock:
            stats = {
                "global_rules_count": len(self._global_rules),
                "agent_rules_count": {agent: len(rules) for agent, rules in self._agent_rules.items()},
                "total_agent_rules": sum(len(rules) for rules in self._agent_rules.values()),
                "template_cache_size": len(self._template_cache),
                "supported_actions": [action.value for action in ActionType],
                "processing_config": self._processing_config.copy()
            }
        return stats
    #
    # ========================================================================
    # Method 2.6.37: validate_rule_configuration
    # ========================================================================
    #
    def validate_rule_configuration(self) -> List[str]:
        """Validate the current rule configuration and return any issues"""
        issues = []

        # Thread-safe validation
        with self._lock:
            # Check global rules for issues
            for rule in self._global_rules:
                rule_issues = self._validate_individual_rule(rule, "global")
                issues.extend(rule_issues)

            # Check agent rules for issues
            for agent_name, rules in self._agent_rules.items():
                for rule in rules:
                    rule_issues = self._validate_individual_rule(rule, agent_name)
                    issues.extend(rule_issues)

        return issues
    #
    # ========================================================================
    # Method 2.6.38: _validate_individual_rule
    # ========================================================================
    #
    def _validate_individual_rule(self, rule: Dict[str, Any], context: str) -> List[str]:
        """Validate an individual rule structure"""
        issues = []
        rule_id = rule.get('id', 'unknown')

        # Check required fields are present
        required_fields = ['id', 'rule_name', 'type', 'action', 'severity', 'message']
        for field in required_fields:
            if field not in rule:
                issues.append(f"Rule {rule_id} ({context}): Missing required field '{field}'")

        # Validate action type is supported
        action = rule.get('action')
        if action and action not in [a.value for a in ActionType]:
            issues.append(f"Rule {rule_id} ({context}): Invalid action type '{action}'")

        # Validate severity level is supported
        severity = rule.get('severity')
        if severity and severity not in [s.value for s in SeverityLevel]:
            issues.append(f"Rule {rule_id} ({context}): Invalid severity level '{severity}'")

        # Validate LLM guidance structure if present
        llm_guidance = rule.get('llm_guidance')
        if llm_guidance and not isinstance(llm_guidance, dict):
            issues.append(f"Rule {rule_id} ({context}): llm_guidance must be a dictionary")

        return issues
    #
    # ========================================================================
    # Method 2.6.39: get_template_cache_info
    # ========================================================================
    #
    def get_template_cache_info(self) -> Dict[str, Any]:
        """Get information about the template cache"""
        # Thread-safe cache information retrieval
        with self._lock:
            return {
                "cache_size": len(self._template_cache),
                "cached_templates": list(self._template_cache.keys()),
                "cache_enabled": self._processing_config.get("template_cache_enabled", True)
            }
    #
    # ========================================================================
    # Method 2.6.40: clear_template_cache
    # ========================================================================
    #
    def clear_template_cache(self) -> None:
        """Clear the template cache"""
        # Thread-safe cache clearing
        with self._lock:
            self._template_cache.clear()
        logger.info("Template cache cleared")
    #
    # ========================================================================
    # Method 2.6.41: inject_project_context
    # ========================================================================
    #
    def inject_project_context(self, base_prompt: str, agent_name: str,
                             task: str, context: Optional[Dict] = None) -> str:
        """Inject project context into prompts (following steipete/agent-rules pattern)"""

        context_parts = []

        # Add working directory context if available
        if context and 'working_directory' in context:
            context_parts.append(f"Your work folder is {context['working_directory']}")

        # Add project context if available
        if context and 'project_name' in context:
            context_parts.append(f"Project: {context['project_name']}")

        # Add agent context
        context_parts.append(f"Agent: {agent_name}")
        context_parts.append(f"Task: {task}")

        # Add file context if available
        if context and 'current_file' in context:
            context_parts.append(f"Current file: {context['current_file']}")

        # Combine context with prompt
        if context_parts:
            context_header = "\n".join(context_parts)
            return f"{context_header}\n\n{base_prompt}"

        return base_prompt
    #
    # ========================================================================
    # Method 2.6.42: get_applicable_rules_for_file
    # ========================================================================
    #
    async def get_applicable_rules_for_file(self, file_path: str, agent_name: str) -> List[Dict[str, Any]]:
        """Get rules applicable to a specific file (supports glob patterns)"""

        applicable_rules = []
        all_rules = self.get_agent_rules(agent_name)

        # Check each rule for file pattern matching
        for rule in all_rules:
            # Check if rule has file glob patterns
            globs = rule.get('globs', [])
            if globs:
                import fnmatch
                # Check against each glob pattern
                for glob_pattern in globs:
                    if fnmatch.fnmatch(file_path, glob_pattern):
                        applicable_rules.append(rule)
                        break
            else:
                # No glob patterns, rule applies to all files
                applicable_rules.append(rule)

        return applicable_rules
    #
    # ========================================================================
    # Method 2.6.43: get_processing_config
    # ========================================================================
    #
    def get_processing_config(self) -> Dict[str, Any]:
        """Get the current processing configuration"""
        # Thread-safe configuration retrieval
        with self._lock:
            return self._processing_config.copy()

    # ========================================================================
    # Method 2.6.44: update_processing_config
    # ========================================================================
    #
    def update_processing_config(self, new_config: Dict[str, Any]) -> bool:
        """Update the processing configuration"""
        try:
            # Thread-safe configuration update
            with self._lock:
                self._processing_config.update(new_config)
            logger.info("Processing configuration updated")
            return True
        except Exception as e:
            logger.error(f"Failed to update processing configuration: {e}")
            return False
#
#
## END rule_engine.py
