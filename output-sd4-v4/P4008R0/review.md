# [P4008R0](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P4008R0/paper.md) - Clean Modular Mode: Legacy Opt-out for C++
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> exclude std.legacy; // Opt into Clean Mode
> void clean_code() {
>     int arr[10];
>     int* p = arr;       // ERROR: Array decay is disabled
>     double d = 3.14;
> …
