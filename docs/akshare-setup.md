# AKShare 可选真实数据接入

AKShare 是第三方数据采集库，不是官方数据真实性证明。当前只读适配器支持 A 股日线行情和巨潮公告索引；**不会自动执行交易**，也不会在单元测试时联网。

## Windows 本地安装（PowerShell）

```powershell
git clone https://github.com/rongbore/stock-market-Agent.git
cd stock-market-Agent
git fetch origin
git switch feat/v0.2-akshare-readonly-adapter
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-akshare.txt
.\.venv\Scripts\python.exe -c "import akshare; print(akshare.__version__)"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

若本地没有 Python 3.13，可先安装 Python，或改用受支持的其他 Python 版本；请先确认 AKShare 与该版本兼容。

## 获取 000776.SZ 日线数据

```powershell
.\.venv\Scripts\python.exe -m scripts.akshare_smoke --symbol 000776.SZ --start-date 2026-10-01 --end-date 2026-10-30 --output akshare_daily_snapshot.json
```

成功会输出记录数和日期范围，保存 `akshare_daily_snapshot.json`。数据文件不应提交到 Git；它带有 `source_content_verified=false` 标志。

如果失败，请保留完整异常堆栈、AKShare 版本、Python 版本及请求日期；遇到 403/429 应停止并检查官方访问政策，不要绕过限制。**不要把接口报错当作“当天无公告/行情”。**

## GitHub Actions

工作流 `.github/workflows/akshare-integration.yml` 使用 `workflow_dispatch` 手动触发。GitHub 通常要求工作流文件已经存在于默认分支，才会在 Actions 页面提供手动运行入口。因此 PR 分支中的新工作流不会自动出现在默认分支的 Actions 列表中。

合并 PR 后，进入 Actions → AKShare read-only integration → Run workflow，使用代码 `000776.SZ` 与日期范围。成功时会生成保留三天的 `akshare-daily-unverified` artifact。

## 验收标准

1. 离线单元测试及原有 E2E 测试通过。
2. AKShare 在可联网环境成功安装，记录具体版本。
3. 日线实际返回非空数据且日期、OHLC 检查通过。
4. 公告 PDF、来源真实性和历史时点可用性分别核验，不能仅凭 AKShare 返回值标为已验证。

PR #37 在完成真实网络测试前可保持 Draft。
