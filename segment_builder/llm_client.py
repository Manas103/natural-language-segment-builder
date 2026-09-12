"""The pluggable LLM-client interface, mirroring
`ontology-grounded-operations-agent/llm_client.py`'s shape: one abstract
interface, a free deterministic implementation used for the large-scale
evals, and a real `claude -p` subprocess implementation exercised on a small,
explicitly-counted live sample.

Every implementation is handed exactly the same two things: the plain-English
request text, and `fields.schema_metadata_for_prompt()` (field names, types,
and enum labels, never a profile row). `tests/test_llm_client.py` asserts this
by construction: it inspects the literal prompt string built for the real
client and the literal arguments passed to the deterministic client, and fails
if any synthetic profile id or attribute value drawn from `store.py` ever
appears in either.
"""
from __future__ import annotations

import abc
import json
import re
import subprocess
from dataclasses import dataclass, field

from segment_builder.fields import schema_metadata_for_prompt
from segment_builder.intent_parser import IntentParseError, parse_request
from segment_builder.tools import BuilderError, SegmentBuilderSession


class LLMClientError(RuntimeError):
    """The client could not produce a finished SegmentDefinition."""


class LLMClient(abc.ABC):
    """A client takes a plain-English request and the schema metadata, drives
    a SegmentBuilderSession through tool calls, and returns the finished
    (but not yet validated) SegmentDefinition dict. No implementation is ever
    given profile data."""

    @abc.abstractmethod
    def build_segment(self, request_text: str) -> dict:
        raise NotImplementedError


def _replay_tree_as_tool_calls(session: SegmentBuilderSession, node: dict) -> int:
    """Turn an already-known predicate tree into the equivalent sequence of
    tool calls. Used by DeterministicIntentParserClient so that the free,
    reproducible path exercises the exact same SegmentBuilderSession API the
    real Claude CLI client drives, rather than shortcutting around it."""
    if node["type"] == "event":
        return session.add_event_predicate(
            node["event_name"], node["operator"], node["count"], node.get("within_days")
        )
    if node["type"] == "attribute":
        return session.add_attribute_predicate(node["field"], node["operator"], node["value"])
    if node["type"] in ("and", "or"):
        child_ids = [_replay_tree_as_tool_calls(session, c) for c in node["children"]]
        return session.combine(node["type"], child_ids)
    if node["type"] == "not":
        child_id = _replay_tree_as_tool_calls(session, node["children"][0])
        return session.negate(child_id)
    raise LLMClientError(f"unknown node type {node['type']!r}")


@dataclass
class DeterministicIntentParserClient(LLMClient):
    """Wraps intent_parser.parse_request. This is the client used for the
    200-request accuracy eval and the 150-invalid-definition safety eval,
    because those need to be exactly reproducible without spending real API
    calls, the same reasoning `ontology-grounded-operations-agent` gives for
    its `DeterministicToolRouterClient`."""

    last_request_text: str | None = field(default=None, init=False)

    def build_segment(self, request_text: str) -> dict:
        self.last_request_text = request_text
        tree = parse_request(request_text)  # raises IntentParseError on failure
        session = SegmentBuilderSession()
        root_id = _replay_tree_as_tool_calls(session, tree["root"])
        return session.finalize_segment(root_id)


_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)

_PROMPT_TEMPLATE = """You are building a marketing segment definition from a plain-English request.

You may ONLY use the following tool calls, each producing an integer node id:
{tools}

Schema (field names and types only; there is no profile data available to you and you must never reference or invent any):
{schema}

Respond with ONLY a JSON array of tool calls, no prose, no markdown fences. Each element is
{{"tool": "<name>", "args": {{...}}}}. The last element must be a call to finalize_segment.

Request: {request}
"""


@dataclass
class ClaudeCLIClient(LLMClient):
    """Shells out to the real `claude` CLI as a genuine subprocess (`claude -p
    "<prompt>"`), exactly the pattern `ontology-grounded-operations-agent`'s
    `ClaudeCLIClient` uses. Exercised on a small live sample only
    (scripts/run_live_llm_sample.py); never used for the 200/150-scale evals."""

    binary: str = "claude"
    timeout_s: int = 120
    last_prompt: str | None = field(default=None, init=False)
    last_raw_response: str | None = field(default=None, init=False)

    def _build_prompt(self, request_text: str) -> str:
        from segment_builder.tools import TOOL_DEFINITIONS

        tools_desc = "\n".join(
            f"- {t['name']}({t['parameters']}) -> {t['returns']}: {t['description']}"
            for t in TOOL_DEFINITIONS
        )
        schema_desc = json.dumps(schema_metadata_for_prompt())
        return _PROMPT_TEMPLATE.format(tools=tools_desc, schema=schema_desc, request=request_text)

    def build_segment(self, request_text: str) -> dict:
        prompt = self._build_prompt(request_text)
        self.last_prompt = prompt
        try:
            result = subprocess.run(
                [self.binary, "-p", prompt],
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
        except FileNotFoundError as exc:
            raise LLMClientError(f"claude CLI not found: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise LLMClientError(f"claude CLI timed out after {self.timeout_s}s") from exc

        self.last_raw_response = result.stdout
        if result.returncode != 0:
            raise LLMClientError(f"claude CLI exited {result.returncode}: {result.stderr[:500]}")

        match = _JSON_ARRAY_RE.search(result.stdout)
        if not match:
            raise LLMClientError(f"no JSON tool-call array found in response: {result.stdout[:500]!r}")
        try:
            calls = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise LLMClientError(f"malformed JSON tool-call array: {exc}") from exc

        session = SegmentBuilderSession()
        finished: dict | None = None
        for call in calls:
            name = call.get("tool")
            args = call.get("args", {})
            try:
                if name == "add_event_predicate":
                    session.add_event_predicate(**args)
                elif name == "add_attribute_predicate":
                    session.add_attribute_predicate(**args)
                elif name == "combine":
                    session.combine(**args)
                elif name == "negate":
                    session.negate(**args)
                elif name == "finalize_segment":
                    finished = session.finalize_segment(**args)
                else:
                    raise LLMClientError(f"model invoked unknown tool: {name!r}")
            except (BuilderError, TypeError) as exc:
                raise LLMClientError(f"tool call {name!r} failed: {exc}") from exc

        if finished is None:
            raise LLMClientError("model never called finalize_segment")
        return finished
