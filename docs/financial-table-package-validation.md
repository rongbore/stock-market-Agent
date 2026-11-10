# Table review-package structural acceptance

```sh
python -m scripts.financial_table_package_validation --package review.json --output validation.json
```

This optional check accepts the complete v0.1 output of the table review package
CLI. It requires explicit false verification flags, canonical metadata, unique
numeric cells, requested page membership and unchanged derived blocker lists.
Period hints must match the supplied preceding header text and containing
horizontal rectangle in the same table. Metric/unit hints must match exact label
fragments left of the number, on the same or consecutive label rows. Known scope
claims are refused: consolidation scope remains unresolved.

The output binds the canonical package hash and says `structure_valid=true` only
when these consistency checks pass. `release_evidence_accepted` and financial
verification remain false. No PDF is reopened or re-extracted: supplied geometry
and text can still be false, and unavailable full-table context cannot establish
that a header is the nearest eligible header or that intervening rows were empty.
This is neither source authentication nor proof that a financial value is correct.

Inputs are bounded to 5 MiB. Output is atomically replaced only after validation,
and cannot overwrite the input or target a symbolic link. Unknown package schema
fields fail rather than silently changing the contract.

Run `python -m unittest tests.test_financial_table_package_validation -v` for
tampered evidence, blocker/flag and actual-parser synthetic-table coverage.
