# 两股票采集到研究包实际运行 — 2026-11-22

在 main `9a60f59bbcac315fccb7869924498408a7b2ffdd` 加入本轮批量采集代码后，
使用隔离环境 AKShare 1.20.65、显式 `sina`、2026-11-02 至 2026-11-06 的请求，
实际运行 CLI（并通过 AKShare 全局设置将超时设为 10 秒）：

```sh
python -m scripts.collect_batch_research --input request.json --output collected-research.zip --allow-network
```

结果：CLI 退出码 0，两项均为 `COLLECTED_UNVERIFIED`；`000001.SZ` 和 `000776.SZ`
各获得 5 条日线，实际接口为 `stock_zh_a_hist_sina`。生成两个研究页面、统一索引、
采集诊断、标准化快照及文件清单，ZIP 完整性检查通过。没有假造 provider 回包，
也没有调用付费模型或券商。

[机器记录](collected-batch-live-20261122.json)包含实际请求、每项检索时间、接口、
记录数、快照规范化哈希和 ZIP 字节哈希。原始行情行未提交仓库。
调用方日历明确标为 replay sessions，并非独立官方日历；此运行只能证明按该输入
采集和生成链路可用，不能证明日期完整性、行情准确性或历史时点可用性。

东方财富此前的连接故障仍未解决，此次显式选择新浪并未自动换源，也未声明双源一致。
浏览器视觉验收和 v0.2 发布级证据要求仍独立存在。

另在安装的真实 AKShare 1.20.65 上构造 `akshare.utils.http.Push2RateLimitError`
（未发送限流请求），确认归类为 `rate_limit`。离线回归测试确认限流不重试、其他源
仍执行，普通瞬时断线重试和 `BaseException` 传播保持原行为。
