# P3642R4 — Carry-less product: std::clmul

LEWG · proposal

**Falls short on Q5 (no argument for fit with C++ language philosophy).**

### Q5 — No argument for fit with C++ language philosophy

The paper does not argue how carry-less multiplication fits with C++'s broader design philosophy such as zero-overhead abstraction, don't pay for what you don't use, or other language-wide principles.

**Would pass:** An explicit argument connecting the proposal to one or more of C++'s established design principles — e.g., that exposing hardware carry-less multiplication as a thin wrapper upholds zero-overhead abstraction, or that providing the operation in the standard library rather than requiring intrinsics supports portability and trust-the-programmer.
