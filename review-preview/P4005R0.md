# [P4005R0](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P4005R0/paper.md) - A proposal for guaranteed-(quick-)enforced contracts
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> void f(int x) entry_cond(x >= 0);
> void use_it()
> {
>  f(-42); // entry_cond not met, will not continue to the subsequent code
>  void(*p)(int) = f;
> …
