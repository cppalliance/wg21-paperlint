# [P2964R2](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P2964R2/paper.md) - User-defined element types in std::simd through trait-based vectorizable definition
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> struct Meters { float value; };
> struct Seconds { float value; };
> 
> // Type safety at scalar level
> Meters distance{100.0f};
> …
