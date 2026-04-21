# [P3983R0](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P3983R0/paper.md) - Object Representation for std::simd
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> template<typename T, typename Abi>
> auto abs_via_bitwise(basic_vec<T, Abi> v) -> basic_vec<T, Abi> {
> auto bits = std::bit_cast<basic_vec<uint_t, Abi>>(v);
> bits &= ~sign_bit_mask;
> return std::bit_cast<basic_vec<T, Abi>>(bits);
> …
