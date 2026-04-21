# [P4006R0](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P4006R0/paper.md) - Transparent Function Objects for Shift Operators
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> // With P4006 - concise and self-documenting
> std::transform(values.begin(), values.end(),
> shifts.begin(),
> results.begin(),
> std::bit_lshift<>{});
