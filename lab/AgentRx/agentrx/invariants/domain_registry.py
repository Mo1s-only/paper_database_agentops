#!/usr/bin/env python3
"""
Domain registry for invariant generation.

Centralizes all domain-specific configuration so that adding a new domain
requires changes in exactly ONE place (this file) plus an IR converter
function in ir/trajectory_ir.py.

Usage:
    from agentrx.invariants.domain_registry import DOMAIN_REGISTRY, get_domain_config, list_domains

    cfg = get_domain_config("tau")
    print(cfg.tools_list)
    print(cfg.tools_structure)
    ir_fn = cfg.ir_converter
    examples = cfg.examples_block
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

# Lazy-import IR converters to avoid circular imports at module load time.
# They are resolved on first access via the ir_converter_name string.
_IR_CONVERTERS: Dict[str, Callable] = {}


def _get_ir_converter(name: str) -> Callable:
    """Lazily import and cache an IR converter function by name."""
    if name not in _IR_CONVERTERS:
        from agentrx.ir.trajectory_ir import tau_bench_ir, flash_ir, magentic_ir, llm_ir  # noqa: F811
        _IR_CONVERTERS.update({
            "tau_bench_ir": tau_bench_ir,
            "flash_ir": flash_ir,
            "magentic_ir": magentic_ir,
            "llm_ir": llm_ir,
        })
    fn = _IR_CONVERTERS.get(name)
    if fn is None:
        raise ValueError(
            f"Unknown IR converter '{name}'. "
            f"Registered converters: {list(_IR_CONVERTERS.keys())}"
        )
    return fn


@dataclass
class DomainConfig:
    """All domain-specific wiring for invariant generation."""

    # Human-readable domain name
    name: str

    # The function name in ir.trajectory_ir that converts raw trajectories
    # into the standard IR format.  Resolved lazily via _get_ir_converter().
    ir_converter_name: str

    # Tools / agents available in this domain
    tools_list: List[str] = field(default_factory=list)
    tools_structure: Optional[Dict[str, Any]] = None

    # Domain-specific invariant examples block (injected into prompts).
    # Empty string → no examples.
    examples_block: str = ""

    # Default policy document path (relative to project root).
    # None → caller must supply one explicitly.
    default_policy_path: Optional[str] = None

    # ---- derived helpers -------------------------------------------------------

    @property
    def ir_converter(self) -> Callable:
        """Return the actual IR converter function."""
        return _get_ir_converter(self.ir_converter_name)


# ---------------------------------------------------------------------------
# TAU-BENCH (RETAIL)
# ---------------------------------------------------------------------------
TAU_RETAIL_TOOLS_LIST = [
    "find_user_id_by_email",
    "find_user_id_by_name_zip",
    "list_all_product_types",
    "get_order_details",
    "get_product_details",
    "get_user_details",
    "cancel_pending_order",
    "exchange_delivered_order_items",
    "modify_pending_order_address",
    "modify_pending_order_items",
    "modify_pending_order_payment",
    "modify_user_address",
    "return_delivered_order_items",
]

TAU_RETAIL_TOOLS_STRUCTURE = {
    "protocol": {
        "event_types": ["assistant", "tool"],
        "common_fields": ["role", "content"],
        "call_pattern": "Assistant makes tool_calls, system returns tool results"
    },
    "tools": {
        "find_user_id_by_email": {
            "capability": "Locate user ID by email address for authentication",
            "inputs": {"email": "string"},
            "outputs": {"user_id": "string"}
        },
        "find_user_id_by_name_zip": {
            "capability": "Locate user ID by first name, last name, and zip code for authentication",
            "inputs": {"first_name": "string", "last_name": "string", "zip": "string"},
            "outputs": {"user_id": "string"}
        },
        "list_all_product_types": {
            "capability": "List all available product types and their IDs",
            "inputs": {},
            "outputs": {"products": "dict mapping product names to IDs"}
        },
        "get_order_details": {
            "capability": "Retrieve detailed information about a specific order",
            "inputs": {"order_id": "string"},
            "outputs": {"order_info": "dict with status, items, payment, address, dates"}
        },
        "get_product_details": {
            "capability": "Get details about a specific product including available items",
            "inputs": {"product_id": "string"},
            "outputs": {"product_info": "dict with items, options, prices"}
        },
        "get_user_details": {
            "capability": "Retrieve user profile information",
            "inputs": {"user_id": "string"},
            "outputs": {"user_info": "dict with email, address, payment methods"}
        },
        "cancel_pending_order": {
            "capability": "Cancel an order that is in pending status",
            "inputs": {"order_id": "string", "reason": "string ('no longer needed' or 'ordered by mistake')"},
            "outputs": {"confirmation": "dict with cancellation details"}
        },
        "exchange_delivered_order_items": {
            "capability": "Exchange items from a delivered order (can only be called once per order)",
            "inputs": {
                "order_id": "string",
                "item_ids": "list of strings",
                "new_item_ids": "list of strings",
                "reason": "string"
            },
            "outputs": {"confirmation": "dict with exchange details"}
        },
        "modify_pending_order_address": {
            "capability": "Modify delivery address for a pending order",
            "inputs": {"order_id": "string", "new_address": "string"},
            "outputs": {"confirmation": "dict with updated address"}
        },
        "modify_pending_order_items": {
            "capability": "Modify items in a pending order (can only be called once per order)",
            "inputs": {
                "order_id": "string",
                "item_ids_to_remove": "list of strings",
                "item_ids_to_add": "list of strings"
            },
            "outputs": {"confirmation": "dict with updated items"}
        },
        "modify_pending_order_payment": {
            "capability": "Modify payment method for a pending order",
            "inputs": {"order_id": "string", "new_payment_method": "string"},
            "outputs": {"confirmation": "dict with updated payment"}
        },
        "modify_user_address": {
            "capability": "Update user's default address",
            "inputs": {"user_id": "string", "new_address": "string"},
            "outputs": {"confirmation": "dict with updated address"}
        },
        "return_delivered_order_items": {
            "capability": "Return items from a delivered order",
            "inputs": {
                "order_id": "string",
                "item_ids": "list of strings",
                "reason": "string"
            },
            "outputs": {"confirmation": "dict with return details"}
        }
    }
}

EXAMPLES_BLOCK_TAU_RETAIL = r"""
================================================================================================
EXAMPLES OF INVARIANTS YOU MUST INCLUDE
================================================================================================
You MUST include invariant templates that cover each of these retail domain requirements:

