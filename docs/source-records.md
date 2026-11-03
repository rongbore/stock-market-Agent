# Source record schema — v0.2 foundation

A source record contains `kind`, `provider`, `symbol`, `url`,
`published_at`, and `retrieved_at`. Both timestamps must have explicit
timezone offsets; URLs must be HTTPS without embedded credentials.

The validator rejects sources published after a supplied analysis cutoff.
**It does not fetch data, independently verify a publication timestamp,
authenticate a publisher, or guarantee historical point-in-time integrity.**
Future provider adapters must supply genuine source metadata and must not
invent missing publication times. For daily historical studies, choose a
market-specific cutoff with care, rather than assuming the calendar date
alone proves data availability.

Offline test: `python -m unittest discover -s tests -v`.
