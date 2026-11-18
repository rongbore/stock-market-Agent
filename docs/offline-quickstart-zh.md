# 合成数据离线快速运行

这组示例展示“日期验收 → 纸面评估 → 单股研究包 → 批量研究”的现有入口。
所有价格、成交量、时间与成本均为 **SYNTHETIC 合成测试数据**；股票代码只是
演示标识，不代表这些股票的实际行情或投资判断。日历从同一合成样例复制，
只验证程序机制，不能证明真实交易日完整性。

从仓库根目录使用 Python 3.11+ 执行下列命令。无需 AKShare、API 密钥、联网、
模型或券商连接。下面的 `results/quickstart` 用于首次运行；验收、ZIP 和批量
输出要求新文件，重复运行请改用新的输出文件名或目录，不要覆盖已有证据。

## 1. 单股日期验收

```sh
python -m scripts.calendar_acceptance_cli --input examples/offline_quickstart/SYNTHETIC_acceptance_config.json --output results/quickstart/acceptance.json
```

预期退出码 0，`status` 为 `MATCH`。它只表示日期与调用方提供的合成日历一致。

## 2. 带日历门禁的 SMA 纸面评估

```sh
python -m scripts.sma_evaluation_cli --input examples/backtest/SYNTHETIC_sma_oos_config.json --calendar examples/offline_quickstart/SYNTHETIC_calendar.json --output results/quickstart/sma-evaluation.json
```

预期退出码 0，输出含 `calendar_coverage.status: MATCH`、日历哈希，以及原有
训练、测试和买入持有基准结果。参数固定为样例值；不是参数优化或已核实绩效。
不匹配日历会在评估开始前阻断；此 CLI 不生成日期失败诊断，已有输出保持不变。

## 3. 单股离线 ZIP

```sh
python -m scripts.offline_research_package --input examples/offline_quickstart/SYNTHETIC_acceptance_config.json --output results/quickstart/single-research.zip
```

预期退出码 0。解压到新目录，打开 `dashboard.html` 或 `summary.md`；同包的
`acceptance.json` 与 `manifest.json` 保存日期检查和文件校验信息。无须手动从
JSON 提取 HTML。ZIP 内不包含第 2 步的 SMA 评估；这是两个独立演示入口。

## 4. 三股批量 JSON：成功、日期缺口、非法输入

```sh
python -m scripts.batch_calendar_research --input examples/offline_quickstart/SYNTHETIC_batch_calendar_research.json --output results/quickstart/batch-research.json
```

**预期退出码为 2，不等于程序崩溃。** 此示例故意包含两种失败路径，仍应写出完整
批量 JSON：`status: PARTIAL_RESEARCH_UNVERIFIED`，已生成 1、日期待核查 1、失败 1。
各任务相互隔离，只有通过检查的那一项含研究摘要和 Dashboard HTML。

| 演示代码 | 设计输入 | 预期任务状态 |
| --- | --- | --- |
| `000776.SZ` | 与合成日历匹配的 5 条日线 | `RESEARCH_GENERATED_UNVERIFIED` |
| `000001.SZ` | 故意缺少 `2026-11-03`，日历保持不变 | `REVIEW_REQUIRED` |
| `600519.SS` | 故意填写不支持的成交量单位 | `FAILED_INPUT_OR_GENERATION` |

可打开 JSON 的 `summary_markdown` 和 `results` 查看每项结果。Bash 可在该命令后
执行 `echo $?` 查看退出码；PowerShell 使用 `$LASTEXITCODE`。不要用忽略所有错误
的包装命令掩盖退出码。若 JSON 根本没有生成、出现 traceback 或已有输出冲突，
应先检查路径和输入，不能仅凭数字 2 断定这是预期的部分失败。

所有示例结果仍为来源、历史可用性和日历真实性未核验，不连接实盘，不构成建议。
完整参数和边界见 [SMA CLI](sma-evaluation-cli.md)、
[单股 ZIP](offline-research-package.md) 和 [批量研究](batch-calendar-research.md)。


## 5. 批量研究 ZIP：打开统一入口

```sh
python -m scripts.batch_research_package --input examples/offline_quickstart/SYNTHETIC_batch_calendar_research.json --output results/quickstart/batch-research.zip
```

此混合示例同样预期退出码 2。解压后打开 `index.html`：一项提供研究页面，
其余两项只提供诊断。无需从 JSON 手动提取 HTML。校验清单位于
`manifest.json`；查看[批量研究包说明](batch-research-package.md)了解文件结构。