(1) User authentication must happen first (TEMPORAL)
- Before any order operations or product listing, user must be authenticated via find_user_id_by_email or find_user_id_by_name_zip
- This applies to: list_all_product_types, get_order_details, get_user_details, get_product_details, cancel_pending_order, exchange_delivered_order_items, return_delivered_order_items, modify_pending_order_*, modify_user_address
- Even if user provides user_id, authentication via email/name+zip is required
- IMPORTANT: Use source_regex to match all these tools: "list_all_product_types|get_order_details|get_user_details|get_product_details|cancel_pending_order|exchange_delivered_order_items|return_delivered_order_items|modify_pending_order_.*|modify_user_address"

(2) Order status validation before actions (PROTOCOL/CAPABILITY)
- cancel_pending_order can only be called if order status is 'pending'
- exchange_delivered_order_items can only be called if order status is 'delivered'
- return_delivered_order_items can only be called if order status is 'delivered'
- modify_pending_order_* tools can only be called if order status is 'pending'
- IMPORTANT: For each of these, set source_regex to the specific tool name (e.g., "cancel_pending_order")
- This ensures the check only triggers when that specific tool is called

(3) Cancellation reason validation (SCHEMA)
- cancel_pending_order reason must be either 'no longer needed' or 'ordered by mistake'

(4) Single-use modification tools (PROTOCOL)
- exchange_delivered_order_items can only be called once per order_id
- modify_pending_order_items can only be called once per order_id

(5) User confirmation for consequential actions (TEMPORAL)
- Before calling any database-write tools (cancel, modify, return, exchange),
  there must be evidence of explicit user confirmation (e.g., "yes")
- This is a semantic check requiring nl_check
- IMPORTANT: Use source_regex to match write-action tools: "cancel_pending_order|exchange_delivered_order_items|return_delivered_order_items|modify_pending_order_.*|modify_user_address"
- Rubric should have self-contained criteria like:
  * "A user message contains explicit affirmation keywords (yes/confirm/proceed/ok)"
  * "An assistant content message describes the specific action type (cancel/modify/exchange/return/address update) and includes the relevant identifier (order_id or user_id)"
  * "The identifier (order_id or user_id) mentioned in the assistant's description matches the identifier in the current tool call arguments"
- Focus_steps should specify WHERE to look:
  * "The user message 1 step back for confirmation keywords"
  * "The assistant message 2 steps back for action description and identifier"
  * "The current tool call arguments for the identifier to verify consistency"

(6) One user per conversation (PROTOCOL)
- Only one user_id should be authenticated per conversation
- Agent must deny requests related to other users

