# Bind review assertions to a table review package

`review_package_sha256(package)` hashes canonical JSON of the complete review
package. `record_table_reviews(package, annotations)` requires both that hash
and the original PDF `file_sha256`. Changes to numeric text, hints, coordinates,
ordering or blockers invalidate the supplied review binding.

```python
from scripts.financial_table_review_annotations import review_package_sha256, record_table_reviews

annotations = {
    "file_sha256": package["file_sha256"],
    "package_sha256": review_package_sha256(package),
    "decisions": [{"candidate_index": 0, "decision": "accepted_by_reviewer",
                   "reviewer": "Reviewer name", "note": "Describe the page check."}],
}
result = record_table_reviews(package, annotations)
```

Decisions are `accepted_by_reviewer` or `rejected_by_reviewer`; both require a
nonempty reviewer label and note. Omitted candidates remain pending. Duplicate,
boolean, out-of-range indices, unknown annotation fields, stale fingerprints and
asserted verification flags are rejected. Empty packages are never complete.

These are caller-supplied review assertions. Hashes do not authenticate the PDF,
review package or reviewer identity. All original blockers are retained, including
consolidation scope. Even `all_candidates_decided=true` does not validate financial
values, prove publication time, or authorize release or merging; verification and
release-evidence flags stay false. This module does not execute or solicit reviews.
