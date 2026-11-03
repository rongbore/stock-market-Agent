# SEC filing metadata adapter — v0.2

The offline adapter in `scripts/sec_filings.py` converts the parallel arrays
in SEC submissions `filings.recent` into structured source records.

- It constructs SEC EDGAR archive URLs and uses `acceptanceDateTime` in
  America/New_York, converted to UTC. It does **not** rely on `filingDate`
  as the moment the filing became available.
- A timezone-aware cutoff can exclude filings accepted later.
- Input must be retrieved independently from official SEC data endpoints;
  this module does not fetch, authenticate, or verify filings.
- No network requests, DeepSeek keys, brokerage connections, or paid APIs
  are used by the tests.
- SEC EDGAR is primarily for US securities; it does **not** provide a
  general-purpose A-share/HK filing adapter.
- Source records are not yet integrated into TradingAgents reports or
  `run_provenance.json`. The separate source schema PR must be reviewed
  before integration.

Run `python -m unittest discover -s tests -v`.
