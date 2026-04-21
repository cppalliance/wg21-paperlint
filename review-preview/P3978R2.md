# [P3978R2](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P3978R2/paper.md) - constant_wrapper should unwrap on call and subscript
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> auto test1() {
>   constexpr int iota[4] = {0, 1, 2, 3};
>   auto x = std::cw<iota>;
>   return x[1]; // #1 OK
> }
> …
