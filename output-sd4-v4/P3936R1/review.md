# [P3936R1](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P3936R1/paper.md) - Safer atomic_ref::address
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> using value_type = remove_cv_t<T>; using address-return-type = COPYCV(T, void)*; //expos static constexpr size_t required_alignment = implementation-defined; // ... constexpr T* address-return-type address() const noexcept;
