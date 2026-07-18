"""Enum flag types.

Typer validates these before any DB round-trip, so a bad ``--status`` /
``--verdict`` / ``--outcome`` is rejected with the valid list and exit code 2.
The members mirror the CHECK constraints in the schema (0001 migration); if a
constraint changes, these change with it.
"""

from __future__ import annotations

from enum import Enum


class ProjectStatus(str, Enum):
    active = "active"
    paused = "paused"
    done = "done"
    archived = "archived"


class TaskStatus(str, Enum):
    backlog = "backlog"
    planned = "planned"
    in_progress = "in_progress"
    in_review = "in_review"
    awaiting_tyler = "awaiting_tyler"
    done = "done"


class ModelTier(str, Enum):
    plan = "plan"
    execute = "execute"
    local = "local"


class RunMode(str, Enum):
    team = "team"
    subagent = "subagent"
    headless = "headless"
    interactive = "interactive"


class RunOutcome(str, Enum):
    done = "done"
    negative_result = "negative-result"
    blocked = "blocked"
    failed = "failed"


class PrStatus(str, Enum):
    open = "open"
    merged = "merged"
    rejected = "rejected"
    closed = "closed"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class DecisionStatus(str, Enum):
    proposed = "proposed"
    accepted = "accepted"
    superseded = "superseded"
    reversed = "reversed"


class DecisionSignificance(str, Enum):
    major = "major"
    minor = "minor"


class RiskCategory(str, Enum):
    security = "security"
    architecture = "architecture"
    operational = "operational"
    cost = "cost"
    dependency = "dependency"
    product = "product"


class RiskStatus(str, Enum):
    acknowledged = "acknowledged"
    mitigated = "mitigated"
    accepted = "accepted"
    realized = "realized"
    closed = "closed"


class Verdict(str, Enum):
    approve = "approve"
    concerns = "concerns"
    block = "block"


class ArtifactType(str, Enum):
    mockup = "mockup"
    diagram = "diagram"
    spec = "spec"
    schema = "schema"
    model = "model"
    eval_set = "eval-set"
    prompt = "prompt"


class ArtifactStatus(str, Enum):
    approved = "approved"
    rejected = "rejected"
    superseded = "superseded"


class MetricStatus(str, Enum):
    proposed = "proposed"
    active = "active"
    retired = "retired"


class LearningCategory(str, Enum):
    start = "start"
    stop = "stop"
    keep = "keep"
    question = "question"


class LearningStatus(str, Enum):
    open = "open"
    resolved = "resolved"
    escalated = "escalated"


class DebtKind(str, Enum):
    duplication = "duplication"
    coupling = "coupling"
    missing_tests = "missing-tests"
    pattern_drift = "pattern-drift"
    dead_code = "dead-code"
    docs = "docs"
    other = "other"


class DebtStatus(str, Enum):
    open = "open"
    proposed = "proposed"
    resolved = "resolved"
    stale = "stale"
    escalated = "escalated"


class Severity(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"
