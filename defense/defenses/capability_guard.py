from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any, Mapping


_CREDENTIAL_NAME = re.compile(
    r"(^|/)(\.env(?:\..*)?|\.aws|\.ssh|\.netrc|credentials?|secrets?|"
    r"id_(?:rsa|dsa|ecdsa|ed25519)(?:\.pub)?)(/|$)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CapabilityPolicy:
    """Principal-blind allowlist for structured tool execution."""

    root: Path
    readable_paths: tuple[str, ...] = (
        "README.md",
        "POLICY.md",
        "pyproject.toml",
        "src",
        "tests",
    )
    writable_paths: tuple[str, ...] = ("src",)
    allow_network: bool = False
    allowed_tools: tuple[str, ...] = (
        "list_directory",
        "read_file",
        "write_file",
        "run_tests",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", self.root.resolve())


@dataclass(frozen=True)
class ToolProposal:
    tool: str
    arguments: Mapping[str, Any]
    request_id: str = "runtime"


@dataclass(frozen=True)
class CapabilityDecision:
    request_id: str
    tool: str
    allowed: bool
    reason: str
    normalized_path: str | None = None
    hard_policy_violation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CapabilityGuard:
    """Authorize structured actions before any side effect occurs."""

    def __init__(self, policy: CapabilityPolicy):
        self.policy = policy
        self.decisions: list[CapabilityDecision] = []

    def _record(
        self,
        proposal: ToolProposal,
        *,
        allowed: bool,
        reason: str,
        path: str | None = None,
        hard: bool = False,
    ) -> CapabilityDecision:
        decision = CapabilityDecision(
            request_id=proposal.request_id,
            tool=proposal.tool,
            allowed=allowed,
            reason=reason,
            normalized_path=path,
            hard_policy_violation=hard,
        )
        self.decisions.append(decision)
        return decision

    def _resolve(self, raw_path: Any) -> tuple[Path | None, str | None, str | None]:
        if not isinstance(raw_path, str) or not raw_path.strip():
            return None, None, "path must be a nonempty string"
        supplied = Path(raw_path)
        candidate = supplied if supplied.is_absolute() else self.policy.root / supplied
        try:
            lexical_relative = candidate.relative_to(self.policy.root)
        except ValueError:
            return None, None, "path escapes the guarded workspace"
        current = self.policy.root
        for part in lexical_relative.parts:
            current = current / part
            if current.is_symlink():
                return None, lexical_relative.as_posix(), "symlink paths are denied"
            if not current.exists():
                break
        try:
            resolved = candidate.resolve(strict=False)
            relative = resolved.relative_to(self.policy.root)
        except (OSError, RuntimeError, ValueError):
            return None, None, "path escapes the guarded workspace"
        normalized = relative.as_posix() or "."
        if _CREDENTIAL_NAME.search(normalized):
            return None, normalized, "credential and secret paths are denied"

        return resolved, normalized, None

    @staticmethod
    def _within_allowlist(normalized: str, allowlist: tuple[str, ...]) -> bool:
        target = Path(normalized)
        for raw_allowed in allowlist:
            allowed = Path(raw_allowed)
            if target == allowed or allowed in target.parents:
                return True
        return False

    def authorize(self, proposal: ToolProposal) -> CapabilityDecision:
        if proposal.tool == "network_request" and not self.policy.allow_network:
            return self._record(
                proposal,
                allowed=False,
                reason="network is disabled",
                hard=True,
            )
        if proposal.tool not in self.policy.allowed_tools:
            return self._record(
                proposal,
                allowed=False,
                reason="undeclared tool",
                hard=True,
            )
        if proposal.tool == "network_request":
            return self._record(
                proposal,
                allowed=self.policy.allow_network,
                reason="network allowed" if self.policy.allow_network else "network is disabled",
                hard=not self.policy.allow_network,
            )
        if proposal.tool == "run_tests":
            if proposal.arguments:
                return self._record(
                    proposal,
                    allowed=False,
                    reason="run_tests accepts no model-controlled arguments",
                    hard=True,
                )
            return self._record(
                proposal,
                allowed=True,
                reason="fixed test command allowed",
            )

        expected_arguments = (
            {"path", "content"} if proposal.tool == "write_file" else {"path"}
        )
        if set(proposal.arguments) != expected_arguments:
            return self._record(
                proposal,
                allowed=False,
                reason=f"{proposal.tool} requires exactly {sorted(expected_arguments)}",
                hard=True,
            )

        resolved, normalized, error = self._resolve(proposal.arguments.get("path"))
        if error:
            return self._record(
                proposal,
                allowed=False,
                reason=error,
                path=normalized,
                hard=True,
            )
        assert resolved is not None and normalized is not None
        if proposal.tool == "list_directory" and normalized == ".":
            return self._record(
                proposal,
                allowed=True,
                reason="guarded workspace-root listing allowed",
                path=normalized,
            )
        allowlist = (
            self.policy.writable_paths
            if proposal.tool == "write_file"
            else self.policy.readable_paths
        )
        if not self._within_allowlist(normalized, allowlist):
            return self._record(
                proposal,
                allowed=False,
                reason="path is outside the tool allowlist",
                path=normalized,
                hard=True,
            )
        return self._record(
            proposal,
            allowed=True,
            reason="structured capability allowed",
            path=normalized,
        )
