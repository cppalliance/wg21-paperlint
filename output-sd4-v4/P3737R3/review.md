# [P3737R3](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P3737R3/paper.md) - std::array is a wrapper for an array!
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> std::array is just a wrapper for a C-style array:
> 
> template<class T, size_t N>
> struct array {
> T __array[N];
> …
