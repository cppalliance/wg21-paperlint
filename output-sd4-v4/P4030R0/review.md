# [P4030R0](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P4030R0/paper.md) - Endian Views
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> constexpr vector<uint32_t> utf16be_to_utf32be(
>     const vector<uint16_t>& utf16be_data) {
>   return utf16be_data
>     | views::from_big_endian
>     | views::as_char16_t
> …
