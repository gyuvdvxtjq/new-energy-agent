# 任务状态

状态：`complete_with_external_optional_sources`

## 已完成

- [x] 确认本地 Agent 工作区形态
- [x] 确认 Codex 优先和 Claude Code 兼容
- [x] 确认三种科研编排模式
- [x] 确认远程 SSH/Slurm 需用户确认
- [x] 建立项目规格、架构、决策和验收文档

## 外部可选扩展

- Figshare 材料级数据自动下载当前 HTTP 403；来源、字段和许可证已登记。它不阻塞本地 Agent、Zenodo 电池数据验证或 Materials Project 适配器。

已完成本轮：

- [x] 创建工作区初始化脚本
- [x] 创建无依赖 CSV 数据契约预检脚本
- [x] 创建只生成计划、不提交任务的远程计算脚本
- [x] 登记公开电池、DFT 和基准数据源
- [x] 写入电池材料验证数据契约草案
- [x] 添加数值特征 Random Forest 基线和分组切分支持
- [x] 记录 GitHub、LinuxDo 和 DeepModeling 的参考项目与设计经验
- [x] 添加带 SHA256 和来源清单的 Zenodo 公共数据下载器
- [x] 用公开 Zenodo 电芯数据验证下载、哈希和非标准 CSV 表头处理
- [x] 添加电池循环 CSV 到逐循环派生表的确定性转换器
- [x] 添加透明的化学式组成特征提取器，并记录复杂化学式限制
- [x] 补充 Python 科学依赖说明和环境能力诊断
- [x] 建立变更记录
- [x] 建立子 Agent 结构化交接协议和校验器

## 待完成

- [x] 实现数据质量与泄漏检查脚本
- [x] 实现性能预测基线脚本
- [x] 实现 DFT 计划与 SSH/Slurm 命令生成
- [x] 实现 DFT 输出解析入口
- [x] 添加 Codex 安装/验证脚本
- [x] 完成无网络端到端验收
- [x] 添加 Materials Project 可选查询适配器
- [x] 添加统一 CLI 和自动化测试
- [x] 完成公开 NCM 材料数据的真实 IC/EC 端到端演示
- [x] 添加一键材料演示和 Agent 会话记录
- [x] 使用项目 .env 实际查询 Materials Project
- [x] 生成 MP 特征合并表和近似映射 manifest

新增完成：

- [x] 实现数据质量、缺失值、重复和泄漏风险预检
- [x] 实现基础 VASP OUTCAR 标量解析
- [x] 添加无网络自检脚本

## 当前下一步

- [x] 修复 GitHub 上传脚本未导出认证变量的问题；大小写密钥配置均通过模拟认证验证。
- [x] GitHub API 实测密钥有效、目标仓库可访问，返回 push 权限。
- [ ] 推送当前 main 并核对远端提交。
