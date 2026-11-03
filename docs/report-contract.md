# Report artifact contract (v0.2)

Run `python scripts/report_contract.py results/reports` after a successful analysis.
The validator checks that at least one `complete_report.html` exists, is
nonempty, and includes an HTML root tag. Tests run offline with
`python -m unittest discover -s tests -v`.

This is a **structural check only**. It does not establish accuracy, completeness,
source provenance, point-in-time correctness, or investment merit.

Integration into `.github/workflows/analyze.yml` should be reviewed together
with the separate report-upload failure handling PR to avoid conflicting edits.
