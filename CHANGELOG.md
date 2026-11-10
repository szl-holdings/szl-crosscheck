# Changelog

## 0.3.2 (unreleased)

### Fixed

- Align runtime `__version__` with distribution metadata; add an installed-package version regression.
- Preserve differences between adjacent large integer measurements before normalizing relative deltas (#22).
- Preserve JSON value types when comparing receipt contexts and adapter cutoffs; require nonblank context identities and revisions (#23).

### Packaging

- Sync the canonical release gate, including isolated installed-wheel probes and dependency checks, and add its wheel-isolation regressions.

The implementation fixes above are changes since 0.3.1 already present on main. This release preparation changes version identity, packaging validation, and tests. Earlier releases are documented in the repository's GitHub Releases.
