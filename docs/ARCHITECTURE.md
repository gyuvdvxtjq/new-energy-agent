# neagent v2 架构

> 一句话：**LLM 负责理解、规划和解释；任务生命周期、工具权限、付费边界全部由代码强制执行。**
> 垂直场景是电池材料科研，但运行时本身与场景解耦——场景只是"给工具面填充了什么"。

## 1. 四层结构与职责

| 层 | 内容 | 为什么必须存在 |
| --- | --- | --- |
| 宿主 Agent + AGENTS.md | 薄剧本：路由、提问规则、证据纪律 | LLM 需要引导，引导要可版本化。**故意薄**——只有知识，没有权力 |
| **运行时（runtime/）** | 状态机 + 审批闸门 + 工具网关 + 审计日志 | 项目的主体。LLM 干活的唯一通道是网关 dispatch，非法操作代码层直接拒绝 |
| core/（确定性 Python） | data/features/models（预测链）、bohr/sshrun（compute 链）、evidence（证据链） | 可脱离 agent 独立跑（CI/脚本）；MCP 只是它的壳 |
| workspace/ + 测试 | 状态/审批/manifest 全落盘；护栏测试 | 落盘 = 可恢复 + 可审计；测试 = 护栏不是纸面宣传 |

## 2. 状态机（runtime/state.py）

9 状态，显式转换表，**这是唯一允许修改任务状态的代码**：

```
draft ──plan──▶ planned ──request_submit──▶ waiting_approval ──confirm──▶ approved
                  │  ▲        (bohr.plan)        │  ▲      (人类通道)      │
                cancel  reject                   │  └─ reject ──▶ planned  │
                  ▼  │（人类拒绝）               cancel                    execute
              cancelled                          ▼                        ▼
                                                 cancelled              running ──finish──▶ needs_review
                                                                          │                    │
                                                                        fail               accept│revise
                                                                          ▼                    ▼ ▼
                                                                        failed ──resume──▶ planned   completed/planned
```

- `LOCAL_SHORTCUTS`：轻量本地工作流允许 planned→running 直达（非付费工具）
- 终态冻结：completed/cancelled 无出边；failed 保留 resume/cancel 恢复路径
- 运行时教学案例：终态曾把只读工具（task.status）也拦掉——首跑真机发现，已修复为终态放行只读

## 3. 工具网关（runtime/gateway.py）

每次 dispatch 的固定次序：**先审计（被拦截的调用也要留痕）→ 付费工具先过闸门 →
状态契约检查（含终态只读豁免）→ 执行 → success_trigger 经状态机推进 → 记 step**。

工具声明式权限：`read / write / network / paid / gated / allowed_states / success_trigger`。
MCP 的 tools/list 直接暴露这份清单——注意清单里没有 gate.approve / task.confirm，
**agent 物理无法自我审批**，且有测试钉死这一性质。

## 4. compute 链与真实执行通道

`bohr.plan` 从 profile（材料体系可插拔：换体系=加一个 YAML）生成真实 ABACUS 输入
（STRU/INPUT/KPT/赝势/轨道，原子数超预算直接拒单）+ job.json + 审批请求。
两条执行通道：

1. **job submit**（架构正道）：dry-run 校验 → 人工审批 → `bohr.submit`（唯一付费工具）→ fetch（JobId 白名单强制）
2. **SSH**（用户提供机器）：sshrun.py，凭证仅经环境变量；SFTP 被 shell 横幅污染时自动回退流式通道

## 5. 证据链（core/evidence.py）

SHA256 manifest 覆盖输入/输出；`compare_report` 把 computed 与 database_native 并排，
口径不同（LDA vs PBE）显式标注"不可直接比较"并列出 next_checks——诚实是结构性的，
不是靠提示词请求来的。

## 6. v1 → v2 的教训（保留，这是演化故事）

| v1 的问题 | v2 的对策 |
| --- | --- |
| 三套编排层（commands/skills/agents）描述同一批工作流 | 合并为 AGENTS.md 一份薄剧本 |
| 状态机/审批/交接协议全在 Markdown 里，靠模型自觉 | 全部下沉为代码强制 |
| 9 份治理文档 vs 940 行薄脚本 | 文档 3 份（README/本档/AGENTS），代码为主 |
| 5 个广而浅的工作流 | 收敛为 2 条深链 + 证据链贯穿 |
| 纸面 DFT 计划（只写 JSON 不真算） | 真实 ABACUS 全链路，已跑通 |
