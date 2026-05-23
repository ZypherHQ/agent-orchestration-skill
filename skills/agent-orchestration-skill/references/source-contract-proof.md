# Source and Contract Proof

For dependency-backed behavior, do not guess APIs, defaults, timeouts, error semantics, or build behavior.

Before implementation when uncertainty exists:

- read the local source/types/config first;
- use Context7 for dependency docs when available;
- prefer official upstream docs/source over community answers;
- record the exact contract used in the Context Capsule, Dispatch Packet, or Handoff Packet;
- include test evidence showing the contract is satisfied.

For external docs, keep research bounded. The output should be a short contract digest, not a broad literature review.
