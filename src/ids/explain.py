from __future__ import annotations

import joblib
import numpy as np
import pandas as pd

from .common import ProtocolError, write_json
from .evaluate import verify_frozen
from .split import load_partition


def explain_winner(cfg: dict) -> dict:
    try:
        import shap
    except ImportError as exc:
        raise ProtocolError('SHAP is optional: install with python -m pip install -e ".[xai]".') from exc
    processed, run, manifest, frozen = verify_frozen(cfg)
    val = load_partition(processed, manifest, "validation")
    limit = cfg["explain"]["max_rows"]
    if limit < 1:
        raise ProtocolError("SHAP max_rows must be positive.")
    val = val.sample(n=min(limit, len(val)), random_state=cfg["seed"])
    name = frozen["winner"]
    pipeline = joblib.load(run / frozen["models"][name]["file"])
    transformed = pipeline[:-1].transform(val[frozen["feature_schema"]])
    names = pipeline.named_steps["columns"].keep_
    model = pipeline.named_steps["model"]
    explainer = shap.TreeExplainer(model, feature_perturbation="tree_path_dependent", model_output="raw")
    values = explainer.shap_values(transformed, check_additivity=True)
    expected = explainer.expected_value
    if isinstance(values, list):
        values = values[1]
    values = np.asarray(values)
    if values.ndim == 3:
        values = values[:, :, 1]
    if values.shape != transformed.shape:
        raise ProtocolError(f"Unexpected SHAP shape {values.shape}, input shape {transformed.shape}.")
    expected_arr = np.asarray(expected).ravel()
    expected = float(expected_arr[1] if expected_arr.size == 2 else expected_arr[0])
    target_output = (model.predict(transformed, output_margin=True) if name == "xgboost"
                     else model.predict_proba(transformed)[:, 1])
    max_additivity_error = float(np.max(np.abs(expected + values.sum(axis=1) - target_output)))
    if not np.isfinite(values).all() or not np.allclose(expected + values.sum(axis=1), target_output, rtol=1e-3, atol=1e-3):
        raise ProtocolError("SHAP additivity/finite check failed; do not publish this explanation.")
    out = run / "shap"; out.mkdir(exist_ok=True)
    importance = pd.DataFrame({"feature": names, "mean_abs_shap": np.abs(values).mean(axis=0)}).sort_values("mean_abs_shap", ascending=False)
    importance.to_csv(out / "feature_importance.csv", index=False)
    val[["_row_id", "_label"]].to_csv(out / "sample_rows.csv", index=False)
    np.savez_compressed(out / "values.npz", values=values, transformed=transformed, expected=expected, features=np.asarray(names))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    top = importance.head(20).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.barh(top["feature"], top["mean_abs_shap"])
    ax.set_xlabel("Mean |SHAP| (log-odds)" if name == "xgboost" else "Mean |SHAP| (model score)")
    ax.set_title(f"{'SYNTHETIC: ' if frozen['synthetic'] else ''}{name} — Validation sample")
    fig.tight_layout(); fig.savefig(out / "summary.png", dpi=170); plt.close(fig)
    explanation = shap.Explanation(values=values, base_values=np.full(len(values), expected),
                                   data=transformed, feature_names=names)
    shap.plots.waterfall(explanation[0], max_display=12, show=False)
    plt.tight_layout(); plt.savefig(out / "example_waterfall.png", dpi=170, bbox_inches="tight"); plt.close("all")
    meta = {"model": name, "partition": "validation", "sampling": "uniform random without replacement",
            "n": len(val), "seed": cfg["seed"], "label_counts": val["_label"].value_counts().to_dict(),
            "output_unit": "log-odds" if name == "xgboost" else "uncalibrated model score",
            "feature_perturbation": "tree_path_dependent", "background": "training path counts stored by model",
            "max_additivity_error": max_additivity_error, "synthetic": frozen["synthetic"],
            "limitation": "Explains fitted model behavior; correlated feature attributions are not causal evidence or a feature-selection step."}
    write_json(out / "metadata.json", meta)
    return meta

