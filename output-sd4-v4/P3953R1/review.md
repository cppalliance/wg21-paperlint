# [P3953R1](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P3953R1/paper.md) - Rename std::runtime_format
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> ```
> constexpr auto f(std::string_view fmt, int value) {
> return std::format(std::dynamic_format(fmt), value);
> }
> ```
