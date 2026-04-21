# [P3440R2](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P3440R2/paper.md) - Add mask_from_count function to std::simd
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> ```
> void fn(std::span<float> data)
> {
> using V = simd::vec<float>;
> auto count = data.size();
> …
