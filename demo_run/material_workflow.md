# 材料级性能预测真实运行记录

数据：`datasets/raw/NMC_numerical_new.csv`，来自公开 NCM-ML 仓库，168 条材料记录。

执行：

```bash
python3 scripts/data_quality.py datasets/raw/NMC_numerical_new.csv --target IC --out demo_run/reports/nmc_quality.json
python3 scripts/baseline_predict.py --csv datasets/raw/NMC_numerical_new.csv --target IC --out demo_run/reports/nmc_ic_metrics.json
python3 scripts/baseline_predict.py --csv datasets/raw/NMC_numerical_new.csv --target EC --out demo_run/reports/nmc_ec_metrics.json
```

结果：

- IC：MAE 7.7027，RMSE 9.2659，R² 0.9111。
- EC：MAE 6.9329，RMSE 8.5348，R² 0.8944。

当前为随机划分；数据没有材料/论文来源分组字段，不能把这些数值解释为化学体系外推性能。后续真实研究应按材料、来源或结构家族分组，并加入真实 DFT/Materials Project 特征后重新评估。
