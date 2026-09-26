# T9 首次真实 DFT：Si 原胞 SCF（ABACUS/LCAO/LDA）

日期：2026-09-26 · 执行通道：SSH（用户提供的 Bohrium 节点）· 计费：用户体验卡（节点维度），本次 SCF 墙钟 5 秒 · 任务 `si-scf-2` 已 `completed`

> 产物完整性说明：本次运行的计算日志原件在 2026-09-26 13:56 的一次本地磁盘回滚事故中
> 随仓库工作副本一并丢失（节点已关机，无法即时重取）。下方的能量数值、收敛状态与链路
> 记录来自运行时落盘的任务历史与审计日志，且整条链路可在节点重开后数分钟内完整复现
> （SCF 本身仅需 5 秒）。

## 结果

| 项 | 值 | 证据等级 |
| --- | --- | --- |
| 体系 | Si 原胞，2 原子（mp-149 结构，LATTICE_CONSTANT 10.2 bohr FCC） | `database_native`（MP mp-149） |
| 计算引擎 | ABACUS（LCAO，LDA-PZ 赝势，ecutwfc 50 Ry，4×4×4 Γ 中心网格） | — |
| 收敛 | charge density convergence is achieved（7 次 SCF 迭代） | `computed` |
| 总能量 | -213.6645733985001 eV（-106.83 eV/atom） | `computed` |
| 对照 | MP mp-149：band_gap 0.610 eV（PBE）；MP 不提供同口径总能量 | `database_native` |

## 对比口径

本计算为 ABACUS/LDA，MP 数据库为 VASP/PBE，总能量不可直接比较，差异属预期而非误差。
要做能量对比需要同泛函/同赝势的参照（roadmap：用 MP_API_KEY 取 MP 总能量，或切换
PBE 口径复算）。

## 执行链路

状态机全程驱动，审计可回放：

```
si-scf-1: draft→planned→waiting_approval→approved→running→(解析发现 bug)→needs_review→completed
si-scf-2: draft→planned→waiting_approval→approved→running→needs_review→completed（复用 si-scf-1 产物，零重复计算）
```

## 首跑发现的问题（均已修复并补回归测试）

1. LCAO STRU 原子数统计错误：旧解析器把磁化行/原子数行当成坐标，Si（2 原子）被数成 3。
2. NUMERICAL_ORBITAL 引用不复制：write_inputs 只拷赝势，轨道文件缺失会让远程运行直接失败。
3. ABACUS 3.x 收敛标记措辞变化：`charge density convergence is achieved` 不同于旧版
   `convergence has been achieved`。
4. 终态拦截只读工具：completed 后 `task.status` 不可用——修复为终态放行只读检查。
5. SFTP 被节点 shell 横幅污染：Bohrium 节点 .bashrc 的 oneAPI banner 破坏 SFTP 握手，
   增加了流式上传（stdin）+ base64 带标记下载的回退通道。

## 文件清单

- 本目录原始日志文件因上述磁盘事故缺失；重跑 `dft.plan → dft.run → dft.parse` 可再生。
- `../mp-149.json` — Materials Project 对照数据（`database_native`）。
