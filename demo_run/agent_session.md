# Agent 真实演示记录

## 用户问题

“基于公开 NCM 正极材料数据，预测初始放电容量和第 50 周期放电容量，并检查数据质量。”

## Agent 工作流

1. 识别为材料性能预测任务。
2. 确认数据集来源、样本单位、目标列和特征列。
3. 检查缺失值、重复行、标识列和随机切分风险。
4. 分别对 `IC` 和 `EC` 运行 Random Forest 基线。
5. 输出 MAE、RMSE、R²、特征重要性和限制。
6. 明确指出当前数据没有 MP ID/显式 DFT 特征，不能声称 DFT 增益。

## 可复现命令

```bash
python3 scripts/run_material_demo.py
```

这条命令不调用远程计算、不使用 API key，所有输出写入 `demo_run/material_demo/`。
