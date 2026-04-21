# [P3816R2](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P3816R2/paper.md) - Hashing meta::info
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> consteval auto compile_time_function() -> void
> {
> const auto hasher = consteval_hash<meta::info>{}; // proposed
> const size_t h = hasher(^^::);
> 
> …
