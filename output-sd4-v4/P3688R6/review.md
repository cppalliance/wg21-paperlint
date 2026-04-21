# [P3688R6](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P3688R6/paper.md) - ASCII character utilities
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> int get_hex_digit_value(char8_t c) {
>     return c >= u8'0' && c <= u8'9' ? c - u8'0'
>          : c >= u8'A' && c <= u8'F' ? c - u8'A' + 10
>          : c >= u8'a' && c <= u8'f' ? c - u8'a' + 10
>          : -1;
> …
