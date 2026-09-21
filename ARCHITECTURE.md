# 架构

## 总体结构

```text
Codex / Claude Code
        │
        ├── AGENTS.md：项目规则
        ├── commands/：用户入口
        ├── skills/：科研工作流说明
        └── agents/：专门角色和交接协议
                │
                ▼
        workspace/：任务状态与中间产物
                │
                ▼
        scripts/：确定性科学执行
                │
                ├── 文献与证据
                ├── 材料结构与属性
                ├── 数据分析与基线
                ├── DFT 输出解析
                └── SSH/Slurm 命令生成
```

## 三种编排模式

### 研究助手

问题澄清 → 关键词拆解 → 文献检索 → 证据筛选 → 假设 → 实验问题 → 论文产物。

### 数据分析

文件识别 → 数据契约 → 单位和质量检查 → 泄漏检查 → 基线 → 评估 → 不确定性 → 科学解释。

### 计算编排

结构与目标检查 → 方法和参数计划 → 资源估计 → 输入文件 → 用户确认 → SSH/Slurm → 状态监控 → 结果解析 → 收敛和物理检查。

## 工作区结构

```text
workspace/
├── current_task.yaml
├── task_log.md
└── handoffs/
papers/          原始论文和元数据
extracted/       解析后的文本和表格
datasets/        原始数据和标准化数据
structures/      CIF/POSCAR 等结构文件
calculations/    计算输入、输出和任务清单
reports/         最终报告
scripts/         确定性脚本
logs/            命令和运行日志
approvals/       用户确认记录
```

## 状态机

```text
draft → needs_clarification → planned → waiting_user_approval
      → running → partially_completed → needs_human_review
      → completed / failed / cancelled
```

子 Agent 的交接必须符合 `workspace/handoff.schema.json`，至少写明完成步骤、发现、未知项和下一步，不能只返回一段自然语言。

## 证据状态

`user_provided`、`database_native`、`paper_extracted`、`verified_human`、`computed`、`model_predicted`、`hypothesis`、`unverified`。

## 工具适配原则

优先适配成熟工具：pymatgen、ASE、matminer、Materials Project、JARVIS、Matbench、atomate2/jobflow、AiiDA、VASP、Quantum ESPRESSO、ABACUS、DeepMD/DP-GEN 和 Slurm。Agent 只负责选择、配置、调用和解释，不重写这些工具的科学内核。

## 执行确认

本地只读或轻量任务直接执行。GPU、远程、长时、付费、批量或破坏性操作必须生成 `approvals/<task-id>.md`，展示命令、输入、输出、资源、风险和失败策略，等待用户确认。
