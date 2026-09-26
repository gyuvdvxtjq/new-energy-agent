# new-energy-agent

一个垂直领域的 Agent 运行时，场景是电池材料科研：数据 → 特征 → 预测 → 云端 DFT → 证据链报告。运行时本身与场景解耦，场景只决定工具面上挂载了哪些工具。

```
┌──────────────────────────────────────────────────────────────┐
│  宿主 Agent (Claude Code / Codex / 任意 MCP 客户端)            │
│  读 AGENTS.md（薄剧本：路由/提问规则/证据纪律——只有知识,没有权力）│
└──────────────┬───────────────────────────────────────────────┘
               │ MCP (stdio JSON-RPC)          CLI (人类/CI 通道)
┌──────────────▼───────────────────────────────────────────────┐
│  neagent 运行时（唯一强制点）                                   │
│  ├─ state.py    任务状态机：非法转换代码层直接拒绝               │
│  ├─ gate.py     审批闸门：付费操作必须有人类确认记录             │
│  └─ gateway.py  工具网关：权限分级 + 审计日志 + 状态推进          │
├──────────────────────────────────────────────────────────────┤
│  core/（确定性 Python，可脱离 Agent 独立跑）                     │
│  ├─ data.py / features.py / models.py   预测链（防泄漏切分）     │
│  ├─ abacus.py  ABACUS 输入生成 / SSH 执行 / 结果解析             │
│  └─ evidence.py  SHA256 manifest + 证据分级报告                 │
├──────────────────────────────────────────────────────────────┤
│  workspace/  任务状态/审批记录/证据 manifest 全部落盘 → 可恢复可审计│
└──────────────────────────────────────────────────────────────┘
```

## 这个项目解决什么问题

用 LLM 驱动科研工作流有一对绕不开的矛盾：驱动者（模型的指令遵循能力）不可靠，被驱动的动作（付费计算、科研记录）却必须可靠。

如果把任务纪律写在提示词或 Markdown 里，约束力来自模型自觉——换一个不守规矩的模型，整套纪律就失效了。所以这个项目的前提是：凡是必须对的东西，不能请求模型配合，只能在代码层强制。模型只保留它擅长的三件事——理解需求、规划步骤、解释结果，其余全部交给确定性代码：

| 必须可靠的事 | 由谁强制 | 位置 |
| --- | --- | --- |
| 任务状态流转 | 状态机 | `runtime/state.py` |
| 付费操作边界 | 审批闸门 | `runtime/gate.py` |
| 工具权限与能力面 | 工具网关 | `runtime/gateway.py` |
| 结果可审计 | 证据清单 | `core/evidence.py` |

`AGENTS.md` 只提供"怎么把活干对"的知识，并在开头声明自己不授予任何绕过能力。

## 运行时如何强制纪律

模型可调用的全部 17 个工具只有一个执行出口：`ToolGateway.dispatch`。MCP server 与 CLI 最终都汇入这一个函数，没有旁路。每次调用按固定次序执行：

1. 先写审计日志——在任何校验之前。被拦截的调用恰恰是最需要留痕的。
2. 付费工具先过闸门（含内容指纹重验）：没有 `APPROVED` 且指纹匹配的审批记录直接抛 `GateBlockedError`，连状态检查都到不了。
3. 状态契约检查：每个工具声明自己的合法状态；终态只放行只读访问。
4. 执行成功（结果 `ok=True`）后，按工具声明的 `success_trigger` 经状态机翻转任务状态——失败的结果不会推进状态。

这样，越界行为在代码层不可达，而不只是被"拒绝"：模型面前没有自我审批按钮，没有触碰他人作业的通道，没有让状态非法跳转的口子。三个强制点：

- 状态机（`state.py`）：9 个状态 + 显式转换表，是唯一允许修改任务状态的代码。终态（completed/cancelled）无出边，被彻底冻结；`failed` 保留 `resume → planned` 一条恢复路径，用于崩溃续跑。YAML 原子落盘（先写临时文件再替换）。
- 审批闸门（`gate.py`）：付费工具的执行以磁盘上一个 Markdown 批准文件为前提。**审批绑定内容**：`dft.plan` 在批准文件里记录输入文件的 SHA256 指纹，`dft.run` 执行前重验指纹，重新规划会重置批准状态——为 A 内容签发的人工决策永远无法放行 B 内容。"批准"这个动作故意不封装成工具，只能由人编辑该文件或运行 `neagent gate approve`，模型无法自我审批。
- 远程命名空间与预算：`dft.run` 只在用户机器的 `~/neagent/<task_id>/` 内读写（task_id 经白名单字符校验，不可能夹带 shell 语法）；`dft.plan` 在原子数超出 `profile.budget.max_atoms` 时直接拒单。"不动命名空间之外的东西""不超预算"是代码行为，不是口头约定。

`selfcheck` 用 13 条断言验证上述性质；`tests/` 含 44 个用例，其中对抗性护栏测试专门断言"未审批必拒、过期/换内容审批必拒、自审批不可达、失败不推进状态、compute 不得绕过审批"。

## 两条业务链

预测链 `data.quality → features.derive → models.baseline`：

数据质量预检（标识列滥用、泄漏风险、目标列核对）→ 组分特征（不依赖 pymatgen 的透明解析）→ RandomForest 基线。这条链的价值不在指标，而在诚实：无分组列时报告明确写"随机切分、仅冒烟测试、不得外推"，不同切分规则的差异如实记录，而不是只给出一个好看的 R²。`profiles/` 下挂了两个场景证明可插拔：`ncm`（材料级配方 → 初始容量）和 `lgm50`（电芯级循环时序 → 容量，按循环圈分组切分）。

