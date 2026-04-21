# [P3969R0](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P3969R0/paper.md) - Fixing std::bit_cast of types with padding bits
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> struct S { };
> void f() {
>  bit_cast<char8_t>(S{}); // error: bit_cast<char8_t, S> is always undefined
>  bit_cast<unsigned char>(S{}); // OK, returns indeterminate value
>  bit_cast_zero_padding<char8_t>(S{}); // OK, returns char8_t{0}
> …
