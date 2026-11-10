# 离线功能运行指南

目前可用的入口包括财报复核材料、批量历史研究摘要，以及 Python 调用的纸面回测评估。
这些功能不连接券商，不提交交易，不需要模型密钥。测试通过和生成材料均不代表市场数据已核实。

## 1. 批量研究：先运行合成示例

在仓库根目录使用 Python 3.11+ 执行：

```sh
python -m scripts.offline_batch_pipeline --input examples/batch_research/SYNTHETIC_offline_pipeline.json --output results/synthetic-batch.json
```

示例明确标为 `SYNTHETIC`，价格是编造的测试数据。预期共 3 个任务：
1 个摘要成功、1 个缺少输入、1 个因未来日期失败。这是刻意演示的失败隔离，不是所有股票均分析成功。

输出 JSON 中的 `plan` 是确定性任务计划，`bundle` 包含逐股结果和成功／失败计数，
`summary_markdown` 是中文摘要。输入与产物的哈希用于区分数据版本，不能证明来源真实。
程序一次性写入一个产物；全局配置错误时原输出保留，逐股错误则记录在结果内。

使用自己的本地趋势报告时，保留示例的五个顶层字段，将 `data_kind` 设为
`UNVERIFIED_LOCAL`。显式列出 `symbols`、`analysis_date` 及股票代码到报告对象的
`reports` 映射；报告至少提供对应 `symbol`、升序且唯一的 `dates`、对齐的正有限 `prices`。
报告日期不得晚于分析日期。不会自动下载行情、补齐数据或将缺失数据当作零。

详见 [批量流水线](offline-batch-pipeline.md) 和 [中文摘要](batch-research-summary.md)。

## 2. 财报：生成可追溯的复核材料

安装可选的 PDF 解析依赖后，将自行取得的本地 PDF 交给流水线：

```sh
python -m pip install 'pdfplumber>=0.11,<0.13'
python -m scripts.financial_review_pipeline --pdf /path/to/filing.pdf --symbol 000776.SZ --announcement-date 2026-10-30 --pages 1 --output results/financial-review.json
```

上述路径和日期需要替换为实际文件及调用方声明的日期。命令不下载公告，也不认证该日期。
输出中的 `package` 保留数值、页码、表格坐标及指标／单位／期间提示；`validation`
检查结构一致性；`review_record` 记录待审情况；`report_markdown` 供人阅读。

`REVIEW_MATERIALS_READY_UNVERIFIED` 只说明存在数字候选。
`NO_NUMERIC_EVIDENCE` 表示没有数字证据，不能据此形成财务结论。
扫描件、无边框表格、未知指标或单位可能无法提供足够的候选。

记录审核决定时，把 `package.file_sha256` 和 `validation.package_sha256` 原样写入
[复核记录格式](financial-table-review-annotations.md)，再用 `--annotations` 指定该 JSON。
文件或解析结果变化后，旧审核绑定可能失效，需要重新核对；审核人名字只是调用方声明。
全部记录决定也不会移除合并口径、来源真实性和财务数值核验的缺口。

详见 [财报流水线](financial-review-pipeline.md) 和 [结构检查](financial-table-package-validation.md)。

## 3. 回测：区分数据契约与假设绩效

Python 接口按顺序为：

| 接口 | 用途 |
| --- | --- |
| `build_backtest_dataset` | 校验来源结构、复权声明、单位、日线与证据截止时间 |
| `run_sma_paper_backtest` | 显式费用假设下，收盘信号在下一根已观测日线开盘执行 |
| `evaluate_sma_out_of_sample` | 固定窗口，训练／测试账户独立，与同测试区间买入持有基准比较 |

每次必须明确初始资金、整手数量、佣金、最低费用、卖出税、滑点与窗口。
税费参数是调用方假设，不是系统提供的现行法规或券商费率。
模拟只接受不复权数据，尚未处理公司行动、涨跌停、流动性与完整交易日历。
最大回撤包含初始资金峰值，收益不年化；期末持仓按收盘价标记，不强制平仓。

详见 [数据契约](backtest-data-contract.md)、[样本外评估](sma-out-of-sample.md)
和 [基准及风险指标](paper-benchmark-risk.md)。历史价格时间排序不能证明历史时点可获取。

## 常见阻断

| 现象 | 处理 |
| --- | --- |
| 缺少 `pdfplumber` | 安装 PDF 可选依赖；不能把跳过解析测试当作成功 |
| 批量任务失败 | 逐项查看 `bundle.results`，区分缺失输入与非法日期／价格 |
| 复核指纹不一致 | 对照原 PDF 与完整证据包，重新确认后生成绑定记录 |
| 不允许覆盖输入 | 改用单独输出路径，不把源文件作为结果路径 |
| 结构检查通过但仍未核验 | 这是预期边界；继续核对原件、财务口径与真实数值 |

目前还没有完成真实数据的全链路验收或独立 Web Dashboard；这些命令是本地功能入口。