(7) No information invention or misinterpretation (PROVENANCE)
- Agent should not make up information not provided by user or tools
- Agent should not misinterpret or incorrectly process information from tool outputs
- Response content must be grounded in tool outputs AND correctly interpreted
- This is a semantic check requiring nl_check
- IMPORTANT: Trigger only on assistant events with content (no tool_calls)
- Use source_regex "*" for assistant messages, but check content is not null
- Rubric should have self-contained criteria covering BOTH invention AND misinterpretation:

  INVENTION checks (making up data):
  * "If assistant mentions a specific order_id, that order_id appears in a prior get_order_details result"
  * "If assistant states a status value, that status appears in a prior tool result"
  * "If assistant mentions a product_id or item_id, that ID appears in a prior tool result"
  * "If assistant mentions a currency amount, it either: (a) appears exactly in a prior tool result, OR (b) is clearly described as a calculated value (e.g., 'refund of $X', 'difference of $Y', 'total will be $Z') based on amounts that DO appear in prior tool results AND the calculation is mathematically correct"
  * "If assistant mentions a date/timeline, it either appears in prior tool results or is a general policy statement"

  MISINTERPRETATION checks (wrong processing of existing data):
  * "If assistant mentions counts or quantities (e.g., 'you have 3 items', 'there are 2 orders'), verify the count matches the actual number in the tool result by counting array elements or list items"
  * "If assistant summarizes order items or products, verify all mentioned items actually exist in the order and no items are omitted or added"
  * "If assistant states aggregated information (e.g., 'total price', 'combined shipping'), verify the aggregation is computed correctly from the source data"
  * "If assistant describes item options or specifications (e.g., 'color: red', 'size: large'), verify those exact option values appear in the tool result for that item"
  * "If assistant mentions shipping/tracking information, verify it matches the tracking_id and related fields in the fulfillments array"

  IMPORTANT:
  - Break into specific fact types - avoid criteria like "all facts are grounded"
  - Calculated amounts (refunds, differences, totals) are acceptable if base amounts exist and arithmetic is correct
  - Counts and aggregations must be verified against actual data in tool results
  - Item details must match exactly - no approximations or incorrect mappings

(8) Tool call atomicity (PROTOCOL)
- Agent should make at most one tool call at a time
- If making tool call, should not respond to user simultaneously
"""


# ---------------------------------------------------------------------------
# FLASH (INCIDENT MANAGEMENT)
# ---------------------------------------------------------------------------
FLASH_TOOLS_LIST = [
    "Orchestrator",
    "KustoAgent",
    "IncidentAgent",
    "Executor",
    "GeneralAssistant",
    "Coder"
]

FLASH_TOOLS_STRUCTURE = {
    "protocol": {
        "event_types": ["OrchestrationEvent", "LLMCallEvent"],
        "common_fields": ["timestamp", "source", "message", "type"],
        "call_pattern": "Orchestrator delegates via source like: 'Orchestrator (-> <AgentName>)'"
    },
    "agents": {
        "KustoAgent": {
            "capability": "Execute a provided Kusto query (must already exist in the plan).",
            "inputs": {"kusto_query": "string"},
            "outputs": {"result": "pandas dataframe"}
        },
        "IncidentAgent": {
            "capability": "Query/return incident descriptions only (no extra troubleshooting).",
            "inputs": {"incident_id": "string"},
            "outputs": {"incident_description": "string"}
        },
        "Executor": {
            "capability": "Run user-provided code blocks only (python/sh).",
            "inputs": {"python": "string", "sh": "string"},
            "outputs": {"stdout": "string", "stderr": "string"}
        },
        "GeneralAssistant": {
            "capability": "Summarize, explain, and draft responses based on evidence in the trace.",
            "inputs": {"message": "string"},
            "outputs": {"message": "string"}
        },
        "Orchestrator": {
            "capability": "Follow the plan steps; emit ledger JSON with required keys; pick next speaker.",
            "ledger_schema": [
                "is_step_finished{reason,answer}",
                "next_step{reason,answer}",
                "is_in_loop{reason,answer}",
                "is_progress_being_made{reason,answer}",
                "next_speaker{reason,answer}",
                "instruction_or_question{reason,answer}",
            ]
        }
    }
}

EXAMPLES_BLOCK_FLASH_INCIDENT = r"""
================================================================================================
EXAMPLES OF INVARIANTS YOU MUST INCLUDE (FLASH / INCIDENT MANAGEMENT DOMAIN)
================================================================================================
You MUST include invariant templates that cover each of these FLASH incident-domain requirements.
These invariants should be plan-relative (derived from the plan text in the trajectory), NOT HARD-CODED TO ONE SPECIFIC PLAN OR KUSTO QUERY.
DO NOT HARD-CODE ANY PLAN-SPECIFIC DETAILS; RATHER, WRITE GENERAL INVARIANTS THAT CAN APPLY TO ANY PLAN/QUERY IN THE FLASH INCIDENT DOMAIN.

