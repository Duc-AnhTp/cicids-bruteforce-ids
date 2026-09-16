from __future__ import annotations

import argparse
import json
import sys

from .common import ProtocolError, json_default, load_config


def main():
    parser = argparse.ArgumentParser(description="Auditable offline CICIDS2017 temporal experiment")
    parser.add_argument("command", choices=["audit", "prepare", "train", "evaluate", "report", "explain", "predict"])
    parser.add_argument("--config", default="configs/experiment.yaml")
    parser.add_argument("--input", help="One JSON flow for predict")
    args = parser.parse_args()
    try:
        cfg = load_config(args.config)
        if args.command == "audit":
            from .data import audit
            result = audit(cfg)
            keys = ["raw_rows", "selected_rows", "raw_label_counts", "start_min", "start_max",
                    "exact_record_duplicate_rows", "feature_duplicate_rows", "synthetic"]
            result = {k: result[k] for k in keys if k in result}
        elif args.command == "prepare":
            from .split import prepare
            result = prepare(cfg)["split"]
        elif args.command == "train":
            from .train import fit_models
            result = fit_models(cfg)
        elif args.command == "evaluate":
            from .evaluate import score_test_once
            result = score_test_once(cfg)
        elif args.command == "report":
            from .evaluate import build_report
            result = build_report(cfg)
        elif args.command == "explain":
            from .explain import explain_winner
            result = explain_winner(cfg)
        else:
            if not args.input:
                raise ProtocolError("predict requires --input path/to/flow.json")
            from .predict import predict_one
            result = predict_one(cfg, args.input)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=json_default, allow_nan=False))
    except (ProtocolError, FileNotFoundError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()

