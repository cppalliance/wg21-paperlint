# [P4009R0](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P4009R0/paper.md) - A proposal for solving all of the contracts concerns
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> void f(int x) pre(std::pre(x >= 0));
> int f() post(r: std::post(r >= 0));
> contract_assert(std::cassert(x));
