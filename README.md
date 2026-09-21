# New Energy Research Agent

一个 **Codex-first、文件工作区优先的新能源材料科研 Agent**。

它把研究问题拆成可检查的计划，再由确定性的 Python 工具完成数据检查、基线建模、Materials Project 查询、DFT 输出解析和远程计算计划。模型负责理解问题、规划、提问和解释；科学数据处理、评价指标、来源记录和执行边界落在可复现的文件与脚本中。

项目面向电池材料与 DFT 验证场景，也可以扩展到其他新能源材料问题。它不是 Web SaaS，也不强制绑定某一家模型供应商：在 Codex 中使用时直接复用当前 Agent 的底座模型，Claude Code 等能读取 `AGENTS.md`、Skills 和 Commands 的 Agent 也可以使用同一个目录。

## 目录

- [项目解决什么问题](#项目解决什么问题)
- [能力地图](#能力地图)
- [架构](#架构)
- [快速开始](#快速开始)
- [使用方式](#使用方式)
- [公开数据与真实演示](#公开数据与真实演示)
- [Materials Project 配置](#materials-project-配置)
- [远程 DFT 与确认边界](#远程-dft-与确认边界)
- [输出和可追溯性](#输出和可追溯性)
- [评估与验证](#评估与验证)
- [限制](#限制)
- [设计参考](#设计参考)

## 项目解决什么问题

科研 Agent 最容易失控的地方不是“不会回答”，而是把未经核验的回答、数据库值、实验标签和模型预测混在一起，最后无法复现。这个项目用一个本地工作区把研究过程拆开：

1. 先确认材料体系、科学问题、样本单位、输入、输出和成功标准。
2. 再选择研究、实验、预测、审查或计算工作流。
3. 把中间状态、原始数据、来源、脚本输出和人工确认写进项目目录。
4. 对远程、GPU、长时间、批量或有费用的计算先生成计划，等待用户确认后才执行。
5. 报告事实、数据库原生值、计算值、模型预测和假设各自的证据状态。

因此，项目的核心交付物不是一段聊天记录，而是一组能够被检查、继续执行和写入论文工作流的研究产物。

## 能力地图

| 工作流 | Agent 入口 | 确定性工具 | 主要产物 |
| --- | --- | --- | --- |
| 研究助手 | `/research` | 来源登记、任务状态、证据记录 | `papers/`、`reports/`、`workspace/` |
| 实验设计 | `/experiment` | 数据契约、变量和统计计划模板 | `reports/experiment-plan.md`、数据 schema |
| 性能预测 | `/predict` | 缺失/重复/泄漏预检、分组切分、Random Forest 基线 | 指标 JSON、质量报告、日志 |
| 论文与方法审查 | `/review` | 证据定位和问题清单协议 | 带位置、影响和修改建议的审查报告 |
| DFT 计算编排 | `/compute` | 资源计划、SSH/Slurm 命令、OUTCAR 标量解析 | `approvals/`、`calculations/`、解析结果 |

已经实际验证的材料演示包括：公开 NCM 材料性能数据、公开电芯循环数据、Materials Project API 查询、MP 特征合并、数据质量检查和预测基线。真实远程 DFT 需要用户自己的服务器和确认，不在本地验收中伪造完成。

## 架构

```text
Codex / Claude Code / 其他兼容 Agent
                 │
       AGENTS.md + Commands + Skills
                 │
       研究问题 → 工作流计划 → 用户确认（必要时）
                 │
       workspace/  papers/  datasets/  reports/
                 │
       scripts/：数据、预测、MP、DFT、验收
                 │
       本地执行或经确认的 SSH / Slurm 计算
```

### 四条设计原则

- **模型与科学执行分离**：模型进行问题理解和编排，Python 脚本负责可重复的数据转换、检查和指标计算。
- **证据有状态**：区分 `user_provided`、`database_native`、`paper_extracted`、`computed`、`model_predicted`、`hypothesis` 和 `unverified`。
- **默认可审查**：原始数据不覆盖，来源和 SHA256 写入 manifest，预测记录特征、目标、拆分规则和限制。
- **高成本操作有闸门**：远程、GPU、长时、批量、付费或破坏性操作必须先写出计划并等待确认。

## 快速开始

### 1. 获取代码并安装 Python 依赖

```bash
git clone https://github.com/gyuvdvxtjq/new-energy-agent.git
cd new-energy-agent

python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

核心数据工具使用 `numpy`、`pandas` 和 `scikit-learn`。`pymatgen` 与 `mp-api` 是可选依赖；当前 Materials Project 适配器使用官方 HTTP API，不安装它们也能运行核心流程。

### 2. 安装 Codex / Claude Code Skills

```bash
./install.sh
python3 scripts/install_check.py
```

安装脚本只在用户目录创建 Skills 符号链接：

- Codex：`${CODEX_HOME:-$HOME/.codex}/skills/new-energy-*`
- Claude Code：`$HOME/.claude/skills/new-energy-*`

Commands 保留在当前项目的 `commands/` 中，便于版本控制和审查。

### 3. 运行本地检查

```bash
python3 scripts/doctor.py
python3 scripts/self_test.py
python3 -m unittest discover -s tests -v
```

这些检查不需要网络、不需要 API key，也不会提交远程任务。

## 使用方式

### 在 Codex 或兼容 Agent 中使用

在项目目录打开 Agent，然后直接描述研究任务：

```text
/research 研究掺杂对层状氧化物正极循环稳定性的影响
/experiment 为这个问题设计一个可执行、可统计检验的实验方案
/predict 使用 datasets/ 下的数据预测第 50 周期容量
/review 审查这篇论文的实验方法、统计和 DFT 设置
/compute 为 structures/ 下的结构生成 DFT 计算计划
```

Agent 会先读取 `AGENTS.md`、项目规格和当前任务状态。对于信息不足但会改变方案的问题，它会先提问；轻量本地分析可以直接执行，远程计算则停在确认边界。

### 使用统一 CLI

统一入口 `new_energy_agent.py` 适合脚本化和面试现场演示：

```bash
python3 new_energy_agent.py --help
python3 new_energy_agent.py doctor
python3 new_energy_agent.py self-test

# 无网络的分组预测 smoke test
python3 new_energy_agent.py predict \
  --demo --group source_group --out /tmp/demo-metrics.json

# 检查一个 CSV 的质量和潜在泄漏
python3 new_energy_agent.py quality datasets/raw/NMC_numerical_new.csv \
  --target IC --out /tmp/ncm-quality.json

# 只生成远程计算计划，不执行 SSH/Slurm
python3 new_energy_agent.py compute-plan "relax structure and calculate band gap" \
  --structure structures/example.cif --method "静态 DFT" \
  --host my-cluster --out approvals/example-plan.json
```

其他确定性工具位于 `scripts/`：

| 脚本 | 用途 |
| --- | --- |
| `data_contract.py` | 无第三方依赖的 CSV 字段、缺失和重复预检 |
| `data_quality.py` | 目标列、分组列、缺失、重复和标识符风险检查 |
| `baseline_predict.py` | 数值特征 Random Forest 回归，支持分组切分 |
| `material_features.py` | 透明的化学式组成特征提取 |
| `query_materials_project.py` | 按 MP ID 或化学式查询 Materials Project |
| `merge_mp_features.py` | 将明确记录的 MP 特征合并到 NCM 演示数据 |
| `parse_dft_output.py` | 从 VASP 风格输出提取能量、费米能级、体积和收敛信号 |
| `compute_plan.py` | 生成等待用户确认的 SSH/Slurm 计划 |
| `evaluate_run.py` | 根据可审计产物计算工程准备度分数 |

## 公开数据与真实演示

### 一键材料演示

```bash
python3 scripts/run_material_demo.py --out-dir demo_run/material_demo
```

该演示使用公开的 `NMC_numerical_new.csv`（168 条 NCM 材料记录），完成数据质量检查和 IC/EC 回归基线。当前记录的结果为：

| 目标 | MAE | RMSE | R² |
| --- | ---: | ---: | ---: |
| 初始容量 `IC` | 7.7027 | 9.2659 | 0.9111 |
| 第 50 周期容量 `EC` | 6.9329 | 8.5348 | 0.8944 |

这些是随机切分的工程 smoke test，不是跨化学体系泛化结果。数据没有足够的材料/来源分组字段，正式研究应按材料、结构家族、来源或实验批次进行外推验证。

### 电芯循环数据演示

Zenodo 的 LG M50 电芯样例可以通过下载器和转换器处理：

```bash
python3 scripts/fetch_zenodo.py --record 4032561 \
  --filename LGM50_cell03.csv --out datasets/raw
python3 scripts/prepare_cycle_ml.py \
  --input datasets/raw/LGM50_cell03.csv \
  --out datasets/processed/LGM50_cell03_by_cycle.csv
```

下载器会保存来源、访问信息和 SHA256 manifest；这类数据用于验证循环时序处理，不能直接当作材料组成级标签。

### Materials Project 特征合并

```bash
# 查询一个明确的 MP 记录
python3 scripts/query_materials_project.py \
  --material-id mp-149 --out reports/mp-149.json

# 对演示数据中 M == 0 的记录做明确标注的近似合并
python3 scripts/merge_mp_features.py \
  --out reports/ncm_mp_features.csv
```

合并结果会同时写入 `reports/ncm_mp_features.manifest.json`。由于原始 NCM 表缺少 MP ID、完整掺杂元素和结构信息，当前规则固定 `O2`，按 `Li-Ni-Co-Mn-O` 化学体系组成距离选择候选，并把每一行标为 `nearest_chemsys_candidate_requires_review`。这一步是数据连接演示，不应被解释为精确结构同一或新的实验标签。

数据来源和字段限制见 [`datasets/SOURCES.md`](datasets/SOURCES.md) 与 [`datasets/schema.md`](datasets/schema.md)。

## Materials Project 配置

API key 只保存在本机项目根目录的 `.env`，不要写入 Git、报告、日志或聊天记录：

```bash
cp .env.example .env
chmod 600 .env
```

编辑 `.env`：

```dotenv
MP_API_KEY=your_materials_project_key
```

脚本会优先读取进程环境变量，再读取项目 `.env`。配置检查：

```bash
python3 scripts/doctor.py
```

`.env` 已加入 `.gitignore`。如果 key 曾经出现在 shell 历史、日志或聊天记录中，应立即在服务商后台撤销并重新生成。

## 远程 DFT 与确认边界

项目不假装拥有用户的集群、账户、队列或私钥。先生成计划：

```bash
python3 new_energy_agent.py compute-plan \
  "relax and calculate DOS" \
  --structure structures/sample.cif \
  --method "用户指定的 VASP/QE/ABACUS 方法" \
  --host my-cluster \
  --out approvals/sample-plan.json
```

计划包含目标、结构、方法、主机别名、调度器、资源待确认项、输出文件和失败策略，并明确 `submitted: false`。只有用户确认后，Agent 才可以使用用户现有的 SSH 配置继续执行。项目不读取、复制或写入 SSH 私钥，也不会无限自动重试远程任务。

## 输出和可追溯性

```text
AGENTS.md                 项目规则和科研边界
commands/                 Codex/Claude Code 入口
skills/                   五个可安装科研 Skill
agents/                   研究、实验、数据、计算、审查角色
workspace/                当前任务、日志和结构化交接
datasets/                 数据契约、来源、原始和处理数据
papers/                   文献原始文件和元数据
structures/               CIF/POSCAR 等结构输入
calculations/             计算输入、任务日志和结果
reports/                  质量、预测、审查和演示报告
approvals/                需要确认的计算计划
scripts/                  确定性科学工具
tests/                    本地自动化测试
```

每个科学结论都应能够回到一个输入文件、来源记录、脚本参数、运行日志或用户确认。原始数据与清洗产物分开保存，避免覆盖原始证据。

## 评估与验证

工程准备度可以通过以下命令检查：

```bash
python3 new_energy_agent.py evaluate \
  --root . --out reports/evaluation.json
```

这个分数只衡量项目是否具备规格、来源、质量检查、泄漏控制、测试、DFT 解析器和演示产物等工程证据，不等于科学有效性评分。科学结论仍需要材料体系分组验证、方法核查、实验或计算复现和领域专家审查。

完整验收记录见 [`ACCEPTANCE.md`](ACCEPTANCE.md)。

## 限制

- 当前预测基线只处理数值特征，尚未替代结构模型、图神经网络或严格的化学外推基准。
- NCM 演示数据的随机切分只能说明脚本链路可运行，不能证明跨材料、跨来源或跨实验协议的泛化。
- Materials Project 是数据库原生计算数据，不能直接当作实验测量值；不同数据库的计算协议也不能未经说明直接混合。
- NCM 到 MP 的当前连接因原始表缺少结构标识而是近似映射，必须人工复核。
- 论文检索和审查工作流提供证据组织与问题清单，不会自动保证引用真实性或替代同行评议。
- 真实 SSH/Slurm、GPU、长时计算和付费资源依赖用户自己的基础设施，并受确认闸门约束。
- 项目不包含 Web 前端、账号系统、模型 API 代理、PPT 生成或 Manim 工作流。

## 设计参考

本项目借鉴公开项目和社区经验的**接口与工程思想**，没有复制第三方实现：

| 参考 | 借鉴点 | 在本项目中的落地 |
| --- | --- | --- |
| [OpenAI4S](https://github.com/PKU-YuanGroup/OpenAI4S) | 编排层与持久化科学执行层分离、产物和运行记录可恢复 | Agent Markdown 编排 + 独立 Python 科学脚本 + `workspace/` 产物 |
| [deep-research](https://github.com/dzhng/deep-research) | 问题拆解、迭代检索、来源归因和 Markdown 报告 | `/research` 工作流、`papers/`、证据状态和报告协议 |
| [Open Deep Research](https://github.com/langchain-ai/open_deep_research) | 可配置的研究计划和工具调用边界 | Commands/Skills 分层，按任务选择工具，不把所有能力塞进一个 prompt |
| [atomate2](https://github.com/materialsproject/atomate2) | 计算工作流、输入输出和任务状态显式化 | 计算计划、审批文件、任务日志和结果解析 |
| [dflow](https://github.com/deepmodeling/dflow) / [DP-GEN](https://github.com/deepmodeling/dpgen) | 材料计算中的可复现流程、资源调度和失败恢复意识 | SSH/Slurm 计划、资源估计、失败策略和不无限重试 |
| LinuxDo 科研 Agent 讨论 | 规划、执行、审查分离；使用 Markdown 中间产物；跨会话保留状态 | `AGENTS.md`、`commands/`、`skills/`、`workspace/` 和交接 schema |

更完整的链接、数据源和社区记录见 [`REFERENCES.md`](REFERENCES.md)。

## 面试演示建议

一次完整演示可以按以下顺序进行：

1. `python3 scripts/doctor.py`：展示项目能力诊断和可选依赖状态。
2. `python3 scripts/run_material_demo.py`：展示公开 NCM 数据的质量检查和基线指标。
3. `python3 scripts/merge_mp_features.py --out /tmp/ncm_mp.csv`：展示真实 Materials Project 查询、来源状态和近似映射警告。
4. `python3 new_energy_agent.py compute-plan ...`：展示远程 DFT 在提交前停在用户确认边界。
5. 打开 `reports/`、`demo_run/` 和 `TASKS.md`：展示结果、限制和任务状态都被写入文件，而不是只存在于对话中。

这条路径能同时展示 Agent 编排、科研数据纪律、可复现基线、外部数据库接入和计算安全边界。
