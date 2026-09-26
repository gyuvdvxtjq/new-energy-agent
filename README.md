# new-energy-agent

> **一个把 LLM 关进代码笼子的垂直领域 Agent 运行时。**
> 模型负责理解、规划和解释；任务生命周期、工具权限、付费边界全部由代码强制执行。
> 垂直场景：电池材料科研（数据 → 特征 → 预测 → 真实云端 DFT → 证据链报告）。

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
│  ├─ bohr.py    ABACUS 输入生成 / dry-run / 提交 / 解析（job 或 SSH 通道）│
│  └─ evidence.py  SHA256 manifest + 证据分级报告                 │
├──────────────────────────────────────────────────────────────┤
│  workspace/  任务状态/审批记录/证据 manifest 全部落盘 → 可恢复可审计│
└──────────────────────────────────────────────────────────────┘
```

## 为什么是现在这个形态（v1 的教训）

v1 把状态机、审批边界、交接协议全写在 Markdown 里，靠宿主 LLM "自觉遵守"。
结论：**用最不确定的组件（LLM 的指令遵循）去保证最需要确定性的东西（科研可审计性），
是不成立的**——换一个不守规矩的模型，整套纪律就失效了。v2 把"必须遵守"的部分
下沉为代码：状态机是唯一的转换入口，付费工具是唯一被闸门保护的提交通道，
Agent 的工具面上**物理不存在**"自我审批"这个能力（见下方测试断言）。
完整设计推演见 `docs/ARCHITECTURE.md`。

## 3 分钟跑通

```bash
git clone https://github.com/gyuvdvxtjq/new-energy-agent && cd new-energy-agent
pip install -e .          # 或直接 PYTHONPATH=src 配合现有 Python 3.10+

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

## 已验证：真实端到端执行（不是纸面架构）

2026-09-26，运行时驱动的完整 compute 链路在真实环境跑通：

```
task.init → plan → bohr.plan（生成真实 ABACUS 输入+审批请求）
→ gate approve（人类通道）→ execute → SSH 上传节点
→ mpirun abacus（Si 原胞 SCF，7 次迭代收敛，墙钟 5s）
→ 取回 → dft.parse → finish → evidence.report（SHA256 manifest）→ completed
```

- 结果：Etot = **-213.6646 eV**（Si 2 原子，LCAO/LDA），证据等级 `computed`，
  与 Materials Project mp-149 出对照报告（口径差异如实标注，详见
  [`reports/first_dft_si/REPORT.md`](reports/first_dft_si/REPORT.md)）
- **真机暴露了 5 个单测抓不到的 bug**（LCAO 原子数解析、轨道文件漏拷、
  ABACUS 3.x 收敛措辞漂移、终态拦截只读工具、节点 shell 横幅污染 SFTP）——
  全部修复 + 回归测试。"纸面测试 + 真实执行各抓不同的坑"是这个项目的核心方法论
- 每一步的状态转换、审批、审计日志都落盘在 `workspace/`，可完整回放

## Agent 工程概念 → 本项目的落地实现

| 概念 | 在哪里 |
| --- | --- |
| **Guardrails** | 工具网关权限分级（read/write/network/paid）、资源白名单、预算拒单 |
| **Human-in-the-loop** | 审批闸门：付费工具先过 approvals 文件 + `approved` 状态双重检查；agent 工具面上物理不存在自我审批能力 |
| **Tool calling** | 14 个 schema 化工具经 MCP (stdio JSON-RPC) 或 CLI 暴露，唯一入口是网关 dispatch |
| **State management** | 9 状态显式转换表 + YAML 持久化，非法转换代码层直接拒绝 |
| **Crash recovery** | `failed → resume → planned`，任务产物/状态全落盘，断点续跑 |
| **Agent evals** | 测试套件中的对抗性用例断言护栏真的拦得住（未审批必拒、非白名单必拒、自审批不可达） |

## 工具面（Agent 能看到的全部能力）

| 工具 | 权限 | 状态约束 | 说明 |
| --- | --- | --- | --- |
| task.init / status / list | 写 / 读 | — | 任务生命周期 |
| task.plan / execute / finish / resume / cancel / reject | 写 | 各有合法前置态 | 仅状态翻转 |
| data.quality | 读+写 | planned/running | 质量+泄漏预检报告 |
| features.derive | 读+写 | planned/running | 组分特征（透明解析，不用 pymatgen） |
| models.baseline | 写 | running | RF 基线，切分规则如实写入报告 |
| bohr.plan | 写 | planned | 生成真实 ABACUS 输入 + job.json + 审批请求 |
| bohr.dryrun | 读+网络 | planned/waiting/approved | CLI dry-run 校验，零成本 |
| **bohr.submit** | **付费+闸门** | **approved** | 真实提交，未审批物理不可达 |
| bohr.status / fetch | 读+网络 | 任意 / running | **只操作本任务 job_ids 白名单** |
| dft.parse | 读+写 | running/needs_review | 收敛/能量提取 → 证据分级 |
| evidence.report | 写 | needs_review | SHA256 manifest + computed vs database_native |

注意表里**没有** `gate.approve` 和 `task.confirm`——审批只存在于人类通道：

```bash
python -m neagent.cli gate approve <task_id>   # 或手工编辑 approvals/<task_id>.md
```

## 安全边界

- **审批闸门**：`bohr.submit` 先查 approvals 文件（PENDING/MISSING 一律拒绝），
  再查任务状态（必须 approved）。拦截行为全部进审计日志。
- **资源白名单**：运行时只触碰本任务 `job_ids` 里登记过的 Bohrium 任务——
  "agent 不能动不属于它的资源"是代码行为，不是口头约定。
- **预算护栏**：plan 阶段按原子数路由机型并估算费用，超出 profile 预算直接拒绝
  （预算调整是用户决定，不是 agent 决定）。
- **密钥纪律**：`MP_API_KEY` / `BOHRIUM_PROJECT_ID` / SSH 凭证只进 `.env`，
  不进代码、日志、manifest。
- **诚实性**：随机切分只声明为 smoke test；ABACUS-LDA vs MP-PBE 的能量差异
  在报告里显式标注为"预期、不可直接比较"，而不是粉饰成验证成功。

## Roadmap

- CHGNet/DPA4 等 MLIP 扩展（GPU 机型路由已预留，一次演示三种证据等级：
  computed / model_predicted / database_native）
- pymatgen 结构特征 + 乱序/带括号化学式解析
- Materials Project 同口径总能量对比（MP_API_KEY 已预留）
- bohr lkm 文献证据链 / exp pxrd

## 演化

v1（tag `v1-final`）：Markdown 编排 + 5 个广而浅的工作流。
v2：收敛为一条深链 + 代码强制运行时。**架构是怎么从踩坑里长出来的，
和架构本身一样重要。**
