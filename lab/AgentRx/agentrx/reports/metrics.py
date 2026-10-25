from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict
import datetime
import uuid
import json
from enum import Enum

@dataclass
class TokenUsage:
    prompt_tokens: int
    output_tokens: int
    total_tokens: int

@dataclass
class TimingInfo:
    start_time: datetime.datetime
    end_time: datetime.datetime
    execution_time_sec: float

class InvariantType(Enum): 
    STATIC = "static" 
    DYNAMIC = "dynamic"

@dataclass
class LLMCallTelemetry:
    tokens: TokenUsage
    time: TimingInfo
    model_name: Optional[str] = None
    instance: Optional[str] = None
    llm_call_id: str = field(init=False)

    def __post_init__(self) -> None:
        self.llm_call_id = str(uuid.uuid4())

@dataclass
class FixAttempt:
    attempt_num: int
    fix_succeeded: bool
    llm_telemetry: LLMCallTelemetry
    error_message: Optional[str] = None

@dataclass
class ExecutionError:
    step_num: int
    invariant_type: InvariantType  # "static" or "dynamic"
    invariant_name: str
    error_message: str
    fix_attempts: list[FixAttempt] = field(default_factory=list)

@dataclass
class ExceptionRaisedDuringSafetyCheck:
    step_num: int
    exception_type: str
    exception_message: str

@dataclass
class Violation:
    step_num: int
    invariant_name: str
    invariant_logic: str
    invariant_type: InvariantType  # "static" or "dynamic"
    primary_step_num: Optional[int] = None

    def __post_init__(self):
        if self.primary_step_num is None:
            self.primary_step_num = self.step_num

@dataclass
class VerificationStepTelemetry:
    step_num: int
    time: TimingInfo
    static_invariants_checked: List[str]
    dynamic_invariants_checked: List[str]
    num_violations: int 
    execution_errors: List[ExecutionError] = field(default_factory=list)
    static_exceptions_raised: List[ExceptionRaisedDuringSafetyCheck] = field(default_factory=list)
    dynamic_exceptions_raised: List[ExceptionRaisedDuringSafetyCheck] = field(default_factory=list)

@dataclass
class StaticInvariantTelemetry:
    llm_call: LLMCallTelemetry
    num_invariants_generated: int
    parsing_time_sec: float  

