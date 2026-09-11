"""Run the complete pipeline in a fresh synthetic workspace."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from make_demo_data import create_demo
from ids.common import load_config
from ids.data import audit
from ids.split import prepare
from ids.train import fit_models
from ids.evaluate import build_report, score_test_once
from ids.predict import predict_one


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "demo_workspace")
    parser.add_argument("--core-only", action="store_true")
    parser.add_argument("--explain", action="store_true")
    args = parser.parse_args()
    cfg_path = create_demo(args.output, args.core_only)
    cfg = load_config(cfg_path)
    audit(cfg); prepare(cfg)
    print(fit_models(cfg))
    print(score_test_once(cfg))
    print(build_report(cfg))
    print(predict_one(cfg, str(args.output / "example_flow.json")))
    if args.explain:
        from ids.explain import explain_winner
        print(explain_winner(cfg))
    print("PASS: synthetic software check only. Models:", cfg["training"]["models"])
    print("This is not a CICIDS2017 performance result.")


if __name__ == "__main__":
    main()

