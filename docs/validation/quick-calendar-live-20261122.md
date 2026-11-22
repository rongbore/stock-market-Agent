# 供应商日历到研究包实际运行 — 2026-11-22

基于 main `a31c17fd702fbbe6c28ce040fd48c1afe97b8df2` 加入快捷入口后，
使用已安装 AKShare 1.20.65 实际执行：

```sh
python -m scripts.quick_market_research --symbols 000776.SZ 000001.SZ --upstream sina --start-date 2026-11-02 --end-date 2026-11-06 --allow-network --output research.zip
```

运行前通过 AKShare 全局 `set_timeout(10)` 设置超时；没有给不支持的接口添加参数。
日历来自实际 `calendar_trade_date_hist_sina` 的单独请求，不来自股票行情日期：
供应商完整列表有 8,797 个日期，首尾为 1990-12-19 和 2026-12-31；请求窗口内有 5 个日期。

随后实际 `stock_zh_a_hist_sina` 为两只股票各返回 5 条日线。CLI 退出码 0，
研究生成数 2，日期阻断和失败数均为 0；最终 ZIP 完整性检查通过。
日历和行情未使用注入函数或合成返回值。详细元数据与哈希见
[机器记录](quick-calendar-live-20261122.json)，未提交原始行情行。

该运行不证明供应商列表内部无缺失、SS/SZ 一致、停牌处理完整或官方来源认证。
日历与价格均来自新浪，不具有独立来源交叉认证。此后上游内容变化可能改变哈希或结果。
默认滚动窗口有离线测试覆盖；本次真实运行使用上面的显式历史窗口。
无付费模型、交易操作或生产发布授权。
