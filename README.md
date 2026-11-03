# stock-market-Agent
股票辅脑

## GitHub 上运行 TradingAgents

使用 GitHub Actions 手动分析股票，调用 DeepSeek，生成中文 HTML 和 Markdown 报告。默认 NVDA，可改为 `600519.SS`、`000001.SZ`、`0700.HK` 等 Yahoo Finance 股票代码。只生成研究报告，不连接券商或提交交易。

### 首次配置

1. 在本仓库 **Settings → Secrets and variables → Actions → New repository secret** 添加 `DEEPSEEK_API_KEY`，值填写自己的 DeepSeek API 密钥。不要将密钥提交到代码或聊天。
2. 打开 **Actions → TradingAgents 中文股票分析 → Run workflow**。
3. 输入股票代码；日期可留空，默认北京时间当天；模型默认 `deepseek-flash`，需与 DeepSeek 账号实际支持的模型一致。
4. 等待运行结束，在该次运行底部 **Artifacts** 下载 `tradingagents-reports-运行编号`，解压并打开 `complete_report.html`。

Actions 工作流需位于默认分支才能在网页手动触发。仓库或组织如果禁用了 Actions，需要先启用。当前仅支持手动运行，没有定时任务。

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
