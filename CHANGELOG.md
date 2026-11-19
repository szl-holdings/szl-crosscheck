# Changelog

## 0.4.0 (unreleased)

### Added

- source_binding: content-addressed cryptographic binding receipts for the evidence graph. Binds a claim, the exact source bytes it was grounded in, and an optional measured outcome into one receipt with deterministic hashing, optional owner-keyed HMAC signing, and fail-closed verification with explicit reason codes.
- Merkle bundles (szl.source-binding-bundle/v1): ordered per-item bindings for a benchmark run collapse into one verifiable root; drift in any single receipt or the run label is detectable offline with no network access.

Honest scope: digests prove which bytes were seen at bind time and that receipts have not drifted since; they do not prove sources are truthful, URLs still resolve, or that an outcome was honest before it was bound. Keys are owner-supplied at runtime and never stored in receipts.

## 0.3.2 (unreleased)


### Fixed

- Align runtime `__version__` with distribution metadata; add an installed-package version regression.
- Preserve differences between adjacent large integer measurements before normalizing relative deltas (#22).
- Preserve JSON value types when comparing receipt contexts and adapter cutoffs; require nonblank context identities and revisions (#23).

### Packaging

- Sync the canonical release gate, including isolated installed-wheel probes and dependency checks, and add its wheel-isolation regressions.

The implementation fixes above are changes since 0.3.1 already present on main. This release preparation changes version identity, packaging validation, and tests. Earlier releases are documented in the repository's GitHub Releases.
