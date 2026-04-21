# [P0876R22](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P0876R22/paper.md) - fiber_context - fibers without scheduler
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> 1 void foo(){
> 2     fiber_context f{[](fiber_context&& m){
> 3         m=std::move(m).resume(); // switch to 'foo()'
> 4         m=std::move(m).resume(); // switch to 'foo()'
> 5         ...
> …
