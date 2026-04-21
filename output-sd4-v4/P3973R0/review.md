# [P3973R0](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P3973R0/paper.md) - bit_cast_as: Element type reinterpretation for std::simd
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> // basic element reinterpretation
> vec<uint8_t, 16> bytes = /*...*/;
> auto shorts = std::bit_cast_as<uint16_t>(bytes); // vec<uint16_t, 8>
> auto ints = std::bit_cast_as<uint32_t>(bytes); // vec<uint32_t, 4>
> auto longs = std::bit_cast_as<uint64_t>(bytes); // vec<uint64_t, 2>
