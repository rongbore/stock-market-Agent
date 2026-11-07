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

`scripts.financial_page_text_crosscheck.check_page_text(claims, fingerprints, pages, symbol, research_date)` 接受由调用方提供的页面文字记录数组（每项为 `file_sha256`、`page`、`text`）。`check_disclosure_page_evidence` 则接受 `scripts.disclosure_pdf_text_evidence` 导出的对象，并把核对结果附上公告 URL 和抓取时间；该连接仍是未验证引用，不能证明下载来源或公告当时可得。两种入口都会按文件指纹及页码查找**完整数值字面串**，输出 `literal_value_found_unverified`、`literal_value_not_found` 或 `page_text_missing`。即使找到数值，也无法判断它属于哪个财务指标、单位或报告期，更不能据此认定财务内容正确。若抓取日期晚于研究日期，结果会显式标记 `retrieval_date_after_research_date=true`。

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

页面文字核对新增 `table_column_ambiguous_unverified` 风险提示：当页面出现“本期金额/上期金额”等成对表头，且某条包含目标数字的文本行还有至少一个其他数字时，提示可能存在多列表格歧义。此规则只是保守的页面级启发式预警，不定位表格列，不证明数字属于本期或上期；未触发不代表没有歧义。需要人工复核原始 PDF 表格布局。

新增 `scripts/financial_pdf_geometry.py`：`inspect_spans(spans)` 校验调用方提供的 `{page,text,bbox:[x0,y0,x1,y1]}` 坐标记录，`column_candidates(spans,page,value)` 返回精确数字候选的坐标。限制记录数、文本长度、坐标范围和非有限数值；目前**不从 PDF 自动提取坐标、不识别列标题归属、不核验来源真实性**，所有候选仍需人工查看 PDF 原页。

新增离线字符坐标提取脚本 `scripts/offline_pdf_geometry_extract.py`，需额外安装 `pdfplumber`。示例：`python -m scripts.offline_pdf_geometry_extract --pdf local.pdf --symbol 000776.SZ --announcement-date 2026-10-20 --pages 1 --output geometry.json`。输出单字符 `bbox`（左、上、右、下），单次最多 2000 个字符，复杂页面可能因上限被拒绝；这些字符坐标**不能直接作为完整数字的 bbox**，需后续字符组合与表格行列对齐。当前测试使用模拟 PDF 读取器，尚未覆盖真实 PDF 文件的端到端坐标提取；不核验官方来源或财务语义。

新增 `scripts/financial_pdf_number_boxes.py` 的 `number_boxes(spans)`：将单字符 PDF 坐标按页码、行高和水平间距保守拼接为数字及其包围框，支持负号与小数；拒绝千分位形式的局部误匹配，遇非数字字符、跨行或较大间距即断开。默认间距阈值 3 坐标单位、纵向差 2 单位。当前仅是启发式几何候选，未处理旋转文字、复杂字体排版或表格列语义；不认证财务数值、官方来源和列归属。

新增 `scripts/financial_pdf_column_hints.py` 的 `column_proximity_hints(numbers, headers)`：对**调用方提供**的数字与中文表头 bbox 做同页 x 轴中心距离比较。仅在出现唯一的已知表头对且距离明显时返回 `nearest_header_hint_unverified`；缺失/重复表头、不同页、过远或等距均返回空候选。**不检测真实表格边界、行关系、表头上下位置，也不认定本期/上期列归属**；只可作为人工审查提示。

新增 `scripts/financial_pdf_table_regions.py` 的 `scoped_column_hints(numbers, headers, regions)`：使用**调用方显式提供**的同页表格矩形范围，要求数字只落在一个区域内，并只使用同区域的表头进行横向距离提示；区域外、区域重叠、表头缺失均不判定。区域用 `{page, text: "", bbox: [x0,y0,x1,y1]}` 表示，最多 100 个。**不自动检测表格边界，不验证区域正确性、表头期间语义或官方来源。**

新增 `scripts/financial_pdf_rectangle_candidates.py` 的 `rectangle_region_candidates(rectangles)`：过滤调用方提供的 PDF 绘制矩形（字段 `page,x0,top,x1,bottom`），输出足够大的候选表格区域；跨页独立处理，重叠候选全部剔除，限制输入 2000 个矩形和输出 100 个候选。**该模块不直接读取 PDF、不识别无边框表格，矩形也可能只是普通图形；所有候选仍为未核验提示。**

新增 `scripts/offline_pdf_rectangle_extract.py`：使用可选的 `pdfplumber` 从**本地** PDF 的 `page.rects` 提取绘制矩形并调用 `rectangle_region_candidates`。运行示例：`python -m scripts.offline_pdf_rectangle_extract --pdf ./report.pdf --symbol 000776.SZ --announcement-date 2026-10-20 --pages 1 --output ./rectangle_candidates.json`。读取前后校验文件 SHA256，限制页数和矩形数量；**不联网、不验证官方来源，不识别线段拼成的边框或无边框表格**。输出仅供人工核查。

