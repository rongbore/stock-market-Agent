# 本地快照文件批量研究：合成示例

这里提供的是 **SYNTHETIC 合成文件输入**，不是实际采集的数据。
价格、成交量、时间和日历来自现有合成 SMA 示例，股票代码只是演示标识；
AKShare 格式和接口名称表示输入结构，不代表已从该服务取得数据。
所有步骤均离线，不下载行情、不调用模型、不连接券商。

从仓库根目录运行：

```sh
python -m scripts.local_snapshot_batch --input examples/local_snapshot_batch/SYNTHETIC_manifest.json --output results/local-snapshot-demo.zip
```

首次运行使用新的输出文件名；重复演示请另取输出名，保留前一次证据。
解压 ZIP 到新目录，打开 `index.html` 查看任务汇总，成功任务可进入其研究页面。

**该混合示例预期退出码为 2**：一项生成研究，一项因日期缺口被阻断。
这不是程序崩溃，也不代表两项都成功。应同时检查 ZIP 已生成、索引及诊断内容；
出现 traceback、缺少 ZIP 或输出文件冲突时，须另行排查，不能仅凭退出码判断。

| 本地文件 | 用途 |
| --- | --- |
| `SYNTHETIC_manifest.json` | 数据声明、显式证据截止时间、复权口径及两项任务 |
| `SYNTHETIC_000776_snapshot.json` | 5 条合成日线，与日历一致，预期生成未核验研究 |
| `SYNTHETIC_000001_missing_date_snapshot.json` | 同一合成来源改用演示代码，故意缺少 `2026-11-03`，预期待核查 |
| `SYNTHETIC_calendar.json` | 两项任务共用的 5 日合成日历 |

manifest 中 `snapshot_path`、`calendar_path` 均相对 **manifest 所在目录**，
不是相对当前运行目录。顶层字段固定为 `schema_version`、`data_kind`、
`evidence_as_of`、`expected_adjustment`、`items`；每项只填写 `symbol`、
`snapshot_path`、`calendar_path`。入口最多接受 20 项，本例仅 2 项。

日历是从同一合成数据复制而来，只用于机制测试，不能证明真实交易日完整性。
日期匹配仍不代表来源、历史时点可用性、官方日历或策略绩效已经核验。
本例不填补缺失日线、不构成选股或投资建议，也不输出真实金融结论。

需要先了解独立的单股验收、回测和 ZIP 入口，可阅读
[离线快速运行指南](../../docs/offline-quickstart-zh.md)。
