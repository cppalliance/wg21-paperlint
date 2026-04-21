# [P2953R4](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P2953R4/paper.md) - Forbid defaulting operator=(X&&) &&
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> struct C {
> C& operator=(const C&) && = default;
> // C++26: Well-formed
> // Proposed: Unusable (deleted or ill-formed)
> };
> …
