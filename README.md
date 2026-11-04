# stock-market-Agent
股票辅脑

## GitHub 上运行 TradingAgents

使用 GitHub Actions 手动分析股票，调用 DeepSeek，生成中文 HTML 和 Markdown 报告。默认 NVDA，可改为 `600519.SS`、`000001.SZ`、`0700.HK` 等 Yahoo Finance 股票代码。只生成研究报告，不连接券商或提交交易。

### 首次配置

1. 在本仓库 **Settings → Secrets and variables → Actions → New repository secret** 添加 `DEEPSEEK_API_KEY`，值填写自己的 DeepSeek API 密钥。不要将密钥提交到代码或聊天。
2. 打开 **Actions → TradingAgents 中文股票分析 → Run workflow**。
3. 输入股票代码；日期可留空，默认北京时间当天；模型默认 `deepseek-flash`，需与 DeepSeek 账号实际支持的模型一致。
4. 等待运行结束，在该次运行底部 **Artifacts** 下载 `tradingagents-reports-运行编号`，解压并打开 `complete_report.html`。

Actions 工作流需位于默认分支才能在网页手动触发。仓库或组织如果禁用了 Actions，需要先启用。TradingAgents 中文股票分析工作流仍需手动运行；另有独立的 AKShare 双来源行情验收工作流，每周自动执行。

### 费用与数据

- DeepSeek API 按实际用量收费，GitHub Actions 计算资源计入账号相应额度。首次仅分析一只股票，讨论轮数固定为 1。
- 使用 Yahoo Finance，以及适用美股公司的 SEC EDGAR；未配置需要额外密钥的宏观分析和社交情绪分析。
- A 股与港股的数据、新闻覆盖取决于上游数据源；历史非美股财报可能因发布日期不可确认而被上游限制。
- 报告保留 14 天。每次运行使用独立缓存和记忆，不跨次积累持仓或历史决策。
- 报告可被有权查看 Actions 产物的用户下载，请勿在输入中加入私人持仓或秘密。

### 技术配置

工作流使用 Python 3.13，并将 [TradingAgents](https://github.com/TauricResearch/TradingAgents) 固定到提交 `c4544913a14ed3df5f1ed7b9e8483270ce20682a`；其传递依赖仍按上游版本范围安装。脚本位于 `scripts/analyze.py`。默认仅启用技术、新闻和基本面分析，输出为简体中文；上游内部讨论可能仍为英文。

本地运行需 Python 3.11+，安装同一提交的 TradingAgents，并通过环境变量提供 `DEEPSEEK_API_KEY`，然后执行 `python scripts/analyze.py`。可用 `ANALYSIS_TICKER`、`ANALYSIS_DATE`、`ANALYSIS_MODEL` 覆盖默认参数。

本项目用于投研实验；报告需核对数据来源，不能将其视为已验证的盈利策略。

### 可选官方公告来源预校验（离线）

设置 `ANALYSIS_DISCLOSURES_JSON` 为本地公告元数据 JSON 数组文件路径，并设置 `ANALYSIS_DISCLOSURE_SOURCE=cninfo`、`sse` 或 `szse`，可在任何付费模型初始化前对公告 URL 官方域名、代码所属交易所及日期进行校验。该功能不会抓取公告或验证其内容；候选清单及时间信息仍标记为未核实。不设置 `ANALYSIS_DISCLOSURE_SOURCE` 时保留原有通用离线筛选行为。

可单独运行离线筛选命令：`python -m scripts.disclosure_candidates notices.json --analysis-date 2026-10-30 --symbol 000776.SZ --output-dir results/candidates --official-source cninfo`。`--official-source` 也支持 `sse`、`szse`；未指定时仍为通用离线筛选。此命令只检查本地元数据，不抓取公告，不证明内容真实。

### 官方公告 JSON API 传输层（实验性）

`scripts.disclosure_api.fetch_official_disclosure_json(url, source=..., analysis_date=...)` 可从调用方提供的官方 HTTPS 主机 JSON 端点获取公告元数据数组，禁用重定向并限制响应体积。**尚未确认交易所实际公开 API 的路径和响应结构**；需要后续对接官方接口并验证字段映射，不可将示例 URL 当作可用接口。所有返回记录仍标记为未核实，不直接作为已验证研究证据。此功能不使用密钥，不调用付费模型。

实验性公告采集流程可通过 Python 调用 `collect_disclosure_candidates(url, source='cninfo', analysis_date='2026-10-30', symbol='000776.SZ', output_dir='results/disclosures')`。该调用只有在提供**已确认的合法官方 JSON API 地址**时才会发起网络请求；目前项目尚未验证真实端点或其使用许可。成功后会生成 `disclosure_api_snapshot.json` 与 `disclosure_candidates.json`，均不构成公告真实性或历史可用性认证。不得在生产分析中将未核实记录升级为已验证证据。

只读 CLI：`python scripts/disclosure_api.py --endpoint 'https://<已验证的官方主机>/<实际接口路径>' --source cninfo --analysis-date 2026-10-30 --symbol 000776.SZ --output-dir results/disclosures`。占位地址不可直接使用；必须先确认实际官方接口及允许的使用方式。命令不会调用 LLM、券商或交易功能。

### AKShare 双来源行情验收与中文证据报告（只读）

仓库的 **Actions → AKShare dual-upstream crosscheck** 可手动运行（`workflow_dispatch`），默认以 `000776.SZ` 为研究样本；也设置了每周三 02:20 UTC 的定时验收。定时运行自动使用最近 21 个自然日至昨日的日期窗口，手动运行可覆盖代码与起止日期。定时触发可能受 GitHub Actions 调度延迟影响，首次实际定时运行仍须核验。

该工作流通过 AKShare 分别尝试东方财富和新浪的历史日线接口，比较 OHLCV（成交量按显式单位归一化）。在双来源均成功时生成 `daily_crosscheck_report.json`；无论采集是否成功，只要诊断文件已生成，就尝试生成 `dual_source_evidence_unverified.md`。Artifacts 同时保存诊断与可用的快照，保留 3 天。

**本地离线复现报告**（不发起网络请求，不调用付费模型）：

```bash
python -m scripts.akshare_evidence_report --input-dir dual_output --output dual_output/dual_source_evidence_unverified.md
```

输入目录必须有 `dual_upstream_diagnostics.json`；`daily_crosscheck_report.json` 可选。若双来源比较不可用，报告会标注“未通过或未完成”，而不是推断已验证。该报告是**行情数据质量证据摘要**，尚未覆盖真实财报与公告正文，不提供投资建议。

**证据边界：** 两个非交易所数据源的数值一致，不代表交易所权威认证、交易日历完整性、公告发布时间核实或历史时点可用性。当前 `independent_source_verified=false`、`exchange_calendar_checked=false`；不能将其改写为“已认证”。若网络不可达，应查看 Actions 摘要中的安全错误分类与 Artifact，而非认为行情为零。