(1) Plan step sequence must be followed (TEMPORAL)
- Orchestrator ledger transitions must follow the plan: Step-1 -> Step-2 -> ... -> FINAL_ANSWER -> DONE
- Allow only transitions explicitly listed in "next steps" in the plan text.
- Trigger: role_name=Orchestrator

(2) Field extraction integrity: extracted IDs must match incident description (SCHEMA/PROTOCOL)
- Any extracted identifiers (team name, nodeID, container IDs) must come from the user's incident description.
- No hallucinated IDs introduced later.

(3) Kusto query MUST match the plan template (SCHEMA/PROTOCOL)
- When the plan provides an explicit query block template, the KustoAgent query MUST be structurally derived from it.
- Fail if the query is missing a required anchor from the plan (e.g., missing cluster()/database()).

(4) Multi-ID query must preserve per-ID attribution (PROTOCOL, PRE_TOOL)
- If Orchestrator asks to run the plan query "for each container ID" but KustoAgent uses "in (...)" to batch,
  then the query MUST preserve attribution by including ContainerId in the output.
- Rationale: otherwise results cannot be mapped back to each requested ID.

(5) Portal link correctness when ArmId exists (SCHEMA, POST_TOOL)
- If an ArmId exists, the generated portal link MUST be:
  "https://ms.portal.azure.com/#@microsoft.onmicrosoft.com/resource" + <ArmId>
- If ArmId is null, the ONLY allowed link is "https://ms.portal.azure.com/#home".
- Fail if the link prefix is wrong, the ArmId is malformed, or #home is used when ArmId is present.

(6) Orchestrator must not end with "No agent selected" when blocked (PROTOCOL)
- If the workflow is blocked and requires user input, Orchestrator MUST select the user as next speaker and
  emit a clear instruction_or_question (with concrete fields requested).
- Fail if the run terminates due to orchestration error instead of handing off to the user.

(7) FINAL_ANSWER must exist and be last (TEMPORAL)
- If the plan includes a FINAL_ANSWER step, then:
  * Orchestrator must eventually set next_step to FINAL_ANSWER,
  * a final assistant message must be emitted after that transition,
  * and there must be a termination to DONE (not "No agent selected").
- Trigger: role_name=Orchestrator, content_regex="FINAL_ANSWER|termination condition|next_step"
- Fail if run ends without reaching FINAL_ANSWER when the plan expects it,
  OR reaches FINAL_ANSWER but does not emit a final answer message.

