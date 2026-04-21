# [P3642R4](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P3642R4/paper.md) - Carry-less product: std::clmul
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> bool parity(std::uint32_t x) {
>     return std::clmul(x, -1u) >> 31;
> }
