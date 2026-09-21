# 公开数据源登记

本文件是示例数据的来源登记，不代表已经下载或核验了全部记录。下载时必须保存版本、访问日期、许可证和原始 URL。

## 材料级电池性能

### All cycling and rate performance datasets

- URL: https://springernature.figshare.com/articles/dataset/All_cycling_and_rate_performance_datasets/24116592
- 内容：层状正极材料的元素组成、合成条件、循环/倍率性能等表格字段；论文说明提取了 5,265 条属性记录，来自 1,747 篇文章。
- 用途：材料组成与实验性能预测验证。
- 风险：不同论文的测试电流、截止电压、温度和循环终点不一致，必须作为特征或分组字段保留，不能直接混合成无条件标签。
- 相关论文： https://www.nature.com/articles/s41597-024-03196-1
- 相关抽取代码： https://github.com/GGNoWayBack/cathodedataextractor
- 许可证：页面标注 CC0，下载时仍需保存当前记录的许可证信息。
- 状态：首选材料级验证数据，待下载和字段核验。

## 电芯级老化数据

### CALCE battery research data

- URL: https://calce.umd.edu/data
- 内容：LCO、LFP、NMC 等电芯的循环、存储、阻抗和工况数据。
- 用途：时序处理、容量衰减、状态估计和任务工作流验证。
- 边界：这是电芯级测试数据，不等同于材料组成级标签。

### LG M50 cycle ageing dataset

- DOI landing page: https://doi.org/10.5281/zenodo.10637534
- 论文说明：开放的 NMC811/SiOx 电芯循环老化数据。
- 用途：按温度、SOC 和工况进行容量衰减建模。
- 边界：适合验证时序和实验设计，不适合声称跨材料体系泛化。

## DFT 与结构数据

### Materials Project

- URL: https://materialsproject.org/
- API 文档: https://docs.materialsproject.org/downloading-data/using-the-api/getting-started
- 内容：结构、形成能、能带、带隙、相稳定性和计算任务信息。
- 用途：补充结构和 DFT 特征，与材料级实验表按组成或结构映射。
- 访问：官方 `mp-api` 需要用户自己的 `MP_API_KEY`；密钥不写入项目。
- 边界：数据库 DFT 值标记为 `database_native`，不能当作实验标签。

### JARVIS-DFT

- URL: https://jarvis.nist.gov/
- 内容：材料结构和计算性质的公开数据库/服务。
- 用途：作为 Materials Project 的补充来源和跨数据库一致性检查。
- 边界：记录数据集版本和字段定义，避免不同计算协议直接混合。

### Matbench

- URL: https://github.com/materialsproject/matbench
- 内容：材料性质预测基准任务。
- 用途：验证数据契约、拆分、基线和评价报告是否可复现。
- 边界：基准任务结果不能直接替代用户材料体系的实验结论。

## 下载记录要求

每个数据集保存：

```text
source_id
title
url_or_doi
retrieved_at
version
license
raw_filename
sha256
field_mapping
known_limitations
evidence_status
```
