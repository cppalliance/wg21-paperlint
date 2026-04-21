# [P3899R1](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P3899R1/paper.md) - Clarify the behavior of floating-point overflow
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> constexpr std::float32_t min = std::numeric_limits<std::float32_t>::min(); // OK
> constexpr std::float32_t max = std::numeric_limits<std::float32_t>::max(); // OK
> constexpr std::float32_t inf = std::numeric_limits<std::float32_t>::infinity(); // OK
> constexpr std::float32_t nan = std::numeric_limits<std::float32_t>::quiet_NaN(); // OK
> 
> …
