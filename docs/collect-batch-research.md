# 批量采集到研究页面：一条命令

安装可选行情依赖后，从明确指定的东方财富或新浪获取最多 5 只股票的未复权日线，
完成结构和调用方日历检查，再生成可直接查看的研究包：

```sh
python -m pip install -r requirements-akshare.txt
python -m scripts.collect_batch_research --input request.json --output collected-research.zip --allow-network
```

解压 ZIP 后打开 `index.html`。成功项提供研究页面；日期不符或失败项只有诊断。
`collection.json` 保存采集状态、实际接口名、记录数及内容哈希；
`collected/<股票代码>.snapshot.json` 保留通过结构校验的标准化快照。
日期缺口快照也原样保存以供核查，不补造记录。它不是原始 HTTP 响应。
`manifest.json` 对所有其他导出文件的实际字节计算长度和 SHA-256。

## 请求文件

顶层必须且仅含 `schema_version`、`upstream`、`start_date`、`end_date`、`items`。
`schema_version` 为 `"0.1"`；`upstream` 明确选择 `sina` 或 `eastmoney`；
`items` 每项只含 `symbol` 和 `calendar`。日历格式见
[日期覆盖检查](collect-market-research.md#explicit-calendar-coverage-gate)。

- 1–5 只互不重复的 `.SZ` / `.SS` 股票；不自动选股或排序推荐。
- 明确起止日期、最多 366 天跨度、结束日早于北京时间当天。
- 每项显式提供匹配交易所和请求窗口的日历；程序不从返回日期生成日历。
- 所有请求和日历校验在首个供应商调用前完成；没有 `--allow-network` 不执行采集。
- 不自动换源。某项失败后继续下一项，但不对失败项生成研究页面。

[合成注入请求](../examples/collect_batch_research/SYNTHETIC_injected_request.json)
只供离线测试机制：它的日历来自合成样例，不能作为真实完整性证据。
CLI 即使读取该示例，只要加 `--allow-network` 仍会发出真实请求，不能冒充离线测试。

## 退出码与边界

全部生成返回 0；部分或全部未生成返回 2，仍输出含诊断的 ZIP。
无 ZIP、输入错误或 traceback 应单独排查，不能仅凭退出码判为正常部分失败。
输出要求新文件；目录写入预检查在网络调用前进行，并发创建不会覆盖已有证据。
普通错误会清理临时文件；文件系统需支持 hard link。

供应商内部超时和重试行为由 AKShare 继承，本入口不增加传输截止时间或重试。
多个大快照可能触发既有聚合 JSON 体积上限，此时整个包不发布，即使部分采集已完成。
本入口只声明 `UNVERIFIED_LOCAL`：单源可运行不等于双源一致、官方来源认证、
独立日历完整性、历史时点可用性或策略绩效已验证。没有付费模型或券商调用。
