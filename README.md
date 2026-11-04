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


#### 将公告索引元数据纳入离线行情证据报告（实验性）

可选参数 `--disclosures-json disclosure_index.json` 接受本地 JSON 数组，单条格式：

```json
[{"symbol":"000776.SZ","announcement_date":"2026-10-20","title":"公告标题（示例）"}]
```

运行 `python -m scripts.akshare_evidence_report --input-dir dual_output --output dual_output/dual_source_evidence_unverified.md --disclosures-json disclosure_index.json`。程序仅允许相同股票代码、有效日期且不晚于研究截止日期的公告元数据；最多 100 条。**仅列出本地提供的索引元数据，不代表已经联网获取公告、核验公告 PDF 正文、披露时刻或财务数据。** 未提供索引时，报告明确标记“未提供”，而不是“没有公告”。正式公告信息应以巨潮资讯网披露原文核实。

#### 本地公告 PDF 文件指纹（离线、未认证）

已从可信渠道自行取得 PDF 文件后，可执行：

```bash
python -m scripts.disclosure_pdf_fingerprint --pdf announcement.pdf --symbol 000776.SZ --announcement-date 2026-10-20 --output disclosure_fingerprint.json
```

输出 SHA-256、文件字节数、股票代码和公告日期；仅检查 PDF 文件头，不解析正文、不下载文件、不访问网络，也**不证明文件确实来自巨潮资讯网、公告日期属实或财务内容正确**。输出中的来源、正文和历史时点验证标志均为 `false`。限制文件大小不超过 20 MiB。原始文件应保留在可信的证据归档中，以便复核摘要。

#### 将本地 PDF 指纹纳入中文行情证据报告

将 `scripts.disclosure_pdf_fingerprint` 生成的一个或多个 JSON 对象汇总为 JSON 数组文件 `fingerprints.json`，然后执行：

```bash
python -m scripts.akshare_evidence_report --input-dir dual_output --output dual_output/dual_source_evidence_unverified.md --fingerprints-json fingerprints.json
```

文件指纹必须与研究股票代码和日期区间一致，SHA-256 为 64 位小写十六进制，文件大小在 8 字节到 20 MiB 范围内，并且 `official_origin_verified`、`source_content_verified` 均须为 `false`。这仅关联离线文件摘要，不证明文件来自官方或财报数字正确。

#### 财务指标证据结构校验（离线实验）

`scripts.financial_claim_evidence.validate_claims(claims, fingerprints, symbol, research_date)` 对**人工录入且尚未验证**的财务指标进行结构检查。单条 claim 包括：`symbol`、`metric`（revenue/net_profit_attributable/total_assets/operating_cash_flow）、`value`（十进制字符串）、`unit`（CNY/CNY_10000/CNY_100000000）、`period_end`、`announcement_date`、`file_sha256`、`page`（从 1 开始）。必须引用现有本地 PDF 指纹，并且公告日期不晚于研究截止日。输出一律标注 `manually_transcribed_unverified`，不进行 PDF 文字识别、来源认证或数值核实；不得将其直接作为已证实的财报数据。

财务指标证据日期约束：所引用 PDF 指纹必须包含 `announcement_date`，且与 claim 的公告日期完全一致，均不得晚于研究截止日。同一 SHA-256 不允许映射到不同公告日期。日期匹配仅是元数据一致性检查，不代表公告时间或正文已获官方核验。

#### 在离线中文证据报告中展示人工财务摘录

将 `validate_claims` 所需格式的人工摘录对象汇总为 `claims.json` 数组，并同时提供同一批本地 PDF 指纹数组：

```bash
python -m scripts.akshare_evidence_report --input-dir dual_output --output dual_output/dual_source_evidence_unverified.md --fingerprints-json fingerprints.json --claims-json claims.json
```

输出每条指标的数值、单位、报告期、公告日期、PDF 页码与 SHA-256，强制关联对应的 PDF 指纹。所有数值均标记为**人工摘录、未认证**，不得据此断言 PDF 正文核验通过。缺少 `--claims-json` 时保留原有报告行为。

#### 财务指标与页面文字的离线字面核对（实验）

`scripts.financial_page_text_crosscheck.check_page_text(claims, fingerprints, pages, symbol, research_date)` 接受由调用方提供的页面文字记录数组（每项为 `file_sha256`、`page`、`text`）。先校验人工财务摘录与 PDF 指纹，再按文件指纹及页码查找**完整数值字面串**，输出 `literal_value_found_unverified`、`literal_value_not_found` 或 `page_text_missing`。这不是 PDF 解析器；页面文字由调用方提供，无法验证其确实来自对应 PDF。即使找到数值，也无法判断它属于哪个财务指标、单位或报告期，更不能据此认定财务内容正确。

#### 从本地 PDF 提取指定页码文字（可选依赖）

先在本地环境安装 `pypdf`（CI 使用注入式离线测试，不要求联网安装依赖）。仅处理本地文件，限制 20 MiB、单次最多 100 个指定页码，提取前后计算 SHA-256 并拒绝文件变化；加密 PDF 不支持。示例：

```bash
python -m scripts.offline_pdf_page_text --pdf local_disclosure.pdf --symbol 000776.SZ --announcement-date 2026-10-20 --pages 1,4 --output pages.json
```

生成的 `pages.json` 可传入 `scripts.financial_page_text_crosscheck.check_page_text`。扫描件可能没有可提取文字；本模块不进行 OCR，不保证提取内容正确，也不验证文件来自官方、财务含义或披露时间。

#### PDF 页面文字核对结果写入中文报告

先用 `scripts.offline_pdf_page_text` 生成 `pages.json`，并提供匹配的 `fingerprints.json` 和 `claims.json`：

```bash
python -m scripts.akshare_evidence_report --input-dir dual_output --output dual_output/dual_source_evidence_unverified.md --fingerprints-json fingerprints.json --claims-json claims.json --pages-json pages.json
```

报告分别列出人工财务摘录及其页面数字字面核对结果。字面找到相同数字并不验证它属于指定指标、单位或报告期；页面文字与文件来源真实性也未认证。没有 `--pages-json` 时保留原报告行为。

财务页面文字核对还会提供 `metric_label_near_value_unverified`：仅当同一文本行中，预设中文指标名称位于数字前且距离不超过 80 字符时为 `true`。该字段只是一条弱词汇线索，可能误判表格、否定语境或跨栏文字；不能据此认定指标名称、数值、单位、报告期或官方来源已核验。

页面文字核对新增 `unit_label_near_value_unverified`：仅在数字同一行紧邻出现明确单位标记（`人民币元`、`万元`、`亿元`）时记录弱线索；单位不一致、跨行或距离过远不记为匹配。此检测不理解表格列标题、金额换算或上下文，不得据此认定财务单位已经核验。

页面数字核对新增 `period_end_near_value_unverified`：仅当人工摘录的报告期日期（ISO 日期或常见中文年月日格式）出现在数字之前、同一行且不超过 80 字符时提供弱线索。它不理解跨列表头、财务报表列结构或“本期/上期”关系；即使为真，也不代表报告期已通过财务语义核验。
