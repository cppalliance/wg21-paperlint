# [P3822R1](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P3822R1/paper.md) - Conditional noexcept specifiers in compound requirements
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> template<typename F, bool noexc>
> concept invocable = requires(F f) {
> { f() } noexcept(noexc);
> };
> template<bool noexc>
> …
