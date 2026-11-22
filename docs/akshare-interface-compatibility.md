# AKShare daily-interface compatibility

The actual 2026-11-18 dual-source run failed on a removed legacy attribute before
both sources could complete. Compatibility is based on callable attributes, not
an assumed package version or a silent relabeling of data.

| Upstream | Selection order | Explicit volume unit |
| --- | --- | --- |
| Eastmoney | `stock_zh_a_hist_em`, then `stock_zh_a_hist` | `lots_100_shares` |
| Sina | `stock_zh_a_hist_sina`, then `stock_zh_a_daily_sina`, then `stock_zh_a_daily` | `shares` |

Only an absent attribute (`AttributeError`, including the library's rename hint)
permits checking the next documented name. An existing noncallable attribute is
a dependency error. A selected function's transport, parameter or response error
never causes a call to another interface name. Sina's current `hist` function is
called with `period="daily"`; earlier daily-only names receive no period argument.
All requested dates, symbol conventions, adjustments and required OHLCV columns
remain explicit. Unknown columns/units still fail existing validation.

Snapshots record the **actual selected interface** and installed AKShare version;
new calls are never written as legacy interfaces. The backtest data contract
accepts only the documented current/legacy interfaces for the matching upstream
and unit. Eastmoney's standalone snapshot quality check accepts its current name.
The cross-source comparator already converts only explicit lots/shares units;
its arithmetic is unchanged.

Dual-source smoke diagnostics now classify an `AttributeError` as
`runtime_or_dependency` / `interface_unavailable`, without exception text or a
retry. The other source is still attempted. Known missing-name/no-callable cases
raised by the adapter remain safe runtime dependency failures. Source agreement
and authenticity flags are not promoted by interface compatibility.

## Official contract checked 2026-11-19

- [AKShare stock quote documentation](https://akshare.akfamily.xyz/data/stock/stock_quote.html):
  Eastmoney `hist_em` takes a six-digit symbol, explicit period/date/adjustment
  parameters, Chinese OHLCV columns and lot volume. Sina `hist_sina` takes a
  market-prefixed symbol, supports daily period, English OHLCV columns and share
  volume.
- [Official changelog](https://akshare.akfamily.xyz/changelog.html): 1.20.46 renamed
  the legacy Eastmoney historical and Sina daily functions; 1.20.64 renamed Sina
  `daily_sina` to `hist_sina` and added weekly/monthly periods while retaining
  daily behavior.

The compatibility tests use synthetic provider responses and intentionally
missing attributes. They cover both current APIs, historical API names, actual
interface metadata, unchanged unit normalization, unavailable/noncallable APIs,
no fallback after a failed call, and continuing the other source with sanitized
diagnostics. They are not fresh successful upstream acceptance. A separate
read-only live run must establish current endpoint availability; new source
contracts outside these exact names remain unsupported.

## Provider exception isolation and rate limits

The dual-source fetch boundary also handles optional AKShare provider exceptions
that are not subclasses of the older built-in exception tuple. Fixed diagnostics
are written and the other source is still attempted; raw messages are not copied.
Process cancellation such as `KeyboardInterrupt` and `SystemExit` still propagates.

AKShare's documented `RateLimitError` / `Push2RateLimitError` signals are identified
through their known provider classes before Requests connection classification.
They emit `rate_limit` and are **not retried**. Ordinary transient Requests/built-in
connection failures retain the existing bounded retry policy. This does not bypass
upstream limits or establish provider availability. See the
[official FAQ](https://akshare.akfamily.xyz/faq.html) and the installed AKShare
`exceptions` / `utils.http` classes. Tests simulate their exception hierarchies;
no successful live request or limit recovery is claimed by these checks.
