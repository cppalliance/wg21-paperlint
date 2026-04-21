# [P3181R1](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P3181R1/paper.md) - Atomic stores and object lifetimes
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> ```
> Thread A: fence(release);                // irrelevant for present purposes. a1: a->store(1, relaxed); Thread B: b1: r1 = a->load(acquire);     // sees 1. b2: delete a; Reallocating thread C: c1: b = new atomic<int>(0);    // gets the same location as a. c2: r2 = b->load(relaxed);     // Should not see the 1 from thread A.
> ```
