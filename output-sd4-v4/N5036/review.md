# [N5036](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/N5036/paper.md) - Extensions to C++ for Transactional Memory Version 2
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> [ Example 1 : unsigned int f() { static unsigned int i = 0; atomic do { ++i; return i; } } Each invocation of f (even when called from several threads simultaneously) retrieves a unique value (ignoring wrap-around). -end example ]
