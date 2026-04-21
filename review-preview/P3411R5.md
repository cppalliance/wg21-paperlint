# [P3411R5](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P3411R5/paper.md) - any_view
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> class MyClass {
>  std::unordered_map<Key, Widget> widgets_;
> public:
>  std::ranges::any_view<Widget> getWidgets();
> };
> …
