from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
from typing import Any, Iterable, Sequence

from track3.components import ComponentScore


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class MiniLMEmbedder:
    """Local-only chunked encoder using an already acquired HF snapshot."""

    def __init__(
        self,
        model_path: str | Path,
        *,
        device: str | None = None,
        max_length: int = 512,
        stride: int = 384,
    ):
        self.model_path = Path(model_path).resolve()
        self.device_name = device
        self.max_length = max_length
        self.stride = stride
        self._tokenizer: Any = None
        self._model: Any = None
        self._torch: Any = None

    def _load(self) -> None:
        if self._model is not None:
            return
        if not self.model_path.is_dir():
            raise FileNotFoundError(f"embedding model missing: {self.model_path}")
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("MiniLM embedding requires torch and transformers") from exc
        device = self.device_name or (
            "mps" if torch.backends.mps.is_available() else "cpu"
        )
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_path,
            local_files_only=True,
        )
        self._model = AutoModel.from_pretrained(
            self.model_path,
            local_files_only=True,
        ).to(device)
        self._model.eval()
        self._torch = torch
        self.device_name = device

    def _chunks(self, text: str) -> list[list[int]]:
        backend = getattr(self._tokenizer, "backend_tokenizer", None)
        if backend is not None:
            token_ids = backend.encode(text, add_special_tokens=False).ids
        else:  # pragma: no cover - all supported snapshots use a fast tokenizer
            token_ids = self._tokenizer.encode(text, add_special_tokens=False)
        content_limit = self.max_length - 2
        if not token_ids:
            return [[]]
        step = min(self.stride, content_limit)
        return [
            token_ids[start : start + content_limit]
            for start in range(0, len(token_ids), step)
        ]

    def embed(self, text: str) -> list[float]:
        self._load()
        chunk_vectors = []
        for token_ids in self._chunks(text):
            input_ids = self._tokenizer.build_inputs_with_special_tokens(token_ids)
            prepared = {
                "input_ids": self._torch.tensor(
                    [input_ids],
                    dtype=self._torch.long,
                    device=self.device_name,
                ),
                "attention_mask": self._torch.ones(
                    (1, len(input_ids)),
                    dtype=self._torch.long,
                    device=self.device_name,
                ),
            }
            with self._torch.inference_mode():
                hidden = self._model(**prepared).last_hidden_state
            mask = prepared.get("attention_mask")
            if mask is None:
                vector = hidden.mean(dim=1)
            else:
                expanded = mask.unsqueeze(-1).expand(hidden.size()).float()
                vector = (hidden * expanded).sum(dim=1) / expanded.sum(dim=1).clamp(min=1e-9)
            vector = self._torch.nn.functional.normalize(vector, p=2, dim=1)
            chunk_vectors.append(vector[0])
        aggregate = self._torch.stack(chunk_vectors).mean(dim=0)
        aggregate = self._torch.nn.functional.normalize(aggregate, p=2, dim=0)
        return [float(value) for value in aggregate.detach().cpu()]

    def embed_many(self, texts: Iterable[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


@dataclass
class EmbeddingOODModel:
    """Rank-bounded shrinkage-covariance OOD fitted only on benign embeddings."""

    center: list[float]
    projection: list[list[float]]
    projected_center: list[float]
    precision: list[list[float]]
    distance_threshold: float
    component_id: str = "minilm_benign_ood"
    artifact_sha256: str | None = None

    @classmethod
    def fit(
        cls,
        embeddings: Sequence[Sequence[float]],
        *,
        quantile: float = 0.95,
    ) -> "EmbeddingOODModel":
        if not 0.5 <= quantile < 1.0:
            raise ValueError("OOD quantile must be in [0.5, 1)")
        if len(embeddings) < 3:
            raise ValueError("OOD fitting requires at least three benign embeddings")
        try:
            import numpy as np
            from sklearn.covariance import LedoitWolf
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "OOD fitting requires numpy and scikit-learn"
            ) from exc
        matrix = np.asarray(embeddings, dtype=float)
        if matrix.ndim != 2 or matrix.shape[1] == 0:
            raise ValueError("embeddings must be a nonempty matrix")
        origin = matrix.mean(axis=0)
        centered = matrix - origin
        # Full 384-D covariance with a few dozen benign rows is numerically
        # unstable. Restrict the model to a data-supported subspace before
        # shrinkage covariance estimation.
        _, _, right_vectors = np.linalg.svd(centered, full_matrices=False)
        rank = max(1, min(matrix.shape[0] - 2, 32, matrix.shape[1]))
        projection = right_vectors[:rank]
        projected = centered @ projection.T
        estimator = LedoitWolf().fit(projected)
        distances = estimator.mahalanobis(projected)
        threshold = float(np.quantile(distances, quantile, method="higher"))
        return cls(
            center=[float(value) for value in origin],
            projection=[
                [float(value) for value in row]
                for row in projection
            ],
            projected_center=[float(value) for value in estimator.location_],
            precision=[
                [float(value) for value in row]
                for row in estimator.precision_
            ],
            distance_threshold=max(threshold, 1e-9),
        )

    def distance(self, embedding: Sequence[float]) -> float:
        if len(embedding) != len(self.center):
            raise ValueError("embedding dimension does not match OOD model")
        difference = [
            float(value) - center
            for value, center in zip(embedding, self.center)
        ]
        reduced = [
            sum(row[index] * difference[index] for index in range(len(difference)))
            - self.projected_center[row_index]
            for row_index, row in enumerate(self.projection)
        ]
        projected = [
            sum(row[index] * reduced[index] for index in range(len(reduced)))
            for row in self.precision
        ]
        return max(
            0.0,
            sum(reduced[index] * projected[index] for index in range(len(reduced))),
        )

    def predict(self, request_id: str, embedding: Sequence[float]) -> ComponentScore:
        distance = self.distance(embedding)
        ratio = distance / self.distance_threshold
        score = 1.0 / (1.0 + math.exp(-4.0 * math.log(max(ratio, 1e-12))))
        return ComponentScore(
            request_id=request_id,
            component_id=self.component_id,
            scope="ood",
            score=score,
            flagged=distance > self.distance_threshold,
            available=True,
            evidence=f"mahalanobis_distance={distance:.6g}",
            reason="Ledoit-Wolf benign embedding OOD detector",
            artifact_sha256=self.artifact_sha256,
        )

    def save(self, path: str | Path) -> Path:
        try:
            import numpy as np
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("saving OOD models requires numpy") from exc
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            output,
            center=np.asarray(self.center, dtype=float),
            projection=np.asarray(self.projection, dtype=float),
            projected_center=np.asarray(self.projected_center, dtype=float),
            precision=np.asarray(self.precision, dtype=float),
            distance_threshold=self.distance_threshold,
            component_id=self.component_id,
        )
        self.artifact_sha256 = _sha256(output)
        return output

    @classmethod
    def load(cls, path: str | Path) -> "EmbeddingOODModel":
        try:
            import numpy as np
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("loading OOD models requires numpy") from exc
        source = Path(path)
        with np.load(source, allow_pickle=False) as payload:
            component = payload["component_id"]
            if hasattr(component, "item"):
                component = component.item()
            center = [float(value) for value in payload["center"]]
            if "projection" in payload:
                projection = [
                    [float(value) for value in row]
                    for row in payload["projection"]
                ]
                projected_center = [
                    float(value) for value in payload["projected_center"]
                ]
            else:  # Backward-compatible loader for pre-subspace dev artifacts.
                projection = [
                    [1.0 if row == column else 0.0 for column in range(len(center))]
                    for row in range(len(center))
                ]
                projected_center = [0.0] * len(center)
            return cls(
                center=center,
                projection=projection,
                projected_center=projected_center,
                precision=[
                    [float(value) for value in row]
                    for row in payload["precision"]
                ],
                distance_threshold=float(payload["distance_threshold"]),
                component_id=str(component),
                artifact_sha256=_sha256(source),
            )
