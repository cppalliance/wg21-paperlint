# [P2929R2](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P2929R2/paper.md) - Proposal to add simd_invoke to std::simd
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> auto addsub(vec<float, 32> x, vec<float, 32> y)
> {
>  return simd::chunked_invoke(native_addsub, x, y);
> }
