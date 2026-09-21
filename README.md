# New Energy Research Agent

面向新能源材料研究的本地 Agent 工作区。它通过 `AGENTS.md`、Skills、Commands、子 Agent 和可复现脚本，为 Codex 提供文献研究、实验设计、性能预测、论文审查和 DFT 计算编排能力。

项目不提供 Web 前端，也不绑定模型供应商。Codex 是主要运行入口；Claude Code 等兼容 Agent 可以通过同一套项目文件使用。

## 设计原则

- LLM 负责理解、规划、提问和解释。
- Python/命令行脚本负责确定性的数据处理和科学检查。
- 轻量本地任务可直接执行；远程、GPU、长时或有费用的任务先展示计划并等待确认。
- SSH/Slurm 只在用户确认后执行，私钥不进入项目目录。
- 每个结论、数据和计算结果保留来源、状态和处理记录。

## 快速使用

将项目安装到 Codex 和 Claude Code 的 skills 目录：

```bash
./install.sh
```

数据基线脚本需要 Python、pandas、numpy 和 scikit-learn；可按当前机器情况安装：

```bash
python3 -m pip install -r requirements.txt
```

`pymatgen` 和 `mp-api` 是可选的材料结构与 Materials Project 适配依赖，不会在安装 Skills 时强制安装。

然后在项目目录中使用 Codex：

```text
/research 研究掺杂对层状氧化物正极循环稳定性的影响
/experiment 设计一个可验证上述问题的实验
/predict 使用当前 datasets/ 下的数据预测循环保持率
/review 审查当前论文草稿和 DFT 方法
/compute 为当前结构生成 DFT 计算计划
```

## 当前状态

项目目前处于规范和基础工作流实现阶段。权威文档见：

- `PROJECT_SPEC.md`：项目目标和范围
- `ARCHITECTURE.md`：完整架构
- `DECISIONS.md`：已经确认的决策
- `REQUIREMENTS.md`：功能与验收标准
- `TASKS.md`：当前任务状态

## 本地自检

```bash
python3 scripts/self_test.py
```

统一 CLI：

```bash
python3 new_energy_agent.py doctor
python3 new_energy_agent.py self-test
python3 new_energy_agent.py predict --demo --group source_group --out /tmp/metrics.json
python3 new_energy_agent.py quality datasets/processed/LGM50_cell03_by_cycle.csv --target capacity_ah_max --group cycle --out /tmp/quality.json
python3 scripts/run_material_demo.py
```

运行 Python 测试：

```bash
python3 -m unittest discover -s tests -v
```
