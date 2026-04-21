# [P4021R0](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P4021R0/paper.md) - compile_assert(expression, message)
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> static void log_message(const char * p) {
>     compile_assert(p, "check not null");
>     printf("%s\n", p);
> }
