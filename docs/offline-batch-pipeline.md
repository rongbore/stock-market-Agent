# 单命令离线批量研究演示

在仓库根目录执行：

```sh
python -m scripts.offline_batch_pipeline --input examples/batch_research/SYNTHETIC_offline_pipeline.json --output /tmp/SYNTHETIC-batch-artifact.json
```

示例中的价格全部为虚构合成数据，**不代表真实市场数据**。它刻意包含一项正常
历史摘要、一项缺失输入和一项晚于分析截止日期的输入，预期成功 1 项、失败或缺失
2 项。命令成功表示一次性产物已生成，不表示所有任务成功；查看 `bundle` 的计数
与每项状态。输出中的 `summary_markdown` 是经校验、转义的中文复核摘要。

流水线复用 `build_batch_plan` → `run_batch_plan` → `render_summary`，不复制行情或
财务校验逻辑，也不执行计划中的路径。单个 JSON 原子产物包含完整 `plan`、`bundle`
和 `summary_markdown`，任何阶段失败均不替换已有产物。不会创建各股票输出目录。

输入必须且只能有 `schema_version: "0.1"`、`data_kind`、`symbols`、`analysis_date`
和 `reports` 五个字段。`symbols` 是 1–100 个唯一 A 股格式代码；`reports` 是这些
代码到内联趋势报告对象的映射，不是路径或 URL。报告字段遵循离线批量 runner。
`data_kind` 必须为 `SYNTHETIC` 或 `UNVERIFIED_LOCAL`；这是调用方声明，绝不升级为
真实或已验证来源。非 JSON、非有限数值、过深或过大的整体配置会拒绝；可编码但
语义无效的单条报告由 runner 隔离失败。重复 JSON 键与未知顶层字段也拒绝。

输入文件及规范化 JSON 编码预算上限 20 MiB，深度、节点与整数限制沿用 runner。
默认摘要显示 20 项，可用 `--max-rows 1..100` 调整，省略数量明确展示。输出拒绝
覆盖输入或符号链接目标；完整产物先序列化，再原子替换文件。

`pipeline_input_sha256` 标识完整输入配置；`artifact_payload_sha256` 标识不包含自身
哈希字段的完整产物，采用 `json_sorted_keys_ascii_compact_v1` 编码。它是解析后
JSON 内容的标识，不是漂亮排版后的文件字节哈希。内部计划和报告哈希仍由 runner
生成。相同输入和摘要行数产生相同产物，无当前时间戳，不修改内存输入。

所有哈希只提供完整性标识，不证明发布者、价格真实性或历史时点可用性。分析日期
不证明数据当时已经公开。该命令不联网、不调用模型或付费接口、不创建调度、不
连接券商或交易，也不生成目标价、排名或投资建议。

验证：`python -m unittest tests.test_offline_batch_pipeline -v`，包含无模拟的 CLI
端到端测试；这仅验证合成离线链路，不是实际股票研究验收。
