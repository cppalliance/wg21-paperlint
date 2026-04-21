# [P3856R5](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P3856R5/paper.md) - New reflection metafunction - is_structural_type (US NB comment 49)
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> template<typename V> requires is_structural_v<decltype(V)> struct const_wrapper { static constexpr auto value = V; }; template<typename V> requires (!is_structural_v<decltype(V)>) struct const_wrapper<V>; // = delete; // or static_assert with a helpful note template<typename V> requires is_structural_v<decltype(V)> void register_token() { /* Register type V */ } template<typename T> void register_token(type_tag<T>) { /* Register type_tag<V> value */ }