真实 PDF 解析集成测试：`python -m unittest tests.test_offline_pdf_rectangle_integration`。测试在内存中构造包含矩形绘制指令的有效单页 PDF 文件，再由真实 `pdfplumber` 解析并核对 bbox；**若未安装可选依赖 pdfplumber，测试会明确 skip 而不是宣称通过**。这只是合成 PDF 的集成验证，仍不是实际上市公司公告的抽样验收。

本地财报抽样核查清单：`python -m scripts.pdf_rectangle_review_manifest --pdf ./filing.pdf --symbol 000776.SZ --announcement-date 2026-10-20 --pages 1,2 --output ./rectangle_review.json`。清单保留 PDF SHA256、候选坐标、重叠候选数量和逐项 `pending_manual_review` 状态；`announcement_date_claimed` 只是用户提供的信息，**不是已核实的公告日期**。此工具不下载实际公告、不自动确认官方来源或财务表格。

人工复核结果校验：`scripts/pdf_manual_review_validation.py` 的 `validate_review_annotations(manifest, annotations)` 将审核决定绑定到原 PDF SHA256、候选序号、页码和 bbox；支持 `pending_manual_review`、`accepted_by_reviewer`、`rejected_by_reviewer`，非待审决定必须填写 reviewer。即使 `review_complete=true`，也**不意味着官方来源、财务科目或报告期间已核验**。此模块不自动抓取公告，也不修改原始核查清单。

离线人工复核 CLI：先使用 `python -m scripts.pdf_rectangle_review_manifest --pdf ./filing.pdf --symbol 000776.SZ --announcement-date 2026-10-20 --pages 1 --output ./manifest.json` 生成候选清单；人工创建 `annotations.json`，格式为 `{ "file_sha256": "<与 manifest 一致的 64 位 SHA256>", "decisions": [{ "candidate_index": 0, "page": 1, "bbox": [20, 120, 240, 220], "review_status": "accepted_by_reviewer", "reviewer": "审核人" }] }`（坐标必须从清单原样复制）；然后运行 `python -m scripts.pdf_review_offline_cli --manifest ./manifest.json --annotations ./annotations.json --output ./review_result.json`。拒绝文件指纹不符、候选坐标变动、重复决定及输入覆盖；审核完成不等于公告来源或财务数据验证。

真实公告 PDF 离线抽样记录：先从公告网站手工下载 PDF，再运行 `python -m scripts.pdf_real_filing_sample_record --pdf ./gf_2025.pdf --symbol 000776.SZ --announcement-date 2026-03-31 --source-url https://static.cninfo.com.cn/finalpage/2026-03-31/1225060422.PDF --output ./sample_record.json`。本命令仅对本地文件计算 SHA256 并记录调用方声明的 HTTPS 来源；**不会联网核对 URL 与文件一致性，也不会证明官方来源、公告日期或财务含义**。须人工核对源站原件后再使用其他 PDF 审核工具。

离线 PDF 副本一致性校验：`python -m scripts.pdf_local_copy_consistency --first ./filing_a.pdf --second ./filing_b.pdf --output ./copy_comparison.json`。仅比较本地文件大小及 SHA256，输出 `byte_identical_by_sha256`；即使相同，也不代表文件来自官方公告网站，`official_origin_verified` 和 `financial_meaning_verified` 均为 false。文件大小上限为 100 MiB，工具不会下载或上传 PDF。

一条命令生成离线公告样本证据包：安装 `pdfplumber>=0.11,<0.13` 后运行 `python -m scripts.pdf_sample_bundle_cli --pdf ./gf_2025.pdf --symbol 000776.SZ --announcement-date 2026-03-31 --source-url https://static.cninfo.com.cn/finalpage/2026-03-31/1225060422.PDF --pages 1 --output ./sample_bundle.json`。同时生成 `source_record` 和 `review_manifest`，强制两个阶段 PDF SHA256 相同。输出中的 `sample_checked_with_real_pdf_parser` 仅说明调用了真实 PDF 解析器，不表示 PDF 是真实官方公告；官方来源及财务含义始终标为未核实。请勿将合成测试文件误认为真实财报。

PDF 样本验收诊断：先分别生成 `sample_bundle.json` 和 `review_result.json`，再运行 `python -m scripts.pdf_sample_acceptance_gate --bundle ./sample_bundle.json --review ./review_result.json --output ./acceptance.json`。校验指纹、候选数量、审核决定与坐标是否一致；`blockers` 列出解析器未确认、候选为空、人工审核未完成及官方来源/财务含义未核验等原因。`offline_review_ready` 仅代表离线矩形审核材料齐备，`release_evidence_accepted` 固定为 false；不得据此发布已核实的财务结论。
