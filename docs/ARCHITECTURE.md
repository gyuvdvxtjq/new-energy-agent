# neagent v2 架构

> 一句话：**LLM 负责理解、规划和解释；任务生命周期、工具权限、付费边界全部由代码强制执行。**
> 垂直场景是电池材料科研，但运行时本身与场景解耦——场景只是"给工具面填充了什么"。

## 1. 四层结构与职责

| 层 | 内容 | 为什么必须存在 |
| --- | --- | --- |
| 宿主 Agent + AGENTS.md | 薄剧本：路由、提问规则、证据纪律 | LLM 需要引导，引导要可版本化。**故意薄**——只有知识，没有权力 |
| **运行时（runtime/）** | 状态机 + 审批闸门 + 工具网关 + 审计日志 | 项目的主体。LLM 干活的唯一通道是网关 dispatch，非法操作代码层直接拒绝 |
| core/（确定性 Python） | data/features/models（预测链）、abacus/sshrun（compute 链）、evidence（证据链） | 可脱离 agent 独立跑（CI/脚本）；MCP 只是它的壳 |
| workspace/ + 测试 | 状态/审批/manifest 全落盘；护栏测试 | 落盘 = 可恢复 + 可审计；测试 = 护栏不是纸面宣传 |

## 2. 状态机（runtime/state.py）

9 个状态，显式转换表，**这是唯一允许修改任务状态的代码**：

```
draft ──plan──▶ planned ──request_submit──▶ waiting_approval ──confirm──▶ approved
                  │  ▲        (dft.plan)          │  ▲      (人类通道)      │
                cancel  reject                   │  └─ reject ──▶ planned  │
                  ▼  │（人类拒绝）               cancel                    execute
              cancelled                          ▼                        ▼
                                                 cancelled              running ──finish──▶ needs_review
                                                                          │                    │
                                                                        fail               accept│revise
                                                                          ▼                    ▼ ▼
                                                                        failed ──resume──▶ planned   completed/planned
```

- `LOCAL_SHORTCUTS`：planned→running 直达，**只对本地工作流（predict/compare）开放**——网关对 `workflow=="compute"` 的任务传 `allow_local_shortcut=False`，state.py 里也独立再拒一次。compute 通往 running 的唯一路径是 `dft.run`（approved→running，付费且过闸门）。
- 终态冻结：completed/cancelled 无出边；failed 保留 resume/cancel 恢复路径。
- task_id 同时是本地路径段和远程 `~/neagent/<id>` 命名空间，因此强制 `[A-Za-z0-9._-]+`（纯点号也拒）——在 state 层校验，所有读写在进入 store 之前就过了这道闸。
- 一个教学案例：终态曾把只读工具（task.status）也一并拦掉，首跑真机时发现，已修复为终态放行只读。

## 3. 工具网关（runtime/gateway.py）

每次 dispatch 的固定次序：**先审计（被拦截的调用也要留痕）→ 付费工具先过闸门（含内容指纹重验）→ 状态契约检查（含终态只读豁免）→ 执行 → 结果校验后推进状态 → 记 step**。

工具声明式权限：`read / write / network / paid / gated / allowed_states / success_trigger / ok_key / content_paths_resolver`。后两个是 v2 护栏加固的结果：

- `ok_key`：工具返回 `ok=False` 时抛 `ToolFailedError` 且**状态机不前进**——"调用返回了"不等于"成功了"。
- `content_paths_resolver`：gated 工具在 dispatch 时算出待执行内容的指纹并交给闸门重验。

MCP 的 tools/list 直接暴露这份清单。清单里没有 gate.approve / task.confirm，**agent 物理无法自我审批**，且有测试钉死这一性质。

## 4. compute 链与执行通道

`dft.plan` 从 profile（材料体系可插拔：换体系 = 加一个 YAML）生成真实 ABACUS 输入（STRU/INPUT/KPT/赝势/轨道，原子数超预算直接拒单）+ 审批请求（绑定输入指纹）。随后：

1. **人类审批**：编辑 approvals 文件或 `neagent gate approve`（闸门只放 PENDING→APPROVED；重规划会重写请求并重置为 PENDING，旧决策不残留）。
2. **`dft.run`（唯一付费工具）**：闸门重验指纹 → 状态检查（必须 approved）→ SSH 上传 → 远程 SCF → 打包取回。

执行通道只有一条：**用户自己提供的 SSH 机器**（`core/sshrun.py`）。远程 namespace 固定在 `~/neagent/<task_id>/`，`np_mpi` 在拼进命令行之前被强转成有界整数（CLI 通道的参数一律是字符串，不校验就是远程命令注入）。SFTP 被节点 shell 横幅污染时自动回退到流式通道（stdin 上传 / base64 带标记下载）。

> 历史注记：v2 曾以 Bohrium job submit 为主通道（`bohr.*` 工具族 + `job_ids` 白名单 + `BOHRIUM_PROJECT_ID`）。SSH 通道是首次真机验证时走的路线，跑通后反过来取代了云通道——计算花的是用户自己的机时，不经手任何云平台账号、不存放计费凭证。旧代码见 git 历史。

## 5. 证据链（core/evidence.py）

SHA256 manifest 覆盖任务的全部产物（`evidence.report` 递归收集 outputs/）；`compare_report` 把 computed 与 database_native 并排，口径不同（LDA vs PBE）时显式标注"不可直接比较"并列出 next_checks。诚实是结构性的，不是靠提示词请求来的。

## 6. v1 → v2 的演化（保留，这是设计判断的来源）

| | v1 | v2 |
| --- | --- | --- |
| 编排 | 三套层（commands/skills/agents）描述同一批工作流 | 一份薄剧本 `AGENTS.md` |
| 纪律 | 状态机/审批/交接全在 Markdown，靠模型自觉 | 全部下沉为代码强制 |
| 文档 vs 代码 | 9 份治理文档 vs 940 行薄脚本 | 3 份文档，代码为主 |
| 工作流 | 5 个广而浅 | 2 条深链 + 证据链贯穿 |
| DFT | 只写 JSON 计划不真算 | 真实 ABACUS 全链路，已跑通 |

核心教训：**把"必须可靠"的东西交给提示词，等于把可靠性绑定在模型的指令遵循能力上**——换一个不守规矩的模型，整套审批与状态纪律当场失效。v2 把这些性质搬进代码后，它们变成了可以断言、可以测试的东西（selfcheck 13 条 + tests/ 44 例，其中对抗性测试专门攻击"换内容审批、旧审批复用、失败推进状态、compute 绕过审批"这些侧门）。
