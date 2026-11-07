# TradingAgents 真实分析失败排查（只读）

适用：手动工作流 `TradingAgents 中文股票分析` 的 `analyze` 作业失败，尤其是 `002517.SZ` 基本面分析。

## 先确认运行模式

- `dry_run=true`（默认）：只生成离线合成报告；**不会**验证 DeepSeek 连接、实时行情或新闻。
- `dry_run=false`：启动真实分析，可能产生模型 API 费用。不要为了确认修复而反复重试。
- `date` 可留空（北京时间当天），填写时必须是 `YYYY-MM-DD`；输入预检查在安装 TradingAgents 之前执行。

## 识别错误

| 日志现象 | 解释 | 建议 |
| --- | --- | --- |
| `Unexpected response type from OpenAI-compatible endpoint ... NoneType` | 模型兼容接口响应无法被当前客户端解析；发生在模型调用链，不等同于日期格式错误 | 核对工作流填写的模型 ID 是否为提供方账号支持的模型，检查提供方状态与兼容性；不要公开密钥或原始带凭据的请求 |
| `FRED_API_KEY environment variable is not set` | 可选宏观数据源未配置 | 标记宏观数据缺失；不要将其当作模型响应异常的已证实原因 |
| `Yahoo Finance has no news articles tagged ...` | 对应代码的 Yahoo 新闻结果不可用 | 标记新闻覆盖缺口；不要推断为“没有重大新闻” |
| `分析日期必须使用 YYYY-MM-DD` | 日期未补零等输入错误 | 例如使用 `2026-11-04`，或留空 |
| `DEEPSEEK_API_KEY` 配置缺失 | 缺少所需的 Actions secret | 仅在仓库 Actions secrets 中配置；不要写入代码、Issue 或日志 |

## 无费用验证与人工核对

1. 在 Actions 中先选 `dry_run=true`，检查离线报告合同与脱敏检查是否通过。它**不代表**真实模型服务已恢复。
2. 在原始失败运行的 `Analyze stock` 日志中确认最后一条异常及失败的 Agent；不要只根据 FRED 或 Yahoo 警告推断根因。
3. 核对 `model` 输入与实际账号可用的模型名称。工作流默认值 `deepseek-flash` **不保证**在所有账号或时点可用。
4. 若需真实连通性验证，应先明确接受可能产生的费用，再进行**一次受控验证**；失败时停止，不启用自动重试。
5. 报告中的来源缺失应标记为不可用或未验证；不得将缺失新闻、宏观数据或人工录入内容提升为已核实证据。

## 安全边界

不要求提供 API key、完整 Authorization 请求头或账户凭据。此排查手册不修改交易功能，不连接券商，不承诺分析报告具备投资决策可靠性。
