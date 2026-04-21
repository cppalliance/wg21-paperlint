# [P3981R0](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P3981R0/paper.md) - Better return types in std::inplace_vector and std::exception_ptr_cast
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> ```
> auto range = get_some_elements();
> if (v.try_append_range(range).empty()) {
>  // success
> }
> …
