# SYNTHETIC 批量采集请求样例

`SYNTHETIC_injected_request.json` 是用于注入测试的查询描述，并非市场数据。
其中的日历从既有合成样例复制，不是独立官方交易日历。顶层 schema 不包含
`data_kind` 字段；SYNTHETIC 标签保留在文件名及每项日历的 source 中。

离线测试应通过 `build_collected_batch_package(request, allow_network=True, fetcher=合成返回函数, now=固定时钟)`
注入合成快照，不调用真实数据源。`allow_network=True` 在这里仅满足显式执行门禁，
实际访问行为由注入函数控制；不要把此测试误报为真实采集成功。

CLI `python -m scripts.collect_batch_research --input 请求文件 --output 新文件.zip --allow-network`
会执行真实供应商请求，并非离线演示。运行真实采集前，应另备明确日期窗口和独立日历，
不应使用本合成日历证明完整性。不匹配或某项采集失败时，ZIP 仍可包含成功项和诊断，
退出码 2 表示未全部生成；无 ZIP 或 traceback 应另行排查。所有来源/PIT/日历仍未核验。
