# P3953R1Rename std::runtime_format


## Published Proposal, 2026-01-17



Author:
Victor Zverovich
Audience:
LEWG
Project:
ISO/IEC 14882 Programming Languages — C++, ISO/IEC JTC1/SC22/WG21











## 1. Abstract

[P2918] introduced std::runtime_format to allow opting out of compile-time
format string checks in std::format. Subsequently, [P3391] made std::format usable in constant evaluation. As a result, std::runtime_format can now be evaluated at compile time, making its name misleading. This paper
proposes renaming std::runtime_format to std::dynamic_format to better
reflect its semantics and avoid confusion in constexpr contexts.


## 2. Changes since R0



Use the actual proposed name in the "after" example.



## 3. Motivation

The name std::runtime_format was accurate when introduced in [P2918], as
format strings were not usable in constant evaluation. However, with the
adoption of constexpr std::format, the term runtime no longer reliably
describes the behavior of std::runtime_format.

Consider the following code:

```
constexpr auto f(std::string_view fmt, int value) {
return std::format(std::runtime_format(fmt), value);
}

```

Despite its name, std::runtime_format can be evaluated at compile time.
This creates a semantic mismatch:



"runtime" suggests evaluation timing


The facility actually describes how the format string is obtained.


The real distinction is not when formatting occurs, but how the format string
is provided and validated. The term runtime conflates it with evaluation time.


## 4. Proposed Naming: std::dynamic_format

The proposed name std::dynamic_format reflects the actual semantics:



The format string is dynamically provided


The format string is not a compile-time constant


The validation is deferred (but may still occur during constant evaluation)


This aligns with existing terminology std::format such as dynamic format
specifiers (check_dynamic_spec).

Example with proposed name:

```
constexpr auto f(std::string_view fmt, int value) {
return std::format(std::dynamic_format(fmt), value);
}

```

This reads naturally and avoids semantic contradiction.


## 5. Impact on existing code

If this is adopted for C++26 there will be no impact on existing code since std::runtime_format is a C++26 feature.




## References


### Informative References


[P2918]
Victor Zverovich. Runtime format strings II. URL: https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2023/p2918r2.html
[P3391]
Barry Revzin. `constexpr std::format`. URL: https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2025/p3391r2.html