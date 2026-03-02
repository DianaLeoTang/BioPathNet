# PrimeKG 复现流程：从数据划分到 txgnn_biokgc_all_metrics.csv

本文档说明在用 `01_get_datasplit.py` 生成各 disease split 数据后，如何跑 BioPathNet (BioKGC) 和 TxGNN，并得到 `results/txgnn_biokgc_all_metrics.csv`，供 `02_comparison_txgnn.ipynb` 画图使用。

---

## 总体流程

1. **生成数据划分**：`01_get_datasplit.py` → 得到 `data/primekg/disease_split/<split>_<seed>/nfbnet/`
2. **训练并评估 BioPathNet**：对每个 (split, seed) 跑 `script/run.py`，再对每个 checkpoint 用 `04_collect_biokgc_metrics.py` 按 indication/contraindication 收集指标 → `results/biokgc_metrics.csv`
3. **运行 TxGNN**：在 TxGNN 仓库中对相同 split/seed 训练与评估，并导出同格式指标 → `results/txgnn_metrics.csv`
4. **合并**：`05_merge_txgnn_biokgc_metrics.py` → `results/txgnn_biokgc_all_metrics.csv`

---

## 步骤 1：生成数据划分

在**项目根目录**执行（需先准备好 TxGNN 格式的 source 数据与 `reproduce/data/disease_files/*.csv`）：

```bash
cd /Users/callustang/TsinghuaCode/BioPathNet

# 示例：对 cell_proliferation、seed=42 生成数据，输出到 data/primekg/disease_split/
python reproduce/primekg/01_get_datasplit.py \
  --source data/primekg/disease_split \
  --split cell_proliferation \
  --seed 42
```

- `--source`：建议设为 `data/primekg/disease_split`，这样输出目录为  
  `data/primekg/disease_split/<split>_<seed>/nfbnet/`（内含 `train1.txt`, `train2.txt`, `valid.txt`, `test_indi.txt`, `test_contra.txt` 等）。
- 对每个需要的 **(split, seed)** 各跑一次（如 5 个 disease area × 2 个 seed）。

**注意**：当前 `config/primekg/*.yaml` 里的 `dataset.path` 形如 `data/primekg/disease_split/cell_proliferation_42/`。若你按上面用 `nfbnet` 子目录，则需在配置或运行训练时把 path 改为 **`data/primekg/disease_split/cell_proliferation_42/nfbnet`**（即包含 `train1.txt` 的那一层）。  
训练时请在**项目根目录**运行 `script/run.py`，这样 `data/` 相对路径会正确解析；若训练脚本会 `chdir` 到实验目录，则需在 config 里使用**绝对路径**或根据实验目录写相对路径。

---

## 步骤 2：训练 BioPathNet (BioKGC)

对每个 disease split 和 seed，用对应 config 训练（需传入 `gpus`，因 yaml 中有 `{{ gpus }}`）：

```bash
# 在项目根目录
python script/run.py -c config/primekg/cell_proliferation.yaml --gpus 0 --seed 42
```

- 训练结束后，当前工作目录会切到 `experiments/.../`，其中会有 `model_epoch_<best>.pth`。
- 记下该**实验目录**或**最佳 checkpoint 路径**，下一步收集指标时会用到。

对每个 `config/primekg/<split>.yaml` 和每个 seed 重复上述命令（可并行或写循环脚本）。

---

## 步骤 3：按 indication/contraindication 收集 BioKGC 指标

使用本目录下的 **`04_collect_biokgc_metrics.py`**：对指定 config、seed、checkpoint，分别用 `test_indi.txt` 和 `test_contra.txt` 评估，得到按关系类型分的指标并追加写入 CSV。

```bash
# 在项目根目录
python reproduce/primekg/04_collect_biokgc_metrics.py \
  -c config/primekg/cell_proliferation.yaml \
  --seed 42 \
  --checkpoint /path/to/experiments/.../model_epoch_3.pth \
  --disease_area cell_proliferation \
  --output reproduce/primekg/results/biokgc_metrics.csv
```

- `--checkpoint`：步骤 2 得到的最佳模型路径。
- `--disease_area`：与 config 对应的 split 名（如 cell_proliferation, mental_health）。
- 若数据实际在 `.../nfbnet` 下，可加：  
  `--dataset_path data/primekg/disease_split/cell_proliferation_42/nfbnet`。

对每个 (split, seed) 及对应 checkpoint 各跑一次，脚本会**追加**到同一个 `--output` CSV。最终得到 **`results/biokgc_metrics.csv`**（列：model, disease_area, seed, rel, metric, mean）。

---

## 步骤 4：运行 TxGNN 并导出指标

在 [TxGNN 仓库](https://github.com/mims-harvard/TxGNN) 中，对**相同的** split 与 seed 做训练与评估，并按与 BioKGC 相同的格式导出：

- **model**：`"TxGNN"`
- **disease_area**：如 cell_proliferation, mental_health 等
- **seed**：与 BioPathNet 一致（如 42）
- **rel**：`indication` 或 `contraindication`
- **metric**：与 BioKGC 一致（如 AUPRC, MRR@20, AP@20 等）
- **mean**：该 (rel, metric) 的数值

保存为 **`reproduce/primekg/results/txgnn_metrics.csv`**（列名与上面一致即可）。

---

## 步骤 5：合并为 txgnn_biokgc_all_metrics.csv

在项目根目录运行：

```bash
python reproduce/primekg/05_merge_txgnn_biokgc_metrics.py \
  --biokgc reproduce/primekg/results/biokgc_metrics.csv \
  --txgnn reproduce/primekg/results/txgnn_metrics.csv \
  --output reproduce/primekg/results/txgnn_biokgc_all_metrics.csv
```

会生成 **`results/txgnn_biokgc_all_metrics.csv`**，供 `02_comparison_txgnn.ipynb` 使用。

---

## 步骤 6：画图

确保 R 已安装且已安装 notebook 中用到的包（如 `data.table`, `ggplot2`, `patchwork` 等），然后打开并顺序运行：

**`reproduce/primekg/02_comparison_txgnn.ipynb`**

notebook 会读取 `results/txgnn_biokgc_all_metrics.csv`（路径相对 notebook 所在目录）。

---

## 所需 CSV 列说明

- **model**：`"BioKGC"` 或 `"TxGNN"`
- **disease_area**：如 cell_proliferation, mental_health, anemia, adrenal_gland, cardiovascular
- **seed**：整数（如 42）
- **rel**：`indication` 或 `contraindication`
- **metric**：如 AUPRC, Sensitivity, Specificity, F1, FPR, FNR, MRR@20, AP@20, AUPRC_1:1 等（与 notebook 中 `plot_metric` 使用的一致）
- **mean**：该 (model, disease_area, seed, rel, metric) 的数值

BioPathNet 默认评估给出的是 MRR、hits@k、AP、AUROC 等；若 notebook 里用了 Sensitivity/Specificity/F1 等，需在 TxGNN 或后续分析里用同一口径计算并填入。
