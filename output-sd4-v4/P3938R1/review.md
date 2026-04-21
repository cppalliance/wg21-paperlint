# [P3938R1](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P3938R1/paper.md) - Values of floating-point types
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> template <float>
> void f() {}
> 
> // "default" qNaN:
> template void f<std::bit_cast<float>(0x7fc00000)>();
> …
