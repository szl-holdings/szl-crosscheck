# Covenant exact chain/Merkle comparison

`szl_crosscheck.covenant` provides a standard-library-only, independent implementation of receipt-chain validation and RFC 6962 Merkle roots. It imports neither Khipu nor Eclipse. Khipu uses recursive subtree splitting; this implementation uses an iterative carry frontier and a right-to-left final fold.

`crosscheck_covenant(reference_chain, candidate_chain, observed_root=..., expected_root=...)` consumes both complete chains, recomputes every link and payload digest, compares exact framed chain identities, and checks both roots against the caller-held anchor and producer result. It returns CONSISTENT, DIVERGENT, or INVALID. Retrieval score tolerances do not apply.

The profile uses Python JSON with sorted string keys, compact separators, ASCII escaping, and finite numbers. It is deliberately the existing SZL Python chain profile, not a claim of general cross-language JSON canonicalization. Chains have 1..4096 receipts. Leaves are lowercase 64-character hex digests. Receipts have bounded depth, node count, and serialized size. The standalone Merkle helper also supports the RFC empty-tree root.

## Claim boundary

CONSISTENT means exact chain and Merkle agreement only. This package does not verify STH signatures, trusted witness membership, timestamp freshness, independent operators or hosts, tenant authorization, or append-only log continuity. It never authorizes execution or recall. An unkeyed digest is an integrity identifier, not an authenticated provenance signature.

Covenant v2 evidence tooling in szl-eclipse binds the actual loaded modules to clean, explicitly selected commits, uses this package as a comparator, and separately exercises Khipu signature/recall verification using synthetic fixture keys. That composition does not turn this module into an independent cryptographic witness verifier.

## Validation

`python -m pytest tests -q` includes fixed empty/single-leaf vectors; iterative-versus-recursive roots for 0..65, 127..129, 255..257, and 4096 leaves; valid positive controls; changed reference/candidate chains; valid truncation and rehashed chains; malformed payloads and roots; bounded JSON inputs; and non-mutation of caller data.

No witness keys, signatures, or third-party runtime dependencies are stored in this package.
