# [P4019R0](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P4019R0/paper.md) - constant_assert
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> [[gnu::always_inline]] constexpr void constant_assert(bool cond) { if (not __builtin_constant_p(cond)) [] [[gnu::error("constant assert - not constant")]] () { }(); if (not cond) [] [[gnu::noinline, gnu::error("constant assert - false")]] () { }(); }
