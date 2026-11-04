# Source record schema — v0.2 foundation

A source record contains `kind`, `provider`, `symbol`, `url`,
`published_at`, and `retrieved_at`. Both timestamps must have explicit
timezone offsets; URLs must be HTTPS without embedded credentials.

The validator always rejects sources **published** after a supplied analysis cutoff.
With `require_retrieved_by_cutoff=True`, an explicit `analysis_cutoff` is required;\nit also rejects sources retrieved after
that cutoff. This strict point-in-time mode requires a contemporaneous retrieval
record and may exclude legitimate historical documents collected retrospectively.
The default allows retrospective retrieval but does **not** verify historical
point-in-time availability or authenticity.
**It does not fetch data, independently verify a publication timestamp,
authenticate a publisher, or guarantee historical point-in-time integrity.**
Future provider adapters must supply genuine source metadata and must not
invent missing publication times. For daily historical studies, choose a
market-specific cutoff with care, rather than assuming the calendar date
alone proves data availability.

Offline test: `python -m unittest discover -s tests -v`.
