"""A sentence encoder for labels, run locally, with no model in the matching loop.

The deterministic lexicon (``lexicon.py``) reads about seven hundred phrases.
On the words real people use it is nearly blind: measured on a solo-sailing
thought, "single-handed fatigue" against "sleep deprivation" scored 0.03 and
"wind vane self-steering" against "autopilot" scored 0.0, so the same trip
described twice in different words came back "not a resonance" at structural
1.0. That is the defect this closes.

What this is: a small multilingual sentence-embedding model (multilingual-e5
by default), exported to ONNX and run on the CPU by ``onnxruntime``. It turns
one label into one vector; the cosine between two vectors is one more signal
in ``similarity.compare``. It is deterministic for a given model file, works
offline, reads a hundred languages, and never sees a whole thought, only a
label at a time. No language model judges anything.

What this is not: a replacement for the structure. Retrieval, alignment,
contradiction and the verdict stay exactly where they were; a label pair
that the lexicon already relates is unchanged; the encoder only adds
relatedness the lexicon could not see.

Enable it with ``RESONANCE_EMBEDDER=<directory>`` holding ``tokenizer.json``
and ``onnx/model_quantized.onnx`` (or ``model.onnx``). Without the variable,
or without the two libraries, nothing here loads and the engine behaves as
before; ``semantics_version`` says which it was.
"""

from __future__ import annotations

import math
import os
import threading
from functools import lru_cache
from pathlib import Path
from typing import Sequence

ENV_VAR = "RESONANCE_EMBEDDER"
DEFAULT_MODEL_ID = "multilingual-e5-small"
# e5 models were trained with these prefixes; a label is a short query.
QUERY_PREFIX = "query: "
MAX_TOKENS = 64

# Two thresholds turn a cosine into the lexicon's two signals. Cosines from
# e5-small sit high for everything (unrelated pairs land near 0.7), so the
# useful range is narrow and is rescaled before it means anything.
# Measured on multilingual-e5-small (quantised): unrelated pairs such as
# "banana" / "pulsed power supply" sit at 0.75-0.79, paraphrases at 0.82-0.90,
# near-identical labels above 0.93.
COSINE_FLOOR = 0.78      # at or below this, the encoder says "unrelated"
COSINE_CEILING = 0.93    # at or above this, the encoder says "the same thing"


class NeuralUnavailable(RuntimeError):
    """The encoder was asked for and cannot run; say why, then run without it."""


def rescale(cosine: float) -> float:
    """Map a raw cosine into [0, 1] over the range that carries information."""
    if cosine <= COSINE_FLOOR:
        return 0.0
    if cosine >= COSINE_CEILING:
        return 1.0
    return (cosine - COSINE_FLOOR) / (COSINE_CEILING - COSINE_FLOOR)


class OnnxLabelEmbedder:
    """Mean-pooled, L2-normalised sentence embeddings from an ONNX encoder."""

    def __init__(self, directory: str | os.PathLike, *, model_id: str = DEFAULT_MODEL_ID) -> None:
        try:
            import onnxruntime as ort  # noqa: WPS433 - optional dependency
            from tokenizers import Tokenizer  # noqa: WPS433
        except ImportError as exc:  # pragma: no cover - depends on the environment
            raise NeuralUnavailable(
                "the label encoder needs the onnxruntime and tokenizers packages") from exc
        root = Path(directory)
        tokenizer_path = root / "tokenizer.json"
        candidates = [root / "onnx" / "model_quantized.onnx", root / "onnx" / "model.onnx",
                      root / "model_quantized.onnx", root / "model.onnx"]
        model_path = next((c for c in candidates if c.exists()), None)
        if not tokenizer_path.exists() or model_path is None:
            raise NeuralUnavailable(
                f"no tokenizer.json and ONNX model under {root}; expected "
                "tokenizer.json and onnx/model_quantized.onnx")
        self.tokenizer = Tokenizer.from_file(str(tokenizer_path))
        self.tokenizer.enable_truncation(MAX_TOKENS)
        options = ort.SessionOptions()
        options.intra_op_num_threads = max(1, min(4, os.cpu_count() or 1))
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(model_path), options,
                                            providers=["CPUExecutionProvider"])
        self.inputs = {i.name for i in self.session.get_inputs()}
        self.name = f"{model_id}/onnx@{model_path.name}"
        self._lock = threading.Lock()

    def embed(self, label: str) -> list[float]:
        return self._embed(label.strip().lower())

    @lru_cache(maxsize=65536)
    def _embed(self, text: str) -> list[float]:
        import numpy as np  # noqa: WPS433 - onnxruntime already depends on it
        encoded = self.tokenizer.encode(QUERY_PREFIX + text)
        ids = np.asarray([encoded.ids], dtype=np.int64)
        mask = np.asarray([encoded.attention_mask], dtype=np.int64)
        feed = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self.inputs:
            feed["token_type_ids"] = np.zeros_like(ids)
        with self._lock:
            (hidden,) = self.session.run(None, feed)[:1]
        # mean over the tokens the mask keeps
        weights = mask[..., None].astype(hidden.dtype)
        pooled = (hidden * weights).sum(axis=1) / np.clip(weights.sum(axis=1), 1e-9, None)
        vector = pooled[0]
        norm = float(np.linalg.norm(vector))
        return [float(v / norm) for v in vector] if norm else [float(v) for v in vector]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


# ---- the active encoder -----------------------------------------------------------

_ACTIVE: OnnxLabelEmbedder | None = None


def active() -> OnnxLabelEmbedder | None:
    return _ACTIVE


def activate(embedder: OnnxLabelEmbedder | None) -> None:
    """Install (or remove) the encoder the semantic layer reads."""
    global _ACTIVE
    _ACTIVE = embedder
    # Both caches hold answers per label pair; a different encoder is a
    # different answer.
    relatedness.cache_clear()
    from src.semantics import similarity as _similarity
    _similarity.compare.cache_clear()


def activate_from_environment(environ=None) -> str | None:
    """Load the encoder named by RESONANCE_EMBEDDER, if any.

    Returns the encoder's name when one is active, None when the variable is
    unset. A variable that names something unusable raises NeuralUnavailable
    so a deployment never silently runs without the layer it was told to run.
    """
    environ = os.environ if environ is None else environ
    where = (environ.get(ENV_VAR) or "").strip()
    if not where:
        activate(None)
        return None
    activate(OnnxLabelEmbedder(where))
    return _ACTIVE.name if _ACTIVE else None


@lru_cache(maxsize=262144)
def relatedness(a: str, b: str) -> float:
    """Encoder relatedness of two labels in [0, 1]; 0.0 with no encoder."""
    if _ACTIVE is None:
        return 0.0
    if a == b:
        return 1.0
    return rescale(cosine(_ACTIVE.embed(a), _ACTIVE.embed(b)))
