#!/usr/bin/env python3
"""
Collect BioKGC (BioPathNet) metrics per relation (indication / contraindication)
by evaluating on test_indi.txt and test_contra.txt separately.
Appends rows to --output CSV for later merge with TxGNN results.

Run from project root, e.g.:
  python reproduce/primekg/04_collect_biokgc_metrics.py \\
    -c config/primekg/cell_proliferation.yaml --gpus 0 --seed 42 \\
    --checkpoint /path/to/model_epoch_X.pth \\
    --disease_area cell_proliferation \\
    --output reproduce/primekg/results/biokgc_metrics.csv
"""
import os
import sys
import copy
import argparse
import pandas as pd

import torch
from torchdrug import core
from torchdrug.utils import comm

# project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from biopathnet import dataset, layer, model, task, util


def solver_load(checkpoint, solver, load_optimizer=False):
    checkpoint = os.path.expanduser(checkpoint)
    state = torch.load(checkpoint, map_location=solver.device)
    state["model"].pop("fact_graph", None)
    state["model"].pop("fact_graph_supervision", None)
    state["model"].pop("graph", None)
    state["model"].pop("train_graph", None)
    state["model"].pop("valid_graph", None)
    state["model"].pop("test_graph", None)
    state["model"].pop("full_valid_graph", None)
    state["model"].pop("full_test_graph", None)
    solver.model.load_state_dict(state["model"], strict=False)
    if load_optimizer and "optimizer" in state:
        solver.optimizer.load_state_dict(state["optimizer"])
    comm.synchronize()


def build_solver(cfg, _dataset, train_set, valid_set, test_set):
    cfg.task.model.num_relation = _dataset.num_relation
    _task = core.Configurable.load_config_dict(cfg.task)
    cfg.optimizer.params = _task.parameters()
    optimizer = core.Configurable.load_config_dict(cfg.optimizer)
    scheduler = None
    if "scheduler" in cfg:
        cfg.scheduler.optimizer = optimizer
        scheduler = core.Configurable.load_config_dict(cfg.scheduler)
    return core.Engine(_task, train_set, valid_set, test_set, optimizer, scheduler, **cfg.engine)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", required=True, help="Config yaml (e.g. config/primekg/cell_proliferation.yaml)")
    parser.add_argument("--gpus", default=0, help="GPU id for engine (default 0)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed used for this run")
    parser.add_argument("--checkpoint", required=True, help="Path to model_epoch_*.pth")
    parser.add_argument("--disease_area", required=True, help="e.g. cell_proliferation, mental_health")
    parser.add_argument("--output", default="reproduce/primekg/results/biokgc_metrics.csv", help="Output CSV (appended)")
    parser.add_argument("--dataset_path", default=None, help="Override dataset path (e.g. .../cell_proliferation_42/nfbnet)")
    args = parser.parse_args()

    # Load config (gpus is template var in primekg configs)
    cfg = util.load_config(args.config, context={"gpus": args.gpus})
    if args.dataset_path:
        cfg.dataset.path = args.dataset_path

    # Ensure path is absolute relative to cwd so it works when script is run from project root
    if not os.path.isabs(cfg.dataset.path):
        cfg.dataset.path = os.path.abspath(cfg.dataset.path)

    torch.manual_seed(args.seed)
    rows = []

    for test_file, rel in [("test_indi.txt", "indication"), ("test_contra.txt", "contraindication")]:
        test_path = os.path.join(cfg.dataset.path, test_file)
        if not os.path.isfile(test_path):
            print("Warning: %s not found, skipping rel=%s" % (test_path, rel))
            continue
        cfg_local = copy.deepcopy(cfg)
        cfg_local.dataset.files = ["train1.txt", "train2.txt", "valid.txt", test_file]
        _dataset = core.Configurable.load_config_dict(cfg_local.dataset)
        train_set, valid_set, test_set = _dataset.split()
        solver = build_solver(cfg_local, _dataset, train_set, valid_set, test_set)
        solver_load(args.checkpoint, solver)
        solver.model.split = "test"
        metric_dict = solver.evaluate("test")
        if metric_dict is None:
            continue
        for name, value in metric_dict.items():
            if hasattr(value, "item"):
                value = value.item()
            if isinstance(value, (list, tuple)):
                value = sum(value) / len(value) if value else 0.0
            rows.append({
                "model": "BioKGC",
                "disease_area": args.disease_area,
                "seed": args.seed,
                "rel": rel,
                "metric": name,
                "mean": float(value),
            })

    if not rows:
        print("No metrics collected (check dataset path and test_indi/test_contra files).")
        return
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    df = pd.DataFrame(rows)
    write_header = not os.path.isfile(args.output)
    df.to_csv(args.output, mode="a", header=write_header, index=False)
    print("Appended %d rows to %s" % (len(rows), args.output))


if __name__ == "__main__":
    main()