(8) Tool-call atomicity (PROTOCOL)
- At most one tool delegation per LLM event/step (e.g., Orchestrator should not call IncidentAgent and KustoAgent in the same step).
- Trigger: any step containing "Orchestrator (-> X)"
- Fail if more than one distinct tool delegation appears in the same step/event.
"""


# ---------------------------------------------------------------------------
# MAGENTIC-ONE
# ---------------------------------------------------------------------------
MAGENTIC_ONE_TOOLS_LIST = [
    "Orchestrator",
    "WebSurfer",
    "ComputerTerminal",
    "FileSurfer",
    "Assistant",
]

MAGENTIC_ONE_TOOLS_STRUCTURE = {
    "protocol": {
        "event_types": [
            "human",
            "Assistant",
            "Orchestrator",
            "WebSurfer",
            "ComputerTerminal",
            "FileSurfer",
        ],
        "common_fields": ["role", "content"],
        "call_pattern": (
            "Events are a flat list of {role, content}. Orchestrator coordinates the run.\n"
            "- Planning/ledger typically appears as role like 'Orchestrator (thought)'.\n"
            "- Delegation appears as role like 'Orchestrator (-> WebSurfer)'.\n"
            "- Agent responses appear as role exactly 'WebSurfer', 'ComputerTerminal', etc.\n"
            "- Termination can appear as 'Orchestrator (termination condition)'."
        ),
        "notes": [
            "The ledger is often embedded as JSON text inside content.",
            "WebSurfer outputs may include 'I typed ...', 'I clicked ...', and 'Here is a screenshot of ...'.",
        ],
    },
    "agents": {
        "Orchestrator": {
            "capability": "Plans, emits ledger JSON, delegates tasks to other agents, and decides termination.",
            "inputs": {"request": "string", "history": "list of {role, content}"},
            "outputs": {"ledger_json": "string (JSON blob embedded in content)", "delegation": "string"},
            "role_patterns": [
                "Orchestrator (thought)",
                "Orchestrator (-> <AgentName>)",
                "Orchestrator (termination condition)",
            ],
        },
        "WebSurfer": {
            "capability": "Performs web search/browsing steps and reports evidence (snippets/screenshots/URLs).",
            "inputs": {"query_or_instruction": "string"},
            "outputs": {
                "narration": "string",
                "evidence": "string (may include screenshot descriptions, extracted text/OCR)",
            },
            "evidence_markers": [
                "I typed",
                "I clicked",
                "Here is a screenshot of",
                "The viewport shows",
                "Automatic OCR",
                "Search query:",
            ],
        },
        "ComputerTerminal": {
            "capability": "Runs user-provided code blocks only (python/sh).",
            "inputs": {"python": "string", "sh": "string"},
            "outputs": {"stdout": "string", "stderr": "string"},
        },
        "FileSurfer": {
            "capability": "Reads/writes local files and summarizes file content.",
            "inputs": {"path": "string", "operation": "read|list|write"},
            "outputs": {"content": "string", "metadata": "dict"},
        },
        "Assistant": {
            "capability": "General reasoning/summarization and final answer drafting based on evidence in the trace.",
            "inputs": {"message": "string"},
            "outputs": {"message": "string"},
        },
    },
}


# ===========================================================================
# THE REGISTRY
# ===========================================================================
DOMAIN_REGISTRY: Dict[str, DomainConfig] = {
    "tau": DomainConfig(
        name="tau",
        ir_converter_name="tau_bench_ir",
        tools_list=TAU_RETAIL_TOOLS_LIST,
        tools_structure=TAU_RETAIL_TOOLS_STRUCTURE,
        examples_block=EXAMPLES_BLOCK_TAU_RETAIL,
        default_policy_path=os.path.join("data", "policies", "retail_policy.txt"),
    ),
    "flash": DomainConfig(
        name="flash",
        ir_converter_name="flash_ir",
        tools_list=FLASH_TOOLS_LIST,
        tools_structure=FLASH_TOOLS_STRUCTURE,
        examples_block=EXAMPLES_BLOCK_FLASH_INCIDENT,
        default_policy_path=None,  # caller must supply
    ),
    "magentic": DomainConfig(
        name="magentic",
        ir_converter_name="magentic_ir",
        tools_list=MAGENTIC_ONE_TOOLS_LIST,
        tools_structure=MAGENTIC_ONE_TOOLS_STRUCTURE,
        examples_block="",
        default_policy_path=os.path.join("data", "policies", "magentic_policy.txt"),
    ),
}


# ===========================================================================
# PUBLIC API
# ===========================================================================
def list_domains() -> List[str]:
    """Return sorted list of registered domain names."""
    return sorted(DOMAIN_REGISTRY.keys())


def get_domain_config(domain: str) -> DomainConfig:
    """
    Look up domain config.  Raises ValueError for unknown domains.

    To add a new domain:
      1. Define its tools_list, tools_structure, examples_block above.
      2. Add an IR converter function in ir/trajectory_ir.py.
      3. Register both in DOMAIN_REGISTRY.
    """
    cfg = DOMAIN_REGISTRY.get(domain)
    if cfg is None:
        raise ValueError(
            f"Unknown domain '{domain}'. "
            f"Registered domains: {list_domains()}. "
            f"To add a new domain, see instructions in domain_registry.py."
        )
    return cfg


def register_domain(
    domain: str,
    config: Optional[DomainConfig] = None,
    *,
    tools_list: Optional[List[str]] = None,
    tools_structure: Optional[Dict[str, Any]] = None,
    examples_block: str = "",
    default_policy_path: Optional[str] = None,
    ir_converter_name: str = "llm_ir",
) -> DomainConfig:
    """
    Register a new domain at runtime.

    Either pass a pre-built DomainConfig, or use keyword args to create one.
    If no ir_converter_name is specified, defaults to 'llm_ir' (the LLM-based
    converter that automatically converts any raw trajectory format into
    the standard IR via an LLM call + validate_ir retry loop).

    Returns the DomainConfig that was registered.

    Example:
        register_domain(
            "healthcare",
            tools_list=["check_patient", "prescribe"],
            default_policy_path="data/policies/healthcare.md",
        )
    """
    if config is None:
        config = DomainConfig(
            name=domain,
            ir_converter_name=ir_converter_name,
            tools_list=tools_list or [],
            tools_structure=tools_structure,
            examples_block=examples_block,
            default_policy_path=default_policy_path,
        )
    DOMAIN_REGISTRY[domain] = config
    return config
