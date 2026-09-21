# 验收报告

日期：2026-09-21

## 已验证

| 能力 | 验证方式 | 结果 |
|---|---|---|
| 项目规范恢复 | `python3 scripts/doctor.py` | 通过 |
| Codex/Claude Skills 链接 | `python3 scripts/install_check.py` | 通过 |
| 无网络核心自检 | `python3 scripts/self_test.py` | 通过 |
| Python 自动化测试 | `python3 -m unittest discover -s tests -v` | 3/3 通过 |
| 统一 CLI | `python3 new_energy_agent.py doctor/self-test/predict` | 通过 |
| 电池公开数据下载 | Zenodo record 4032561 | 已下载并保存 SHA256 |
| 非标准电池 CSV | `data_contract.py --header-line 14` | 正确识别字段 |
| 循环数据派生 | `normalize_cycle_csv.py` | 生成逐循环表 |
| 数据质量检查 | `data_quality.py` | 输出缺失/重复/分组泄漏警告 |
| 分组性能基线 | `baseline_predict.py --group` | 生成 MAE/RMSE/R² 和特征重要性 |
| 化学式特征 | `material_features.py` | 简单化学式解析通过，复杂语法明确报告限制 |
| DFT 输出解析 | `parse_dft_output.py` | OUTCAR 标量 smoke test 通过 |
| 远程计算安全边界 | `compute_plan.py` | 只生成计划，不提交 SSH/Slurm |
| MP 可选接入 | `query_materials_project.py` | 无 key 时明确提示，不保存密钥 |
| 真实本地端到端演示 | `demo_run/` | 公开 Zenodo 电池数据完成质量检查和分组性能基线 |

## 项目交付内容

- Codex 项目规则：`AGENTS.md`
- 项目规格、架构、决策、需求和任务记录
- `commands/`：research、experiment、predict、review、compute
- `skills/`：五个新能源材料科研 Skill
- `agents/`：研究、实验、数据、计算、审查角色
- `scripts/`：工作区、数据、预测、DFT、安装和验收工具
- `tests/`：本地自动化测试
- 公开数据来源与数据契约
- Git 历史和变更记录

## 外部条件

- Materials Project 查询需要用户在本机设置 `MP_API_KEY`，项目不会保存或读取聊天中的密钥。
- `pymatgen`/`mp-api` 是可选依赖；核心工具不依赖它们。
- 真实 SSH/Slurm 需要用户自己的主机、账户、队列和服务器环境；项目只在确认后生成/执行任务。
- Figshare 材料级数据页面的自动下载接口当前返回 HTTP 403；来源和字段已登记，项目使用 Zenodo 电池数据完成本地验证，并保留 Figshare 作为可选材料级扩展。
- `demo_run/` 的指标是电芯循环 smoke test，不应解释为材料组成或 DFT 特征的科学结论。