@dataclass
class DynamicInvariantTelemetry:
    llm_calls_list: List[Dict[str, Any]]  # [{"step_num": i, "llm_call": LLMCallTelemetry}, ...]
    num_invariants_generated: int

    @property
    def total_tokens(self) -> Dict[str, int]:
        """Aggregate token usage across all dynamic invariant LLM calls."""
        totals = {"prompt_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        for call in self.llm_calls_list:
            llm_call = call.get("llm_call")
            if not isinstance(llm_call, LLMCallTelemetry):
                continue
            # tokens is now a TokenUsage dataclass, not a dict
            tokens = llm_call.tokens
            if isinstance(tokens, TokenUsage):
                totals["prompt_tokens"] += tokens.prompt_tokens
                totals["output_tokens"] += tokens.output_tokens
                totals["total_tokens"] += tokens.total_tokens
        return totals

@dataclass
class TelemetryPerTrajectory:
    traj_id: int
    steps: int
    static_invariant: StaticInvariantTelemetry
    dynamic_invariant: DynamicInvariantTelemetry
    verification_step_telemetry_list: List[VerificationStepTelemetry] = field(default_factory=list)
    static_invariant_usage_count: Dict[str, int] = field(default_factory=dict)
    static_invariant_usage_cumulative: Dict[str, int] = field(default_factory=dict)
    execution_errors: List[ExecutionError] = field(default_factory=list)
    violations_list: List[Violation] = field(default_factory=list)
    total_llm_calls: int = 0
    
    @property
    def num_violations(self) -> int:
        return len(self.violations_list)

    @property
    def total_tokens(self) -> Dict[str, int]:
        totals = {"prompt_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        
        # static_tokens is now a TokenUsage dataclass, not a dict
        static_tokens = self.static_invariant.llm_call.tokens
        if isinstance(static_tokens, TokenUsage):
            totals["prompt_tokens"] += static_tokens.prompt_tokens
            totals["output_tokens"] += static_tokens.output_tokens
            totals["total_tokens"] += static_tokens.total_tokens

        dynamic_totals = (
            self.dynamic_invariant.total_tokens
            if isinstance(self.dynamic_invariant, DynamicInvariantTelemetry)
            else {}
        )
        for key in totals:
            totals[key] += dynamic_totals.get(key, 0)
        return totals

    @property
    def total_violations(self) -> int:
        return sum(step.num_violations for step in self.verification_step_telemetry_list)

    @property
    def total_static_exceptions_raised(self) -> int:
        return sum(len(step.static_exceptions_raised) for step in self.verification_step_telemetry_list)

    @property
    def total_dynamic_exceptions_raised(self) -> int:
        return sum(len(step.dynamic_exceptions_raised) for step in self.verification_step_telemetry_list)
    
    @property
    def total_exceptions_raised(self) -> int:
        return self.total_static_exceptions_raised + self.total_dynamic_exceptions_raised
    
    @property
    def total_static_exceptions_raised_by_type(self) -> Dict[str, int]:
        """Return a dictionary mapping static exception type names to their frequency counts."""
        exception_counts: Dict[str, int] = {}
        
        for step in self.verification_step_telemetry_list:
            for exception in step.static_exceptions_raised:
                exception_type = exception.exception_type
                exception_counts[exception_type] = exception_counts.get(exception_type, 0) + 1
        
        return exception_counts
    
    @property
    def total_dynamic_exceptions_raised_by_type(self) -> Dict[str, int]:
        """Return a dictionary mapping dynamic exception type names to their frequency counts."""
        exception_counts: Dict[str, int] = {}
        
        for step in self.verification_step_telemetry_list:
            for exception in step.dynamic_exceptions_raised:
                exception_type = exception.exception_type
                exception_counts[exception_type] = exception_counts.get(exception_type, 0) + 1
        
        return exception_counts

    @property
    def total_exceptions_raised_by_type(self) -> Dict[str, int]:
        """Return a dictionary mapping exception type names to their frequency counts."""
        exception_counts: Dict[str, int] = {}
        
        for step in self.verification_step_telemetry_list:
            # Process static exceptions
            for exception in step.static_exceptions_raised:
                exception_type = exception.exception_type
                exception_counts[exception_type] = exception_counts.get(exception_type, 0) + 1
            
            # Process dynamic exceptions
            for exception in step.dynamic_exceptions_raised:
                exception_type = exception.exception_type
                exception_counts[exception_type] = exception_counts.get(exception_type, 0) + 1
        
        return exception_counts

    @property
    def total_execution_errors(self) -> int:
        return len(self.execution_errors)

    @property
    def total_execution_time_sec(self) -> float:
        """Aggregate execution time in seconds (4 decimal places) from dynamic LLM calls and verification steps."""

        def _extract_duration(time_info) -> float:
            # Handle TimingInfo dataclass
            if isinstance(time_info, TimingInfo):
                return time_info.execution_time_sec
            
            # Handle dict format (for verification steps)
            if isinstance(time_info, dict):
                duration = time_info.get("execution_time_sec")
                if isinstance(duration, datetime.timedelta):
                    return duration.total_seconds()
                if isinstance(duration, (int, float)):
                    return float(duration)
                start = time_info.get("start_time") or time_info.get("start")
                end = time_info.get("end_time") or time_info.get("end")
                if isinstance(start, datetime.datetime) and isinstance(end, datetime.datetime):
                    return max((end - start).total_seconds(), 0.0)
            
            return 0.0

        total_time = 0.0
        for call_info in getattr(self.dynamic_invariant, "llm_calls_list", []):
            llm_call = call_info.get("llm_call")
            if isinstance(llm_call, LLMCallTelemetry):
                total_time += _extract_duration(llm_call.time)

        for step in self.verification_step_telemetry_list:
            total_time += _extract_duration(step.time)

        return total_time

    def to_json(self, indent: Optional[int] = 2) -> str:
        """Serialize telemetry into a JSON string safe for file output."""

        def _convert(value):
            if isinstance(value, datetime.datetime):
                return value.isoformat()
            if isinstance(value, Enum):
                return value.value
            if isinstance(value, dict):
                return {k: _convert(v) for k, v in value.items()}
            if isinstance(value, list):
                return [_convert(v) for v in value]
            return value

        payload = asdict(self)
        payload["num_violations"] = self.num_violations
        payload["total_tokens"] = self.total_tokens
        payload["total_static_exceptions_raised"] = self.total_static_exceptions_raised
        payload["total_dynamic_exceptions_raised"] = self.total_dynamic_exceptions_raised
        payload["total_exceptions_raised"] = self.total_exceptions_raised
        payload["total_static_exceptions_raised_by_type"] = self.total_static_exceptions_raised_by_type
        payload["total_dynamic_exceptions_raised_by_type"] = self.total_dynamic_exceptions_raised_by_type
        payload["total_exceptions_raised_by_type"] = self.total_exceptions_raised_by_type
        payload["total_execution_errors"] = self.total_execution_errors
        payload["total_execution_time_sec"] = self.total_execution_time_sec
        payload = _convert(payload)
        return json.dumps(payload, indent=indent)

    def write_json_to_file(self, file_path: str, indent: Optional[int] = 2) -> None:
        """Persist telemetry to disk in a pretty-printed JSON file."""
        json_text = self.to_json(indent=indent)
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write(json_text)
            if not json_text.endswith("\n"):
                handle.write("\n")