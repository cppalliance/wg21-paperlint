# [P2728R11](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P2728R11/paper.md) - Unicode in the Library, Part 1: UTF Transcoding
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> static_assert((u8"🙂" | views::to_utf32 | ranges::to<u32string>()) == U"🙂");
