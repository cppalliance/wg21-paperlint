# [P3982R0](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P3982R0/paper.md) - Fix meaning of strided_slice::extent for C++26
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> ```
> 
> auto smd = sumdspan(md, strided_slice{cw<0>, cw<5>, md.extents()[0] / 5})
> 
> ```
