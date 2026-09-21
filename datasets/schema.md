# 电池材料验证数据契约（草案）

## 样本单位

默认一行表示一个“材料/电芯在明确测试条件下的一项性能观测”。材料级数据和电芯级时序数据不得混在同一张表中。

## 材料级字段

| 字段 | 角色 | 说明 |
|---|---|---|
| `record_id` | 标识 | 本项目稳定 ID |
| `source_id` | 来源 | 论文、数据集或数据库记录 |
| `formula` | 输入 | 化学组成 |
| `elements` | 输入 | 元素集合 |
| `structure_id` | 输入/关联 | MP/JARVIS/用户结构 ID |
| `synthesis_temperature_c` | 输入 | 合成温度，需保留原单位和转换记录 |
| `synthesis_time_h` | 输入 | 合成时间 |
| `particle_size_nm` | 输入 | 如文献提供 |
| `df t_formation_energy_ev_atom` | 输入 | 数据库或计算 DFT 特征，需标来源 |
| `dft_band_gap_ev` | 输入 | DFT 特征，需标泛函/来源 |
| `dft_migration_barrier_ev` | 输入 | 若存在，需标计算方法 |
| `test_temperature_c` | 条件 | 电化学测试温度 |
| `rate_c` | 条件 | 倍率 |
| `voltage_window_v` | 条件 | 电压窗口 |
| `cycle_endpoint` | 条件 | 循环终点定义 |
| `capacity_mah_g` | 目标候选 | 容量 |
| `retention_pct` | 目标候选 | 循环保持率 |
| `source_evidence` | 证据 | 页码、表格、数据文件或 API 记录 |
| `evidence_status` | 证据 | `paper_extracted` 等状态 |

字段名中的 `dft` 是前缀；实际实现使用 ASCII 字段名 `dft_formation_energy_ev_atom`。

## 强制拆分字段

至少尝试按以下字段分组或留出外推测试：

- `source_id`
- `formula` / 化学体系
- `structure_id` / 结构原型
- 实验批次
- 测试协议

随机行切分必须有明确理由，否则可能造成材料、论文或批次泄漏。
