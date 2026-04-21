# P2929R2 — Proposal to add simd_invoke to std::simd

LEWG · proposal

**Falls short on Q5 (no argument connecting the proposal to C++ language philosophy).**

### Q5 — No argument connecting the proposal to C++ language philosophy

The paper does not argue how chunked_invoke aligns with any broader C++ design philosophy such as zero-overhead abstraction, composability, or trust-the-programmer.

**Would pass:** An explicit argument that chunked_invoke upholds a recognized C++ design principle — e.g., zero-overhead abstraction over manual chunk/cat patterns, or preservation of trust-the-programmer by letting users access platform intrinsics safely.

### Q7 — Design alternatives (gate REFER)

Gate declined to confirm or reject. §4.1.1 names `chunked_invoke_indexed` vs probing with a rejection reason ("precedent set by simd::permute"). §4.2 explains why prototype-based chunking is not supported ("complicated and error-prone"). These are internal design variants. Whether the design space here is genuinely narrow enough to satisfy Q7 with one-or-two internal alternatives is a judgment call — your read wanted.
