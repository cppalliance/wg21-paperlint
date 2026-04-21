# [P4012R0](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P4012R0/paper.md) - value-preserving consteval broadcast to simd::vec
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> int n = 1; // ------no change: --------simd::vec< float > x = 1.f; // x = 0x5EAF00D; // ill-formed // x = n; // ill-formed x = static_cast < float >(n); // OK static_assert (constructible_from <V, int >); // ------different: --------x = 1; // OK // x = static_cast <simd::vec<float >>(n); // ill-formed pow(x, 3); // OK static_assert (convertible_to < int , V>); // opposite common_type_t <V, int > y = x; // V
