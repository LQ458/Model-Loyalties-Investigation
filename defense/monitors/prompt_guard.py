from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from runtime.components import ComponentScore
from runtime.models import BlindMonitorInput


def _tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


class PromptGuardMonitor:
    """Offline wrapper for a pretrained sequence-classification guard."""

    component_id = "llama_prompt_guard_2"

    def __init__(
        self,
        model_path: str | Path,
        *,
        threshold: float = 0.5,
        device: str | None = None,
    ):
        self.model_path = Path(model_path).resolve()
        self.threshold = threshold
        self.device_name = device
        self._tokenizer: Any = None
        self._model: Any = None
        self._torch: Any = None
        self.artifact_sha256 = (
            _tree_sha256(self.model_path) if self.model_path.is_dir() else None
        )

    def _load(self) -> None:
        if self._model is not None:
            return
        if not self.model_path.is_dir():
            raise FileNotFoundError(f"Prompt Guard weights missing: {self.model_path}")
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "Prompt Guard requires torch and transformers"
            ) from exc
        device = self.device_name or (
            "mps" if torch.backends.mps.is_available() else "cpu"
        )
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_path,
            local_files_only=True,
        )
        self._model = AutoModelForSequenceClassification.from_pretrained(
            self.model_path,
            local_files_only=True,
        ).to(device)
        self._model.eval()
        self._torch = torch
        self.device_name = device

    def _malicious_probability(self, logits: Any) -> float:
        probabilities = self._torch.softmax(logits, dim=-1)
        config = self._model.config
        label2id = {
            str(label).casefold(): int(index)
            for label, index in (getattr(config, "label2id", {}) or {}).items()
        }
        malicious_index = next(
            (
                index
                for label, index in label2id.items()
                if any(token in label for token in ("malicious", "injection", "jailbreak"))
            ),
            None,
        )
        if malicious_index is None:
            if probabilities.shape[-1] != 2:
                raise ValueError("cannot identify Prompt Guard malicious label")
            malicious_index = 1
        return float(probabilities[:, malicious_index].max().detach().cpu())

    def predict(self, item: BlindMonitorInput) -> ComponentScore:
        if not item.observation.strip():
            return ComponentScore(
                request_id=item.request_id,
                component_id=self.component_id,
                scope="input",
                score=None,
                flagged=None,
                available=False,
                reason="empty input observation",
                artifact_sha256=self.artifact_sha256,
            )
        try:
            self._load()
        except (FileNotFoundError, RuntimeError) as exc:
            return ComponentScore(
                request_id=item.request_id,
                component_id=self.component_id,
                scope="input",
                score=None,
                flagged=None,
                available=False,
                reason=str(exc),
                artifact_sha256=self.artifact_sha256,
            )
        encoded = self._tokenizer(
            item.observation,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            return_overflowing_tokens=True,
            padding=True,
        )
        encoded.pop("overflow_to_sample_mapping", None)
        encoded = {key: value.to(self.device_name) for key, value in encoded.items()}
        with self._torch.inference_mode():
            logits = self._model(**encoded).logits
        score = self._malicious_probability(logits)
        return ComponentScore(
            request_id=item.request_id,
            component_id=self.component_id,
            scope="input",
            score=score,
            flagged=score >= self.threshold,
            available=True,
            reason="pretrained Prompt Guard sequence classifier",
            artifact_sha256=self.artifact_sha256,
        )