计算链 `dft.plan → [人类审批] → dft.run → dft.parse → evidence.report`：

从可插拔的 YAML 配方（`profiles/`，换材料体系只需加一个文件）生成真实 ABACUS 输入（STRU/INPUT/KPT/赝势/轨道），然后停下来等人类批准。执行通道是**用户自己提供的 SSH 机器**（`NEAGENT_SSH_HOST/USER/KEY` 等凭证只进 `.env`）：`dft.run` 把输入上传到该机器的 `~/neagent/<task_id>/`，跑 SCF，打包取回结果——整个远程 namespace 固定，凭指纹通过闸门后才放行。计算花费的是用户自己机器的机时，不经手任何云平台账号。

两条链都贯穿证据纪律：每个结果附带 SHA256 清单和证据等级。把 ABACUS/LDA 的计算值与 Materials Project/PBE 的数据库值并排呈现时，`evidence.py` 会主动标注"计算口径不同、不可直接比较"并列出后续对齐步骤，而不是把预期差异包装成"验证通过"。

## 3 分钟跑通

```bash
git clone https://github.com/gyuvdvxtjq/new-energy-agent && cd new-energy-agent
pip install -e .          # 或 PYTHONPATH=src 配合 Python 3.10+

# 1) 护栏自检：非法转换被拒 / 未审批提交被拒 / 审计落盘
python -m neagent.cli selfcheck

# 2) 预测链端到端（NCM 数据，无任何外部依赖）
python -m neagent.cli demo predict

# 3) 全部测试（含对抗性护栏测试）
python -m unittest discover -s tests
```

作为 MCP server 接入任意客户端：

```json
{"command": "python", "args": ["-m", "neagent.mcp_server"]}
```

## 已验证：真实端到端执行

2026-09-26，运行时驱动的完整 compute 链路在真实环境跑通：

```
task.init → plan → dft.plan（生成真实 ABACUS 输入+审批请求）
→ gate approve（人类通道）→ dft.run（上传 SSH 机器）
→ mpirun abacus（Si 原胞 SCF，7 次迭代收敛，墙钟 5s）
→ 取回 → dft.parse → finish → evidence.report（SHA256 manifest）→ completed
```

- 结果：Etot = -213.6646 eV（Si 2 原子，LCAO/LDA），证据等级 `computed`，与 Materials Project mp-149 出了对照报告（口径差异如实标注，见 [`reports/first_dft_si/REPORT.md`](reports/first_dft_si/REPORT.md)）。
- 真机暴露了 5 个单测抓不到的 bug：LCAO 原子数解析、轨道文件漏拷、ABACUS 3.x 收敛措辞变化、终态拦截只读工具、节点 shell 横幅污染 SFTP，已全部修复并补了回归测试。这也是这个项目的方法论：单测证明代码符合设计，真机证明设计符合现实，两者缺一不可。

## 工具面

模型能看到的全部能力。注意表里没有 `gate.approve` 和 `task.confirm`——审批只存在于人类通道（`neagent gate approve` 或手编 approvals 文件）。

| 工具 | 权限 | 状态约束 | 说明 |
| --- | --- | --- | --- |
| task.init / status / list | 写 / 读 | — | 任务生命周期 |
| task.plan / execute / finish / resume / cancel / reject / revise | 写 | 各有合法前置态 | 仅状态翻转；execute 只对本地工作流开放 |
| data.quality | 读+写 | planned/running | 质量+泄漏预检报告 |
| features.derive | 读+写 | planned/running | 组分特征（透明解析，不用 pymatgen） |
| models.baseline | 写 | running | RF 基线，切分规则如实写入报告 |
| dft.plan | 写 | planned | 生成真实 ABACUS 输入 + 审批请求（绑定内容指纹） |
| **dft.run** | **付费+闸门** | **approved** | SSH 上传执行+取回，未审批物理不可达 |
| dft.parse | 读+写 | running/needs_review | 收敛/能量提取 → 证据分级 |
| evidence.report | 写 | needs_review | SHA256 manifest（+ computed vs database_native），两条链都由此收尾到 completed |

## 安全边界

- 审批闸门：`dft.run` 先验 approvals 文件（PENDING/MISSING/指纹不符一律拒绝），再查任务状态（必须 approved）。拦截行为全部进审计日志。
- 内容绑定：审批记录携带计划输入的 SHA256 指纹；执行前重验，重新规划自动重置为 PENDING——人工决策无法被复用到不同内容上。
- 远程命名空间：SSH 通道只在用户机器的 `~/neagent/<task_id>/` 内读写，task_id 强制 `[A-Za-z0-9._-]+` 白名单。
- 预算护栏：plan 阶段超出 profile 原子数预算直接拒绝——调预算是用户的决定，不是 agent 的。
- 密钥纪律：`MP_API_KEY` / SSH 凭证只进 `.env`，不进代码、日志、manifest。
- 诚实性：随机切分只声明为 smoke test；ABACUS-LDA 与 MP-PBE 的能量差异在报告里显式标注为"预期、不可直接比较"，不粉饰成验证成功。

## 架构与 Roadmap

分层设计、状态机转换表、执行通道的取舍，详见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

下一步：

- CHGNet/DPA4 等 MLIP 扩展（可一次演示三种证据等级：computed / model_predicted / database_native）
- pymatgen 结构特征 + 乱序/带括号化学式解析
- Materials Project 同口径总能量对比（`MP_API_KEY` 已预留）
- 文献证据链 / exp pxrd

## 许可

MIT
