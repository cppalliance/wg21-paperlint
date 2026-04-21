# [P3856R4](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P3856R4/paper.md) - New reflection metafunction - is_structural_type (US NB comment 49)
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> template<auto V> requires is_structural_type_v<decltype(V)> struct const_wrapper { static constexpr auto value = V; }; template<auto V> requires (!is_structural_type_v<decltype(V)>) struct const_wrapper<V>; // = delete; // or static_assert with a helpful note template<auto V> requires is_structural_type_v<decltype(V)> void register_token() { /* Register type V */ } template<class T> void register_token(type_tag<T>) { /* Register type_tag<V> value */ }
