# 快捷研究：无需手工准备日历 JSON

不方便在本地安装依赖时，可使用 [GitHub Actions 网页入口](quick-research-actions.md)。

安装可选行情依赖后，从仓库根目录运行：

```sh
python -m scripts.quick_market_research --symbols 000776.SZ 000001.SZ --upstream sina --allow-network --output research.zip
```

该命令默认使用北京时间截至昨日的最近 21 个自然日，先单独读取新浪供应商日历，
再采集指定数据源的日线并生成研究 ZIP。最多 5 只显式股票，不做自动选股。
也可同时指定历史窗口：

```sh
python -m scripts.quick_market_research --symbols 000776.SZ --upstream sina --start-date 2026-11-02 --end-date 2026-11-06 --allow-network --output historical-research.zip
```

解压后打开 `index.html`。成功项有研究页面，失败项有诊断；`calendar-source.json`
保留实际日历接口、版本、检索时间、供应商日期范围和完整日期列表的规范化哈希。
`collection.json`、标准化快照和原有证据仍在包内；`manifest.json` 按最终导出字节重算。
日历不来自行情返回行，不再要求手工复制每只股票的日历。

转存后可在解压前执行：

```sh
python -m scripts.verify_research_package --input research.zip
```

该命令只读、离线检查文件集合、大小和 SHA-256；成功不证明来源或研究结论可信。
输出与退出码见[研究包完整性校验](verify-research-package.md)。

## 必须保留的边界

- `--allow-network` 是显式只读请求开关；不调用付费模型或券商。
- 股票、数据源和日期必须合法，输出必须是新文件；输出写入预检在网络请求前完成。
- 日历只调用一次；只支持已知当前／旧 AKShare 接口，调用报错后不切换接口绕过失败。
- 供应商日期列表必须升序唯一且首末范围覆盖整个请求窗口；覆盖不足或窗口无日期时，
  在采集价格前停止，不补造交易日。此保守范围要求也可能拒绝真实节假日边界窗口。
- 一份新浪日期列表用于 SS/SZ 是未核验的调用方假设，不是交易所分别认证。
  单独下载日历不等于日历与价格来源彼此独立，缺失内部日期仍可能存在。
- 全部生成退出码 0；价格采集/日期检查部分或全部失败时生成诊断包并返回 2。
  日历本身下载或解析失败时无研究包，应使用已有显式日历入口或修正来源后再运行。
- 与现有批量模块一样，聚合体积超限、写入故障或中断可能没有输出包。
  不提供传输截止时间保证；AKShare 内部超时行为仍由供应商客户端决定。

已有经核查的本地日历时，继续使用[显式日历采集](collect-batch-research.md)或
[离线快照清单](local-snapshot-batch.md)。不要用供应商日历替代需要独立核验的发布证据。
