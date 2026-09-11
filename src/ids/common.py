from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path
from typing import Any

import numpy as np
import yaml


class ProtocolError(ValueError):
    """Invalid input or violation of the frozen experiment protocol."""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def digest_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def json_default(value: Any):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False,
                              default=json_default, allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_config(path: str | Path) -> dict:
    path = Path(path).resolve()
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(cfg, dict):
        raise ProtocolError("Config must be a YAML mapping.")
    required = {"experiment_id", "seed", "input", "features", "split", "training", "explain", "paths"}
    if set(cfg) != required:
        raise ProtocolError(f"Top-level config keys must be {sorted(required)}")
    if cfg["input"]["duration_unit"] != "us":
        raise ProtocolError("This protocol expects CIC Flow Duration in microseconds.")
    if cfg["split"]["duplicate_policy"] != "exact_record_keep_earliest":
        raise ProtocolError("Unsupported duplicate policy.")
    if cfg["training"]["selection_metric"] != "f1_attack":
        raise ProtocolError("This implementation freezes selection by validation Attack F1.")
    thresholds = cfg["training"]["thresholds"]
    if not thresholds or any(not 0 < x < 1 for x in thresholds):
        raise ProtocolError("Threshold grid must be nonempty and strictly between 0 and 1.")
    if cfg["training"]["n_jobs"] < 1:
        raise ProtocolError("Use a positive, bounded CPU thread count.")
    models = cfg["training"]["models"]
    expected_models = ["decision_tree", "random_forest", "xgboost"]
    if not models or len(models) != len(set(models)) or not set(models).issubset(expected_models):
        raise ProtocolError("Unknown/duplicated model names.")
    if not cfg["input"]["synthetic"] and models != expected_models:
        raise ProtocolError("The real experiment requires all three models in the declared order.")
    cfg["_root"] = str(path.parent.parent)
    cfg["_config_path"] = str(path)
    return cfg


def public_config(cfg: dict) -> dict:
    return {k: v for k, v in cfg.items() if not k.startswith("_")}


def config_hash(cfg: dict) -> str:
    return digest_json(public_config(cfg))


def resolve(cfg: dict, value: str) -> Path:
    return (Path(cfg["_root"]) / value).resolve()


def locations(cfg: dict) -> tuple[Path, Path]:
    return resolve(cfg, cfg["paths"]["processed"]), resolve(cfg, cfg["paths"]["run"])


def environment() -> dict:
    versions = {}
    for name in ["numpy", "pandas", "scikit-learn", "xgboost", "shap", "joblib", "matplotlib", "PyYAML"]:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {"python": platform.python_version(), "platform": platform.platform(), "packages": versions}


def code_hash() -> str:
    return digest_json({p.name: file_sha256(p) for p in sorted(Path(__file__).parent.glob("*.py"))})


def require_unopened(run: Path) -> None:
    if (run / "TEST_OPENED.json").exists():
        raise ProtocolError("Test was already opened. Do not tune or overwrite this experiment.")
