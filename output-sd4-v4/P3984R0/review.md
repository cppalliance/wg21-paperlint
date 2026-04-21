# [P3984R0](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P3984R0/paper.md) - A type-safety profile
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> void f(vector<int>& v) { v.push_back(7); } void g() { vector v = {1,2}; auto p = &v[1]; f(v); *p = 3; // must be prevented }
