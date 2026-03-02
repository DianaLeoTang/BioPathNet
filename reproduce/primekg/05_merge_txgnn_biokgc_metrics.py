#!/usr/bin/env python3
"""
Merge BioKGC and TxGNN metrics CSV into a single file for 02_comparison_txgnn.ipynb.
Both input CSVs must have columns: model, disease_area, seed, rel, metric, mean.

Usage (from project root):
  python reproduce/primekg/05_merge_txgnn_biokgc_metrics.py \\
    --biokgc reproduce/primekg/results/biokgc_metrics.csv \\
    --txgnn reproduce/primekg/results/txgnn_metrics.csv \\
    --output reproduce/primekg/results/txgnn_biokgc_all_metrics.csv
"""
import argparse
import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--biokgc", default="reproduce/primekg/results/biokgc_metrics.csv", help="BioKGC metrics CSV")
    parser.add_argument("--txgnn", default="reproduce/primekg/results/txgnn_metrics.csv", help="TxGNN metrics CSV")
    parser.add_argument("--output", default="reproduce/primekg/results/txgnn_biokgc_all_metrics.csv", help="Merged output CSV")
    args = parser.parse_args()

    required = ["model", "disease_area", "seed", "rel", "metric", "mean"]
    dfs = []
    for path, name in [(args.biokgc, "BioKGC"), (args.txgnn, "TxGNN")]:
        try:
            df = pd.read_csv(path)
        except FileNotFoundError:
            print("Warning: %s not found, skipping." % path)
            continue
        for c in required:
            if c not in df.columns:
                raise SystemExit("Missing column %r in %s" % (c, path))
        dfs.append(df)
    if not dfs:
        raise SystemExit("No input files found.")
    out = pd.concat(dfs, ignore_index=True)
    out = out.sort_values(["model", "disease_area", "seed", "rel", "metric"]).reset_index(drop=True)
    out.to_csv(args.output, index=False)
    print("Wrote %d rows to %s" % (len(out), args.output))


if __name__ == "__main__":
    main()
