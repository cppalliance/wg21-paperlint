Document Number:

P3844R3

Date:

2026-02-06

Reply-to:

Matthias Kretz <m.kretz@gsi.de>

Audience:

LWG

Target:

C++ 26

## Restore simd::vec broadcast from int

## ABSTRACT

The broadcast constructor in the Parallelism 2 TS allowed construction from ( unsigned ) int , allowing e.g. vec<float>() + 1 , which is ill-formed in the CD. This breaks existing code that gets ported from the TS to std::simd . The design intent behind std::simd was for this to work. However, the understanding in LEWG appeared to be that we can't get this right without constexpr function arguments getting added to the language. This paper shows that a consteval constructor overload together with constexpr exceptions can resolve the issue for C ++ 26 and is a better solution than constexpr function arguments would be.

|    |                                                    |                                                      |   CONTENTS |
|----|----------------------------------------------------|------------------------------------------------------|------------|
|  1 | Changelog                                          |                                                      |          1 |
|    | 1.1                                                | Changes from revision 0 . . . . . . . . . . .        |          1 |
|    | 1.2                                                | Changes from revision 1 . . . . . . . . . . . .      |          1 |
|    | 1.3                                                | Changes from revision 2 . . . . . . . . . . .        |          1 |
|  2 | Straw                                              | Polls                                                |          2 |
|    | 2.1                                                | LEWG @ Kona 2025 . . . . . . . . . . . . . . .       |          2 |
|  3 | Motivation                                         |                                                      |          2 |
|  4 | Design space                                       | Design space                                         |          4 |
|    | 4.1                                                | potentially-convertible-to . . . . . . . . . . .     |          4 |
|    | 4.2                                                | Status quo . . . . . . . . . . . . . . . . . . . . . |          5 |
|    | 4.3                                                | More constrained constexpr overload . . .            |          5 |
|    | 4.4                                                | More constrained consteval overload . . .            |          7 |
|    | 4.5                                                | How to handle bad value-preserving casts             |          8 |
|  5 | Differences                                        | Differences                                          |          8 |
|  6 | Should common_type really change? What if it does? | Should common_type really change? What if it does?   |          9 |
|  7 | broadcast as immediate-escalating expression       | broadcast as immediate-escalating expression         |          9 |
|    | 7.1                                                | escalating [simd.math] functions . . . . . . .       |         10 |
|    | 7.2                                                | move conversions before math calls . . . .           |         10 |
|    | 7.3                                                | Alternative via 'expression alias' P2826 . .         |         11 |
|    | 7.4                                                | The importantance of conversions . . . . .           |         11 |
|  8 | Implementation experience                          | Implementation experience                            |         12 |
|  9 | Recommendation                                     | Recommendation                                       |         12 |

| 10   | Wording for consteval broadcast   | Wording for consteval broadcast   |   12 |
|------|-----------------------------------|-----------------------------------|------|
|      | 10.1                              | Feature test macro . . .          |   12 |
|      | 10.2                              | Modify [simd.expos] . . .         |   13 |
|      | 10.3                              | Modify [simd.expos.defn]          |   13 |
|      | 10.4                              | Modify [simd.overview] .          |   13 |
|      | 10.5                              | Modify [simd.ctor] . . .          |   14 |
| 11   | Wording for [simd.math]           | Wording for [simd.math]           |   14 |
|      | 11.1                              | Modify [simd.expos] . . .         |   14 |
|      | 11.2                              | Modify [simd.expos.defn]          |   15 |
|      | 11.3                              | Modify [simd.syn] . . . .         |   16 |
|      | 11.4                              | Modify [simd.math] . . .          |   22 |
| A    | really_convertible_to definition  | really_convertible_to definition  |   32 |
| B    | Bibliography                      | Bibliography                      |   32 |

1

## 1.1

## Previous revision: P3844R0

- Constrain the consteval ctor to arithmetic types that naturally convert to the basic\_vec 's value-type (checked via common\_type ).
- Discuss consequence on common\_type (besides convertible\_to ).
- Discuss consequence on [simd.math].
- Discuss consteval ctor as immediate-escalating expression.
- Discuss potential consequences for [simd.math].

## 1.2

## Previous revision: P3844R1

- Remove proposed polls.
- Update wording to remove unnecessary simd-broadcast-arg .
- Add [simd.math] wording changes to match original design intent (as if it were an explicit overload set).
- Drive-by wording fixes/improvements to [simd.math]:
- -math-common-simd-t<V0, V1> did not work for non-default ABI tag combinations with scalars.
- -Spell out precondition on integral abs .

## 1.3

## Previous revision: P3844R2

- Restore incorrectly removed math-floating-point wording.
- Fix incorrect constraint in hypot expample.
- Split wording section into the consteval ctor part and the [simd.math] part.

## CHANGELOG

changes from revision 0

changes from revision 1

changes from revision 2

## 2

2.1

## STRAW POLLS

lewg @ kona 2025

Poll: We would like to pursue fixing the issue brought up in 'DE-286 29.10.7.2p1-4 [simd.ctor] Add consteval broadcast constructor from constant integer (P3844)' for C++26.

<!-- image -->

Poll: Resolve 'DE-286 29.10.7.2p1-4 [simd.ctor] Add consteval broadcast constructor from constant integer (P3844)' by adding a consteval broadcast overload for value-preserving conversions, and re-specify in [simd.math] and send to LWG.

```
SF F N A SA 3 15 1 0 0
```

## 3 MOTIVATION

It is very common in floating-point code to simply write e.g. * 2 rather than * 2.f when multiplying a float with a constant:

```
float f( float x) { return x * 2; } // converts 2 to float (at compile time) float g( float x) { return x * 2.; } // converts x to double (at run time) float h( float x) { return x * 2.f; } // no conversions
```

More importantly, using * 2 works reliably in generic code, where the type of x could be any arithmetic type.

Since this is so common, std::experimental::simd<T> made an exception for int in the broadcast constructor to not require value-preserving conversions. Consequently, the TS behavior is:

```
using floatv = std::experimental::native_simd < float >; floatv f(floatv x) { return x * 2; } // converts 2 to float and broadcasts (at // compile time) floatv g(floatv x) { return x * 2.; } // ill-formed floatv h(floatv x) { return x * 2.f; } // broadcasts 2.f to floatv
```

When porting existing code written against the TS to C ++ 26, the first step is to adjust the types:

```
using floatv = std::experimental::native_simdsimd::vec< float >;
```

Except for uses of std::experimental::where , which need to be refactored to use simd::select , the remaining code should work. The one place where it doesn't work is code such as in function f , where 2 needs to be replaced:

```
floatv f(floatv x) { return x * 2std::cw<2>; }
```

Since we don't have constexpr function arguments in the language, std::simd works around it by recognizing integral-constant-like / constant-wrapper-like types, that encode a value into a type. This, however, comes at a compile-time cost. Every different value leads to a template specialization of both constant\_wrapper and a basic\_vec broadcast constructor (with it's helper types/concepts to determine whether the specialization is allowed). Consequently, for vec<float> , I would recommend to always use an f suffix rather than std::cw .

But that solution is fairly limited, since we don't have literals for 8-bit and 16-bit integers in the language. A function template like

```
template <simd_integral V> V f(V x) { return x + 1; // ill-formed for V::value_type = (u)int8_t , (un)int16_t , and uint32_t }
```

needs to use x + V(1) 1 . A clever user might write x + '\1' instead. But that fails for the char type with different signedness.

Consequently, users would need to get used to writing explicit conversions for the constants they use in std::simd code. That's not only verbose and ugly, it is also error-prone. Whenever we coerce our users into writing explicit conversions, then value-changing conversions cannot be diagnosed as erroneous anymore. An explicit static\_cast<uint64\_t>(-1) means 0xffff'ffff'ffff'ffff , whereas uint64\_t x = -1 could have been intended to mean 0x0000'0000'ffff'ffff or is a result of a logic flaw in the code. E.g., GCC's -Wsign-conversion diagnoses the latter, but not the former 2 .

If, with C ++ 26, our users are starting to explicitly convert their int constants to basic\_vec , then the interface of basic\_vec is at least in part guilty for introducing harder to find bugs.

Tony Table 1 presents an example of the solution 3 . Note that the code on the left will never warn about the value-changing conversion, even with all conversion related warnings enabled. This is due to the explicit conversion, which is telling the compiler 'I know what I'm doing; no need to warn me about it'.

```
before with P3844R3 template <simd_floating_point V> V f(V x) { return x + V(0x5EAF00D); } f(vec< double >()); // OK // compiles but adds 99282960 instead of 99282957 f(vec< float >()); // compiles but adds infinity instead of 99282957 f(vec<std::float16_t >()); template <simd_floating_point V> V f(V x) { return x + 0x5EAF00D; } f(vec< double >()); // OK // ill-formed: value -changing conversion f(vec< float >()); // ill-formed: value -changing conversion f(vec<std::float16_t >());
```

TonyBefore/After Table 1: Add an offset

Asafer implementation of the code on the left side of Tony Table 1 (without this paper) would have been to write x + std::cw<0x5EAF00D> instead. Then the value-changing conversion would have resulted in a constraint failure on the broadcast constructor. However, V(0x5EAF00D) is shorter and

1 explicit conversion to basic\_vec allows conversions that are not value-preserving

2 And that's useful, because the former says 'I'm intentionally doing this conversion, no need to warn.'

3 I got bitten by this in my std::simd unit tests

needs fewer template instantations. I expect most users (including myself) will/do not use std::cw all over the place.

## 4

## DESIGN SPACE

In the design review of P1928 of this issue of the broadcast constructor it was overlooked (and never discussed) that a consteval overload of the broadcast constructor could solve this problem. Before constexpr exceptions, we would have worded it to be ill-formed (by unspecified means) if the value changes on conversion to the basic\_vec 's value-type. Now that we have constexpr exceptions, we can specify a consteval broadcast overload that throws on value-changing conversion. If the caller cares, the exception can even be handled at compile time. (I believe it should not throw in C ++ 26, for a minimal change to the WD this late in the C ++ 26 cycle.)

Ordering the overloads for overload resolution is tricky, which is another reason why we should consider this issue before C ++ 26 ships and potentially take action even if we don't add a consteval overload. Overload resolution does not take consteval into account. The process of finding candidate functions ([over.match.funcs.general]), however, does remove explicit constructors from the candidate set if the context does not allow the explicit constructor to be called.

## 4.1

## potentially-convertible-to

R0 proposed to allow any conversion from arithmetic type U , that satisfies convertible\_to<value\_-type> and does not satisfy value-preserving-convertible-to <value\_type> via the consteval broadcast constructor. This was too broad, since it would lead to vec<float>() + 1.5 being valid (of type vec<float> ). While technically not wrong (no loss on conversion from 1.5 ), it is too surprising that an operation involving a double operand is evaluated in single precision.

Therefore, R1 of this paper tightens the constraints for the consteval broadcast to producing a less surprising common type. If the given constant is of arithmetic type T , then we now require common\_type\_t<T, value\_type> to be value\_type . Since common\_type\_t<double, float> is double , the expression vec<float>() + 1.5 becomes ill-formed. However, this rule alone still breaks the case of vec<short>() + 1 , which the user cannot changed to use a short literal (because we don't have one). The TS made an explicit exception for int and unsigned int 4 , which is what we still need for integer types (with lower rank than int ).

So the final potentially-convertible-to constraint looks like this:

```
template < typename From, typename To> concept potentially-convertible-to = is_arithmetic_v <From> && convertible_to <From, To> && ! value-preserving-convertible-to <From, To> && (is_same_v <common_type_t <From, To>, To> || (is_same_v <From, int > && is_integral_v <To>) || (is_same_v <From, unsigned > && unsigned_integral <To>));
```

4 The TS broadcast constructor has a constraint '[…], or From is int , or From is unsigned int and value\_type is an unsigned integral type.'

## 4.2

status quo

The following code shows the properties of the current broadcast constructor. See Appendix A for the definition of the really\_convertible\_to concept.

```
using V = simd::vec< float >; template < typename T> struct X { explicit operator T() const ; }; template < typename ... Ts> concept has_common_type = requires { typename std::common_type_t <Ts...>; }; static_assert (not std::convertible_to <X< float >, V>); static_assert ( std::convertible_to < float , V>); static_assert ( std::convertible_to < short , V>); static_assert ( really_convertible_to < short , V>); static_assert (not std::convertible_to < int , V>); static_assert (not really_convertible_to < int , V>); static_assert ( std::constructible_from <V, X< float >>); static_assert (not std::constructible_from <V, X< short >>); static_assert ( std::constructible_from <V, double >); static_assert ( std::constructible_from <V, float >); static_assert ( std::constructible_from <V, short >); static_assert ( std::constructible_from <V, int >); static_assert (not has_common_type <V, double >); static_assert (not has_common_type <V, int >); V f( int n, short m, std::reference_wrapper < int > l, std::reference_wrapper < float > f) { V x = '\1'; // OK x = 1; // ill-formed x = 0x5EAF00D; // ill-formed x = V(n); // OK x = m; // OK x = l; // OK (because convertible_to <decltype(l), float > is true) x = f; // OK x = 1.1; // ill-formed x = V(1.1); // OK x = X< float >(); // ill-formed: no match for operator= (no known conversion …[]) x = float (X< float >()); // OK (obvious) x = V(X< float >()); // OK }
```

## 4.3

more constrained constexpr overload

A possible solution selects the existing ( constexpr ) broadcast constructor for everything but the cases where the value of the argument needs to be checked. Thus, we need the existing constructor to always be more constrained ([temp.constr.order]) than the consteval constructor. The consteval constructor can then only be selected if the other constructor is not part of the candidate set at all (via explicit ).

Sketch:

```
template < class From, class To> concept simd-consteval-broadcast-arg = explicitly-convertible-to <From, To>; template < class From, class To> concept simd-broadcast-arg = simd-consteval-broadcast-arg <From, To> and true; template < class T> class basic_vec { public : template < simd-broadcast-arg <T> U> constexpr explicit ( see below ) basic_vec(U&&); // #1 template < simd-consteval-broadcast-arg <T> U> consteval basic_vec(U&&); // #2 // Mandates: potentially-convertible-to <remove_cvref_t <U>, value_type > };
```

Now every explicit call to the broadcast constructor will always select #1 . Implicit calls to the broadcast constructor will select #1 if the condition in the explicit specifier is false . Otherwise, #1 is not part of the candidate set and #2 is called. Thus, the condition on the explicit specifier determines whether the consteval overload is chosen or not.

```
static_assert ( std::convertible_to <X< float >, V>); // different to status quo static_assert ( std::convertible_to < float , V>); static_assert ( std::convertible_to < short , V>); static_assert ( really_convertible_to < short , V>); static_assert ( std::convertible_to < int , V>); // different to status quo static_assert (not really_convertible_to < int , V>); static_assert ( std::constructible_from <V, X< float >>); static_assert (not std::constructible_from <V, X< short >>); static_assert ( std::constructible_from <V, double >); static_assert ( std::constructible_from <V, float >); static_assert ( std::constructible_from <V, short >); static_assert ( std::constructible_from <V, int >); static_assert (not has_common_type <V, double >); static_assert ( has_common_type <V, int >); // it's vec<float> V f( int n, short m, std::reference_wrapper < int > l, std::reference_wrapper < float > f) { V x = '\1'; // OK x = 1; // OK (different to status quo) x = 0x5EAF00D; // ill-formed x = V(n); // OK x = m; // OK x = V(l); // OK x = f; // OK x = 1.1; // ill-formed x = V(1.1); // OK x = X< float >(); // ill-formed: static_assert failed (different reason to status quo) x = float (X< float >()); // OK (obvious) x = V(X< float >()); // OK }
```

## 4.4

## more constrained consteval overload

A viable alternative involves the removal of explicit conversions from arithmetic types to basic\_-vec . The consteval constructor is declared with additional constraints over the existing constructor (satisfies convertible\_to , is\_arithmetic\_v , and not value-preserving conversion). This way the consteval constructor is always chosen if the conversion of the given (arithmetic) type to value\_-type is potentially-convertible-to . Otherwise, the constexpr overload is used.

Sketch:

```
template < class From, class To> concept simd-broadcast-arg = explicitly-convertible-to <From, To>; template < class From, class To> concept simd-consteval-broadcast-arg = simd-broadcast-arg <From, To> && potentially-convertible-to <remove_cvref_t <From>, To>; template < class T> class basic_vec { public : template < simd-broadcast-arg <T> U> constexpr explicit ( see below ) basic_vec(U&&); // #1 template < simd-consteval-broadcast-arg <T> U> consteval basic_vec(U&&); // #2 };
```

Here, every explicit call to the broadcast constructor with a type U that satisfies potentiallyconvertible-to <T> is equivalent to an implicit conversion, since the consteval overload is viable and more constrained. Every type with a value-preserving conversion to T will select #1 (because of the constraint on #2 ). Every non-arithmetic type (notably, user-defined types with conversion operator to some arithmetic type) will continue to work as today, since #2 is not viable.

```
static_assert (not std::convertible_to <X< float >, V>); // equal to status quo / different to above static_assert ( std::convertible_to < float , V>); static_assert ( std::convertible_to < short , V>); static_assert ( really_convertible_to < short , V>); static_assert ( std::convertible_to < int , V>); // different to status quo / equal to above static_assert (not really_convertible_to < int , V>); static_assert ( std::constructible_from <V, X< float >>); static_assert (not std::constructible_from <V, X< short >>); static_assert ( std::constructible_from <V, double >); static_assert ( std::constructible_from <V, float >); static_assert ( std::constructible_from <V, short >); static_assert ( std::constructible_from <V, int >); static_assert (not has_common_type <V, double >); static_assert ( has_common_type <V, int >); // it's vec<float> V f( int n, short m, std::reference_wrapper < int > l, std::reference_wrapper < float > f) {
```

```
V x = '\1'; // OK x = 1; // OK (different to status quo / equal to above) x = 0x5EAF00D; // ill-formed x = V(n); // ill-formed (different to both) x = m; // OK x = V(l); // OK x = f; // OK x = 1.1; // ill-formed x = V(1.1); // OK x = X< float >(); // ill-formed: no match for operator= (no known conversion …[]) x = float (X< float >()); // OK (obvious) x = V(X< float >()); // OK }
```

## 4.5

how to handle bad value-preserving casts

The consteval broadcast overload needs to be ill-formed if the argument value cannot be converted to the value type without changing the value. This can be achieved via the mechanism used in ([simd.bit]) for bit\_ceil . The constructor would spell out a precondition followed by Remarks: An expression that violates the precondition in the Preconditions : element is not a core constant expression ([expr.const]).

The alternative that was mentioned before is to throw an exception (at compile time). Since in basically all cases such an exception would not be caught at compile time, the program becomes ill-formed. The ability to catch the exception allowed me to hack up a really\_convertible\_to concept. But otherwise, the utility of using an exception here seems fairly limited. The main reason for using an exception is better diagnostics on ill-formed programs. If we decide to add the consteval constructor for C ++ 26, then we might want to delay the new exception type for C ++ 29, though.

## 5

Differences between the status quo and the two alternatives above:

|                             | status quo   | Section 4.3   | Section 4.4   |
|-----------------------------|--------------|---------------|---------------|
| convertible_to<X<float>, V> | false        | true          | false         |
| convertible_to<int, V>      | false        | true          | true          |
| common_type_t<V, int>       | 8            | V             | V             |
| x = 1;                      | 8            | 4             | 4             |
| x = V(n);                   | 4            | 4             | 8             |

Note that X<float> is never implicitly convertible to vec<float> , so the solution in Section 4.3 lies about that. Also while some values of constant expressions of type int are convertible to vec<float> , it is not true in general that int is convertible to vec<float> .

DIFFERENCES

## 6 SHOULD COMMON\_TYPE REALLY CHANGE? WHAT IF IT DOES?

After convertible\_to changes, consequently also conditional expressions such as false ? vec< float>() : 1 become valid. common\_type\_t<vec<float>, int> simply reflects that. The surprising aspect, similar to convertible\_to , is that this isn't true in general.

If we accept that common\_type changes (we don't have to, as we can specialize common\_type ), this has consquences on [simd.math]. Multi-argument math functions use common\_type in it's specification to spell out the design intent to match <cmath> overloads of these functions. For some background, let's use 2-arg std::hypot as an example. C defines three functions hypot , hypotf , and hypotl . C++ then overloads hypot(double, double) with hypot(float, float) , and hypot(long double, long double) (and since C ++ 23 also std::floatN\_t ). It is not correct to implement this as template <class T> hypot(T, T) , since a call to hypot(1., 1) would then be ill-formed. With explicit overloads hypot(1., 1) calls hypot(double, double) .

The std::simd (and TS) math overloads were designed to match that behavior. The mechanism for this was spelled out after the design went into LWG wording review for C ++ 26. For std::simd it's not as simple as spelling out all overloads. Consider an implementation that supports up to 256 elements in a basic\_vec . The float overloads would need a minimum of 256 overloads ( hypot(vec<float, N>, vec<float, N>) ). But actually more are needed because of differences in ABI tags (vector mask vs. bit mask; different register widths for different targets). That explosion in function overloads just isn't reasonable to spell out (neither in the standard, nor in an implementation).

Therefore, std::simd uses function templates. The 2-arg hypot function is declared as:

```
template < class V0, class V1> math-common-simd-t <V0, V1> hypot( const V0& x, const V1&
```

```
y);
```

The return type is constrained such that at least one of V0 and V1 is a basic\_vec of floating-point type 5 . In the common cases the math-common-simd-t alias is simply common\_type\_t<V0, V1> . If common\_type has no type member, then the overload is removed from the overload set (SFINAE). The status-quo is that for simd::hypot(vec<float>(), 1) math-common-simd-t <vec<float>, int> is not valid and thus no viable simd::hypot overload exists.

The above proposal makes math-common-simd-t <vec<float>, int> a valid type. In principle, that's correct, because 1 can be represented without loss of value as a float .

The question is what should happen for simd::hypot(vec<float>(), 0x5EAF00D) , which would need to convert 0x5EAF00D to float inside the hypot implementation and thereby change its value. Currently, the make-compatible-simd-t trait converts 0x5EAF00D from int to vec<int, vec<float> ::size()> . If the make-compatible-simd-t<V, T> trait is changed to instead be an alias for V 6 rather than vec<T, V::size()> , then the as-if implementation requires a conversion to vec<float> , and thus implying the broadcast constructor behavior.

## 7 BROADCAST AS IMMEDIATE-ESCALATING EXPRESSION

[Refresher ( https://compiler-explorer.com/z/qvdoxavMK ):](https://compiler-explorer.com/z/qvdoxavMK)

5 or is like a reference\_wrapper

6 Also the classification and comparison functions need to be split off in the wording to provide the correct template argument to make-compatible-simd-t .

```
struct A { consteval A( int ) {} }; constexpr A f( int , auto y) // f gets promoted to an immediate function { return y; } // immediate -escalating expression 'A(y)' A test( int x) { return f(x, 1); } // Error: 'x' is not a constant expression
```

If we remove constexpr from f , the underlying issue becomes apparent: f calls a consteval constructor that uses y as it's argument. And that can't work, because y is not a constant expression. The magic of promotion to immediate function simply makes the compiler try harder to make it compile anyway.

## 7.1

## escalating [simd.math] functions

Any simd::vec broadcast expression that promotes the surrounding function to an immediate function becomes 'interesting' if not surprising or problematic. The [simd.math] functions as discussed above are affected. While simd::hypot(vec<float>(), 1) is fine (because the first argument is a constant expression),

```
auto f(simd::vec< float > x) { return simd::hypot(x, 1); }
```

is not, even though 1 can convert to float without loss of value. That's because the hypot implementation needs to call a consteval function, which then promotes hypot itself to an immediate function, which in turn requires all arguments to hypot to be constant expressions. If immediateescalation were not applied, then the conversion from int to vec<float> inside of hypot would be ill-formed. Either way, simd::hypot(x, 1) with not-constant x cannot be valid.

## 7.2

## move conversions before math calls

We can respecify [simd.math] in such a way that conversions happen before the function is called, mirroring the actual behavior of <cmath> overloads. For 2-arg math functions we would have to change from one function template to three function templates:

```
template < math-floating-point V> constexpr deduced-vec-t <V> hypot( const V&, const V&); template < math-floating-point V> constexpr deduced-vec-t <V> hypot( const V&, const deduced-vec-t <V>&); template < math-floating-point V> constexpr deduced-vec-t <V> hypot( const deduced-vec-t <V>&, const V&);
```

However, for 3-arg math functions we would have to change to seven function templates. I can report that this works for all my test cases. I believe I tested a representative set of argument types and permutations. 7

```
template < math-floating-point V> constexpr deduced-vec-t <V> hypot( const V&, const V&, const V&); template < math-floating-point V> constexpr deduced-vec-t <V> hypot( const V&, const deduced-vec-t <V>&, const deduced-vec-t <V>&); template < math-floating-point V> constexpr deduced-vec-t <V> hypot( const deduced-vec-t <V>&, const V&, const deduced-vec-t <V>&); template < math-floating-point V> constexpr deduced-vec-t <V> hypot( const deduced-vec-t <V>&, const deduced-vec-t <V>&, const V&); template < math-floating-point V> constexpr deduced-vec-t <V> hypot( const V&, const V&, const deduced-vec-t <V>&); template < math-floating-point V> constexpr deduced-vec-t <V> hypot( const V&, const deduced-vec-t <V>&, const V&); template < math-floating-point V> constexpr deduced-vec-t <V> hypot( const deduced-vec-t <V>&, const V&, const V&);
```

## 7.3

alternative via 'expression alias' p2826

P2826, which is awaiting a revision for consideration for C ++ 29, could solve this more elegantly. However, we don't have the feature available yet. Thus we would need to ship C ++ 26 with a [simd.math] specification that is forward-compatible

```
7.4 the importantance of conversions
```

Consider the pow function. It is fairly common to call pow with an integral exponent, e.g.

```
std::pow(x, 3); // x³
```

This is well-formed if x is of floating-point type. It would be unfortunate if the same expression would not work for x of type vec< floating-point-type > .

7 I tested arguments of type reference\_wrapper<vec<float>> , reference\_wrapper<float> , reference\_wrapper<short> , vec<float> , float , short , and immediate arguments with value 1 (consteval broadcast from int ). I tested all permutations where at least one argument is either vec<float> or reference\_wrapper<vec<float>> .

8

## IMPLEMENTATION EXPERIENCE

Both solutions (and a lot more variants that were discarded) have been implemented and tested in my implementation. Several days (if not weeks) of exploration and testing went into this paper. I implemented the consteval overloads for a complete set of vectorizable types with an ability to select between the different behaviors discussed in this paper. A representative set of [simd.math] is implemented.

## 9

## My recommendation is:

- Adopt with the solution presented in Section 4.4,
- without a new exception type (Section 4.5), and
- change [simd.math] to the overload sets presented in Section 7.2 for C ++ 26.

This would roll back a small part of a recent change done by [P3430R3].

Hope for P2826 'Replacement function' - the paper is getting renamed to 'expression alias' - to get into C ++ 29 and provide a simple way to restore <cmath> -like overload resolution and conversions on [simd.math] functions.

Rationale for my preference:

1. The explicit conversion from arithmetic types via broadcast constructor is significantly less important after implicit conversion from constant expressions becomes possible.
2. The new consteval overload cannot be fully constrained in the solution presented in Section 4.3, leading to incorrect answers on traits or in requires expressions.
3. This should be part of C ++ 26 because it helps avoiding bugs in user code.
4. A new exception type is not important enough to add it to C ++ 26 and it can easily be added later.
5. [simd.math] was already complicated; making it more complicated is not warranted. Either we get a language feature to make it work or users have to be explicit about conversions.

If LEWG is uncomfortable with adding the consteval overload now I recommend to:

- remove explicit broadcasts and
- simplify [simd.math] to template<class T> T fun(T, T) for C ++ 26.

<!-- image -->

10.1

In [version.syn] bump the \_\_cpp\_lib\_simd version.

## WORDING FOR CONSTEVAL BROADCAST

feature test macro

## RECOMMENDATION

10.2

In [simd.expos], insert:

```
[simd.expos] template<class From, class To> concept simd-consteval-broadcast-arg = see below ; // exposition only template<class V, class T> using make-compatible-simd-t = see below ; // exposition only template<class V> concept simd-vec-type = // exposition only same_as<V, basic_vec<typename V::value_type, typename V::abi_type>> && is_default_constructible_v<V>;
```

## 10.3

In [simd.expos.defn], insert:

modify [simd.expos.defn]

[simd.expos.defn]

template<class From, class To> concept simd-consteval-broadcast-arg = see below ;

- -?-simd-consteval-broadcast-arg subsumes explicitly-convertible-to .
- -?-From satisfies simd-consteval-broadcast-arg <To> only if
- remove\_cvref\_t<From> is an arithmetic type,
- From satisfies convertible\_to<To> ,
- the conversion from remove\_cvref\_t<From> to To is not value-preserving, and
- either
- common\_type\_t<From, To> is To ,
- To is integral and remove\_cvref\_t<From> is int , or
- To satisfies unsigned\_integral and remove\_cvref\_t<From> is unsigned int .

## modify [simd.overview]

```
[simd.overview] noexcept;
```

## 10.4

In [simd.overview], change:

```
// ([simd.ctor]), basic_vec constructors template<class explicitly-convertible-to <value_type> U> constexpr explicit( see below ) basic_vec(U&& value) noexcept; template< simd-consteval-broadcast-arg <value_type> U> consteval basic_vec(U&& x) template<class U, class UAbi> constexpr explicit( see below ) basic_vec(const basic_vec<U, UAbi>&)
```

modify [simd.expos]

10.5

In [simd.ctore], change:

```
template<class explicitly-convertible-to <value_type> U> constexpr explicit( see below ) basic_vec(U&& value) noexcept;
```

- 1 Let From denote the type remove\_cvref\_t<U> .
- 2 Constraints : value\_type satisfies constructible\_from<U> .
- 3 Effects : Initializes each element to the value of the argument after conversion to value\_type .
- 4 Remarks: The expression inside explicit evaluates to false if and only if U satisfies convertible\_-to<value\_type> , and either
- From is not an arithmetic type and does not satisfy constexpr-wrapper-like ,
- From is an arithmetic type and the conversion from From to value\_type is value-preserving ([simd.general]), or
- From satisfies constexpr-wrapper-like , remove\_const\_t<decltype(From::value)> is an arithmetic type, and From::value is representable by value\_type .

## template< simd-consteval-broadcast-arg <value\_type> U> consteval basic\_vec(U&& x)

- -?-Preconditions : The value of x is equal to the value of x after conversion to value\_type .
- -?-Effects : Initializes each element to the value of the argument after conversion to value\_type .
- -?-Remarks: An expression that violates the precondition in the Preconditions : element is not a core constant expression ([expr.const]).

## 11

11.1

In [simd.expos], change:

## WORDING FOR [SIMD.MATH]

modify [simd.expos]

[simd.expos]

modify [simd.ctor]

[simd.ctor]

```
template<class V, class T> using make-compatible-simd-t = see below ; // exposition only template<class V> concept simd-vec-type = // exposition only same_as<V, basic_vec<typename V::value_type, typename V::abi_type>> && is_default_constructible_v<V>; template<class V> concept simd-mask-type = // exposition only same_as<V, basic_mask< mask-element-size <V>, typename V::abi_type>> && is_default_constructible_v<V>; template<class V> concept simd-floating-point = // exposition only simd-vec-type <V> && floating_point<typename V::value_type>; template<class V> concept simd-integral = // exposition only simd-vec-type <V> && integral<typename V::value_type>; template<class V> using simd-complex-value-type = V::value_type::value_type; // exposition only template<class V> concept simd-complex = // exposition only simd-vec-type <V> && same_as<typename V::value_type, complex< simd-complex-value-type <V>>>; template<class... Ts T> concept math-floating-point = // exposition only ( simd-floating-point < deduced-vec-t <Ts>> || ...); template<class... Ts> requires math-floating-point <Ts...> using math-common-simd-t = see below ; // exposition only template<class BinaryOperation, class T> concept reduction-binary-operation = see below ; // exposition only
```

11.2

modify [simd.expos.defn]

```
In [simd.expos.defn], remove: [simd.expos.defn] template<class T> using deduced-vec-t = see below ; 5 Let x denote an lvalue of type const T . 6 deduced-vec-t <T> is an alias for · decltype(x + x) , if the type of x + x is an enabled specialization of basic_vec ; otherwise · void .
```

```
template<class V, class T> using make-compatible-simd-t = see below ; 7 Let x denote an lvalue of type const T . 8 make-compatible-simd-t <V, T> is an alias for · deduced-vec-t <T> , if that type is not void , otherwise · vec<decltype(x + x), V::size()> . template<class... Ts> requires math-floating-point <Ts...> using math-common-simd-t = see below ; 9 Let T0 denote Ts...[0] . Let T1 denote Ts...[1] . Let TRest denote a pack such that T0, T1, TRest... is equivalent to Ts... . 10 Let math-common-simd-t <Ts...> be an alias for · deduced-vec-t <T0> , if sizeof...(Ts) equals 1 ; otherwise · common_type_t< deduced-vec-t <T0>, deduced-vec-t <T1> , if sizeof...(Ts) equals 2 and mathfloating-point <T0> && math-floating-point <T1> is true ; otherwise · common_type_t< deduced-vec-t <T0>, T1> , if sizeof...(Ts) equals 2 and math-floating-point <T0 is true ; otherwise · common_type_t<T0, deduced-vec-t <T1> , if sizeof...(Ts) equals 2 ; otherwise · common_type_t< math-common-simd-t <T0, T1>, TRest...> , if math-common-simd-t <T0, T1> is valid and denotes a type; otherwise · common_type_t< math-common-simd-t <TRest...>, T0, T1> .
```

11.3

In [simd.syn], change:

```
[simd.syn] template<size_t Bytes, class Abi, class T, class U> constexpr auto select(const basic_mask<Bytes, Abi>& c, const T& a, const U& b) noexcept -> decltype( simd-select-impl (c, a, b)); // ([simd.math]), mathematical functions template< math-floating-point V> constexpr deduced-vec-t <V> acos(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> asin(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> atan(const V& x); template<class V0, class V1 math-floating-point V> constexpr math-common-simd-t <V0, V1> deduced-vec-t <V> atan2(const V0& y, const V1& x); template< math-floating-point V> constexpr deduced-vec-t <V> cos(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> sin(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> tan(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> acosh(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> asinh(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> atanh(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> cosh(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> sinh(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> tanh(const V& x);
```

modify [simd.syn]

```
template< math-floating-point V> constexpr deduced-vec-t <V> exp(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> exp2(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> expm1(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> frexp(const V& value, rebind_t<int, deduced-vec-t <V>>* exp); template< math-floating-point V> constexpr rebind_t<int, deduced-vec-t <V>> ilogb(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> ldexp(const V& x, const rebind_t<int, deduced-vec-t <V>>& exp); template< math-floating-point V> constexpr deduced-vec-t <V> log(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> log10(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> log1p(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> log2(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> logb(const V& x); template<class T, class Abi> constexpr basic_vec<T, Abi> modf(const type_identity_t<basic_vec<T, Abi>>& value, basic_vec<T, Abi>* iptr); template< math-floating-point V> constexpr deduced-vec-t <V> scalbn(const V& x, const rebind_t<int, deduced-vec-t <V>>& n); template< math-floating-point V> constexpr deduced-vec-t <V> scalbln( const V& x, const rebind_t<long int, deduced-vec-t <V>>& n); template< math-floating-point V> constexpr deduced-vec-t <V> cbrt(const V& x); template<signed_integral T, class Abi> constexpr basic_vec<T, Abi> abs(const basic_vec<T, Abi>& j); template< math-floating-point V> constexpr deduced-vec-t <V> abs(const V& j); template< math-floating-point V> constexpr deduced-vec-t <V> fabs(const V& x); template<class V0, class V1 math-floating-point V> constexpr math-common-simd-t <V0, V1> deduced-vec-t <V> hypot(const V0& x, const V1& y); template<class V0, class V1, class V2 math-floating-point V> constexpr math-common-simd-t <V0, V1, V2> deduced-vec-t <V> hypot(const V0& x, const V1& y, const V2& z); template<class V0, class V1 math-floating-point V> constexpr math-common-simd-t <V0, V1> deduced-vec-t <V> pow(const V0& x, const V1& y); template< math-floating-point V> constexpr deduced-vec-t <V> sqrt(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> erf(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> erfc(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> lgamma(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> tgamma(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> ceil(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> floor(const V& x); template< math-floating-point V> deduced-vec-t <V> nearbyint(const V& x); template< math-floating-point V> deduced-vec-t <V> rint(const V& x); template< math-floating-point V> rebind_t<long int, deduced-vec-t <V>> lrint(const V& x); template< math-floating-point V> rebind_t<long long int, V> llrint(const deduced-vec-t <V>& x); template< math-floating-point V> constexpr deduced-vec-t <V> round(const V& x); template< math-floating-point V> constexpr rebind_t<long int, deduced-vec-t <V>> lround(const V& x); template< math-floating-point V> constexpr rebind_t<long long int, deduced-vec-t <V>> llround(const V& x); template< math-floating-point V>
```

```
constexpr deduced-vec-t <V> trunc(const V& x); template<class V0, class V1 math-floating-point V> constexpr math-common-simd-t <V0, V1> deduced-vec-t <V> fmod(const V0& x, const V1& y); template<class V0, class V1 math-floating-point V> constexpr math-common-simd-t <V0, V1> deduced-vec-t <V> remainder(const V0& x, const V1& y); template<class V0, class V1 math-floating-point V> constexpr math-common-simd-t <V0, V1> deduced-vec-t <V> remquo(const V0& x, const V1& y, rebind_t<int, math-common-simd-t <V0, V1> deduced-vec-t <V>>* quo); template<class V0, class V1 math-floating-point V> constexpr math-common-simd-t <V0, V1> deduced-vec-t <V> copysign(const V0& x, const V1& y); template<class V0, class V1 math-floating-point V> constexpr math-common-simd-t <V0, V1> deduced-vec-t <V> nextafter(const V0& x, const V1& y); template<class V0, class V1 math-floating-point V> constexpr math-common-simd-t <V0, V1> deduced-vec-t <V> fdim(const V0& x, const V1& y); template<class V0, class V1 math-floating-point V> constexpr math-common-simd-t <V0, V1> deduced-vec-t <V> fmax(const V0& x, const V1& y); template<class V0, class V1 math-floating-point V> constexpr math-common-simd-t <V0, V1> deduced-vec-t <V> fmin(const V0& x, const V1& y); template<class V0, class V1, class V2 math-floating-point V> constexpr math-common-simd-t <V0, V1, V2> deduced-vec-t <V> fma(const V0& x, const V1& y, const V2& z); template<class V0, class V1, class V2 math-floating-point V> constexpr math-common-simd-t <V0, V1, V2> deduced-vec-t <V> lerp(const V0& a, const V1& b, const V2& t) noexcept; template< math-floating-point V> constexpr rebind_t<int, deduced-vec-t <V>> fpclassify(const V& x); template< math-floating-point V> constexpr typename deduced-vec-t <V>::mask_type isfinite(const V& x); template< math-floating-point V> constexpr typename deduced-vec-t <V>::mask_type isinf(const V& x); template< math-floating-point V> constexpr typename deduced-vec-t <V>::mask_type isnan(const V& x); template< math-floating-point V> constexpr typename deduced-vec-t <V>::mask_type isnormal(const V& x); template< math-floating-point V> constexpr typename deduced-vec-t <V>::mask_type signbit(const V& x); template<class V0, class V1 math-floating-point V> constexpr typename math-common-simd-t <V0, V1> deduced-vec-t <V>::mask_type isgreater(const V0& x, const V1& y); template<class V0, class V1 math-floating-point V> constexpr typename math-common-simd-t <V0, V1> deduced-vec-t <V>::mask_type isgreaterequal(const V0& x, const V1& y); template<class V0, class V1 math-floating-point V> constexpr typename math-common-simd-t <V0, V1> deduced-vec-t <V>::mask_type isless(const V0& x, const V1& y); template<class V0, class V1 math-floating-point V> constexpr typename math-common-simd-t <V0, V1> deduced-vec-t <V>::mask_type islessequal(const V0& x, const V1& y); template<class V0, class V1 math-floating-point V> constexpr typename math-common-simd-t <V0, V1> deduced-vec-t <V>::mask_type islessgreater(const V0& x, const V1& y); template<class V0, class V1 math-floating-point V> constexpr typename math-common-simd-t <V0, V1> deduced-vec-t <V>::mask_type isunordered(const V0& x, const V1& y); template< math-floating-point V>
```

```
deduced-vec-t <V> assoc_laguerre(const rebind_t<unsigned, deduced-vec-t <V>>& n, const rebind_t<unsigned, deduced-vec-t <V>>& m, const V& x); template< math-floating-point V> deduced-vec-t <V> assoc_legendre(const rebind_t<unsigned, deduced-vec-t <V>>& l, const rebind_t<unsigned, deduced-vec-t <V>>& m, const V& x); template<class V0, class V1 math-floating-point V> math-common-simd-t <V0, V1> deduced-vec-t <V> beta(const V0& x, const V1& y); template< math-floating-point V> deduced-vec-t <V> comp_ellint_1(const V& k); template< math-floating-point V> deduced-vec-t <V> comp_ellint_2(const V& k); template<class V0, class V1 math-floating-point V> math-common-simd-t <V0, V1> deduced-vec-t <V> comp_ellint_3(const V0& k, const V1& nu); template<class V0, class V1 math-floating-point V> math-common-simd-t <V0, V1> deduced-vec-t <V> cyl_bessel_i(const V0& nu, const V1& x); template<class V0, class V1 math-floating-point V> math-common-simd-t <V0, V1> deduced-vec-t <V> cyl_bessel_j(const V0& nu, const V1& x); template<class V0, class V1 math-floating-point V> math-common-simd-t <V0, V1> deduced-vec-t <V> cyl_bessel_k(const V0& nu, const V1& x); template<class V0, class V1 math-floating-point V> math-common-simd-t <V0, V1> deduced-vec-t <V> cyl_neumann(const V0& nu, const V1& x); template<class V0, class V1 math-floating-point V> math-common-simd-t <V0, V1> deduced-vec-t <V> ellint_1(const V0& k, const V1& phi); template<class V0, class V1 math-floating-point V> math-common-simd-t <V0, V1> deduced-vec-t <V> ellint_2(const V0& k, const V1& phi); template<class V0, class V1, class V2 math-floating-point V> math-common-simd-t <V0, V1, V2> deduced-vec-t <V> ellint_3(const V0& k, const V1& nu, const V2& phi); template< math-floating-point V> deduced-vec-t <V> expint(const V& x); template< math-floating-point V> deduced-vec-t <V> hermite(const rebind_t<unsigned, deduced-vec-t <V>>& n, const V& x); template< math-floating-point V> deduced-vec-t <V> laguerre(const rebind_t<unsigned, deduced-vec-t <V>>& n, const V& x); template< math-floating-point V> deduced-vec-t <V> legendre(const rebind_t<unsigned, deduced-vec-t <V>>& l, const V& x); template< math-floating-point V> deduced-vec-t <V> riemann_zeta(const V& x); template< math-floating-point V> deduced-vec-t <V> sph_bessel( const rebind_t<unsigned, deduced-vec-t <V>>& n, const V& x); template< math-floating-point V> deduced-vec-t <V> sph_legendre(const rebind_t<unsigned, deduced-vec-t <V>>& l, const rebind_t<unsigned, deduced-vec-t <V>>& m, const V& theta); template< math-floating-point V> deduced-vec-t <V> sph_neumann(const rebind_t<unsigned, deduced-vec-t <V>>& n, const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> fmod(const deduced-vec-t <V>& x, const V& y); template< math-floating-point V> constexpr deduced-vec-t <V> fmod(const V& x, const deduced-vec-t <V>& y); template< math-floating-point V> constexpr deduced-vec-t <V> remainder(const deduced-vec-t <V>& x, const V& y); template< math-floating-point V> constexpr deduced-vec-t <V> remainder(const V& x, const deduced-vec-t <V>& y); template< math-floating-point V> constexpr deduced-vec-t <V> copysign(const deduced-vec-t <V>& x, const V& y);
```

| template< math-floating-point                                       | V>                                                        |
|---------------------------------------------------------------------|-----------------------------------------------------------|
| template< math-floating-point                                       | V>                                                        |
| constexpr deduced-vec-t <V>                                         | nextafter(const deduced-vec-t <V>& x, const V& y);        |
| template< math-floating-point                                       | V>                                                        |
| constexpr deduced-vec-t <V>                                         | nextafter(const V& x, const deduced-vec-t <V>& y);        |
| template< math-floating-point                                       | V>                                                        |
| constexpr deduced-vec-t <V>                                         | fdim(const deduced-vec-t <V>& x, const V& y);             |
| template< math-floating-point                                       | V>                                                        |
| constexpr deduced-vec-t <V>                                         | fdim(const V& x, const deduced-vec-t <V>& y);             |
| template< math-floating-point                                       | V>                                                        |
| constexpr deduced-vec-t <V>                                         | fmax(const deduced-vec-t <V>& x, const V& y);             |
| template< math-floating-point                                       | V>                                                        |
| constexpr deduced-vec-t <V>                                         | fmax(const V& x, const deduced-vec-t <V>& y);             |
| template< math-floating-point                                       | V>                                                        |
| constexpr deduced-vec-t <V>                                         | fmin(const deduced-vec-t <V>& x, const V& y);             |
| template< math-floating-point                                       | V>                                                        |
| constexpr deduced-vec-t <V>                                         | fmin(const V& x, const deduced-vec-t <V>& y);             |
| template< math-floating-point                                       | V>                                                        |
| constexpr deduced-vec-t <V>                                         | isgreater(const deduced-vec-t <V>& x, const V& y);        |
| template< math-floating-point                                       | V>                                                        |
| constexpr deduced-vec-t <V>                                         | isgreater(const V& x, const deduced-vec-t <V>& y);        |
| template< math-floating-point                                       | V>                                                        |
| constexpr deduced-vec-t <V>                                         | islessequal(const deduced-vec-t <V>& x, const V& y);      |
| template< math-floating-point                                       | V>                                                        |
| constexpr deduced-vec-t <V>                                         | islessequal(const V& x, const deduced-vec-t <V>& y);      |
| template< math-floating-point                                       | V>                                                        |
| constexpr deduced-vec-t <V>                                         | islessgreater(const deduced-vec-t <V>& x, const V& y); V> |
| template< math-floating-point constexpr deduced-vec-t <V>           | islessgreater(const V& x, const deduced-vec-t <V>& y);    |
| template< math-floating-point constexpr deduced-vec-t <V>           | V> isunordered(const deduced-vec-t <V>& x, const V& y);   |
|                                                                     | V>                                                        |
| template< math-floating-point constexpr deduced-vec-t <V> template< | isunordered(const V& x, const deduced-vec-t <V>& y); V>   |
| math-floating-point constexpr deduced-vec-t <V>                     | atan2(const deduced-vec-t <V>& x, const V& y);            |
| template< math-floating-point constexpr deduced-vec-t <V>           | V> atan2(const V& x, const deduced-vec-t <V>& y);         |
| template< math-floating-point constexpr deduced-vec-t <V>           | V> hypot(const deduced-vec-t <V>& x, const V& y);         |
| template< math-floating-point constexpr deduced-vec-t <V>           | V>                                                        |
|                                                                     | hypot(const V& x, const deduced-vec-t <V>& y);            |
| template< math-floating-point constexpr deduced-vec-t <V>           | V> pow(const deduced-vec-t <V>& x, const V& y);           |
| template< math-floating-point V> constexpr deduced-vec-t <V>        | pow(const V& x, const deduced-vec-t <V>& y);              |
| math-floating-point                                                 |                                                           |
| template<                                                           | V> deduced-vec-t <V>& x, const V& y);                     |
| deduced-vec-t <V> beta(const template< math-floating-point          | V>                                                        |
| deduced-vec-t <V> beta(const V& x, const deduced-vec-t              | <V>& y);                                                  |
| template< math-floating-point V>                                    |                                                           |
| deduced-vec-t <V> comp_ellint_3(const                               | deduced-vec-t <V>& x, const V& y);                        |
| template< math-floating-point V>                                    | V& x, const deduced-vec-t <V>& y);                        |
| deduced-vec-t <V> comp_ellint_3(const                               |                                                           |

| template< math-floating-point V> deduced-vec-t <V> cyl_bessel_i(const                   | deduced-vec-t <V>& x, const V& y);                               |
|-----------------------------------------------------------------------------------------|------------------------------------------------------------------|
| template< math-floating-point V>                                                        |                                                                  |
| deduced-vec-t <V> cyl_bessel_i(const                                                    | V& x, const deduced-vec-t <V>& y);                               |
| template< math-floating-point V> deduced-vec-t <V>                                      |                                                                  |
| math-floating-point V> deduced-vec-t <V> cyl_bessel_j(const                             | cyl_bessel_j(const deduced-vec-t <V>& x, const V& y);            |
| template<                                                                               | V& x, const deduced-vec-t <V>& y); V>                            |
| template< math-floating-point deduced-vec-t <V> cyl_bessel_k(const                      | deduced-vec-t <V>& x, const V& y);                               |
| template< math-floating-point V> deduced-vec-t <V> cyl_bessel_k(const                   |                                                                  |
|                                                                                         | V& x, const deduced-vec-t <V>& y);                               |
| template< math-floating-point V> deduced-vec-t <V> cyl_neumann(const                    | deduced-vec-t <V>& x, const V& y);                               |
| template< math-floating-point V> deduced-vec-t <V> cyl_neumann(const                    |                                                                  |
|                                                                                         | V& x, const deduced-vec-t <V>& y);                               |
| template< math-floating-point V> deduced-vec-t <V> ellint_1(const                       | deduced-vec-t <V>& x, const V& y);                               |
|                                                                                         | V>                                                               |
| template< math-floating-point                                                           |                                                                  |
| deduced-vec-t <V> ellint_1(const                                                        | V& x, const deduced-vec-t <V>& y);                               |
| template< math-floating-point V>                                                        |                                                                  |
|                                                                                         | deduced-vec-t <V>& x, const V& y);                               |
| deduced-vec-t <V> ellint_2(const template< math-floating-point                          | V>                                                               |
| deduced-vec-t <V> ellint_2(const                                                        | V& x, const deduced-vec-t <V>& y);                               |
| template< math-floating-point                                                           | V>                                                               |
| constexpr deduced-vec-t <V>                                                             | <V>& x, const V& y, rebind_t<int, deduced-vec-t <V>>             |
| remquo(const deduced-vec-t template< math-floating-point                                | quo); V>                                                         |
| constexpr deduced-vec-t <V> remquo(const V& x, const                                    | deduced-vec-t <V>& y, rebind_t<int, deduced-vec-t <V>> quo);     |
| template< math-floating-point constexpr deduced-vec-t <V>                               | V> fma(const deduced-vec-t <V>& x, const V& y, const V& z); V>   |
| template< math-floating-point constexpr deduced-vec-t <V> template< math-floating-point | fma(const V& x, const deduced-vec-t <V>& y, const V& z); V>      |
|                                                                                         | fma(const V& x, const V& y, const deduced-vec-t <V>& z);         |
| constexpr deduced-vec-t <V>                                                             | V>                                                               |
| template< math-floating-point                                                           | fma(const deduced-vec-t <V>& x, const deduced-vec-t <V>&         |
| constexpr deduced-vec-t <V>                                                             | const V& z);                                                     |
| template< math-floating-point                                                           | deduced-vec-t <V>& x, const V& y const deduced-vec-t <V>& z);    |
| template< math-floating-point                                                           | V& x, const deduced-vec-t <V>& y                                 |
| constexpr deduced-vec-t <V>                                                             | const deduced-vec-t <V>& z);                                     |
| template< math-floating-point                                                           | V>                                                               |
| constexpr deduced-vec-t <V> template< math-floating-point                               | hypot(const deduced-vec-t <V>& x, const V& y, const V& z);       |
| constexpr deduced-vec-t <V>                                                             | V> hypot(const V& x, const deduced-vec-t <V>& y, const V& z); V> |
| template< math-floating-point constexpr deduced-vec-t <V>                               | hypot(const V& x, const V& y, const deduced-vec-t <V>&           |
| template< math-floating-point                                                           | z);                                                              |
|                                                                                         | deduced-vec-t <V>& x, const deduced-vec-t <V>&                   |
| constexpr deduced-vec-t <V>                                                             |                                                                  |
| hypot(const                                                                             |                                                                  |
| const V& z);                                                                            |                                                                  |
|                                                                                         | y                                                                |
|                                                                                         | V>                                                               |
|                                                                                         | fma(const V>                                                     |
| constexpr deduced-vec-t <V>                                                             |                                                                  |
|                                                                                         | y                                                                |
|                                                                                         | V>                                                               |
| fma(const                                                                               | fma(const                                                        |

```
template< math-floating-point V> constexpr deduced-vec-t <V> hypot(const deduced-vec-t <V>& x, const V& y const deduced-vec-t <V>& z); template< math-floating-point V> constexpr deduced-vec-t <V> hypot(const V& x, const deduced-vec-t <V>& y const deduced-vec-t <V>& z); template< math-floating-point V> constexpr deduced-vec-t <V> lerp(const deduced-vec-t <V>& x, const V& y, const V& z); template< math-floating-point V> constexpr deduced-vec-t <V> lerp(const V& x, const deduced-vec-t <V>& y, const V& z); template< math-floating-point V> constexpr deduced-vec-t <V> lerp(const V& x, const V& y, const deduced-vec-t <V>& z); template< math-floating-point V> constexpr deduced-vec-t <V> lerp(const deduced-vec-t <V>& x, const deduced-vec-t <V>& y const V& z); template< math-floating-point V> constexpr deduced-vec-t <V> lerp(const deduced-vec-t <V>& x, const V& y const deduced-vec-t <V>& z); template< math-floating-point V> constexpr deduced-vec-t <V> lerp(const V& x, const deduced-vec-t <V>& y const deduced-vec-t <V>& z); template< math-floating-point V> deduced-vec-t <V> ellint_3(const deduced-vec-t <V>& x, const V& y, const V& z); template< math-floating-point V> deduced-vec-t <V> ellint_3(const V& x, const deduced-vec-t <V>& y, const V& z); template< math-floating-point V> deduced-vec-t <V> ellint_3(const V& x, const V& y, const deduced-vec-t <V>& z); template< math-floating-point V> deduced-vec-t <V> ellint_3(const deduced-vec-t <V>& x, const deduced-vec-t <V>& y, const V& z); template< math-floating-point V> deduced-vec-t <V> ellint_3(const deduced-vec-t <V>& x, const V& y, const deduced-vec-t <V>& z); template< math-floating-point V> deduced-vec-t <V> ellint_3(const V& x, const deduced-vec-t <V>& y, const deduced-vec-t <V>& z);
```

// ([simd.bit]), bit manipulation template< simd-vec-type V> constexpr V byteswap(const V& v) noexcept;

```
11.4 modify [simd.math] In [simd.math], change: [simd.math]
```

```
template< math-floating-point V> constexpr rebind_t<int, deduced-vec-t <V>> ilogb(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> ldexp(const V& x, const rebind_t<int, deduced-vec-t <V>>& exp); template< math-floating-point V> constexpr deduced-vec-t <V> scalbn(const V& x, const rebind_t<int, deduced-vec-t <V>>& n); template< math-floating-point V> constexpr deduced-vec-t <V> scalbln(const V& x, const rebind_t<long int, deduced-vec-t <V>>& n); template<signed_integral T, class Abi>
```

```
constexpr basic_vec<T, Abi> abs(const basic_vec<T, Abi>& j); template< math-floating-point V> constexpr deduced-vec-t <V> abs(const V& j); template< math-floating-point V> constexpr deduced-vec-t <V> fabs(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> ceil(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> floor(const V& x); template< math-floating-point V> deduced-vec-t <V> nearbyint(const V& x); template< math-floating-point V> deduced-vec-t <V> rint(const V& x); template< math-floating-point V> rebind_t<long int, deduced-vec-t <V>> lrint(const V& x); template< math-floating-point V> rebind_t<long long int, deduced-vec-t <V>> llrint(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> round(const V& x); template< math-floating-point V> constexpr rebind_t<long int, deduced-vec-t <V>> lround(const V& x); template< math-floating-point V> constexpr rebind_t<long long int, deduced-vec-t <V>> llround(const V& x); template<class V0, class V1 math-floating-point V> constexpr math-common-simd-t <V0, V1> deduced-vec-t <V> fmod(const V0& x, const V1& y); template< math-floating-point V> constexpr deduced-vec-t <V> trunc(const V& x); template<class V0, class V1 math-floating-point V> constexpr math-common-simd-t <V0, V1> deduced-vec-t <V> remainder(const V0& x, const V1& y); template<class V0, class V1 math-floating-point V> constexpr math-common-simd-t <V0, V1> deduced-vec-t <V> copysign(const V0& x, const V1& y); template<class V0, class V1 math-floating-point V> constexpr math-common-simd-t <V0, V1> deduced-vec-t <V> nextafter(const V0& x, const V1& y); template<class V0, class V1 math-floating-point V> constexpr math-common-simd-t <V0, V1> deduced-vec-t <V> fdim(const V0& x, const V1& y); template<class V0, class V1 math-floating-point V> constexpr math-common-simd-t <V0, V1> deduced-vec-t <V> fmax(const V0& x, const V1& y); template<class V0, class V1 math-floating-point V> constexpr math-common-simd-t <V0, V1> deduced-vec-t <V> fmin(const V0& x, const V1& y); template<class V0, class V1, class V2 math-floating-point V> constexpr math-common-simd-t <V0, V1, V2> deduced-vec-t <V> fma(const V0& x, const V1& y, const V2& z); template< math-floating-point V> constexpr rebind_t<int, deduced-vec-t <V>> fpclassify(const V& x); template< math-floating-point V> constexpr typename deduced-vec-t <V>::mask_type isfinite(const V& x); template< math-floating-point V> constexpr typename deduced-vec-t <V>::mask_type isinf(const V& x); template< math-floating-point V> constexpr typename deduced-vec-t <V>::mask_type isnan(const V& x); template< math-floating-point V> constexpr typename deduced-vec-t <V>::mask_type isnormal(const V& x); template< math-floating-point V> constexpr typename deduced-vec-t <V>::mask_type signbit(const V& x); template<class V0, class V1 math-floating-point V>
```

```
y);
```

```
constexpr typename math-common-simd-t <V0, V1> deduced-vec-t <V>::mask_type isgreater(const V0& x, const V1& y); template<class V0, class V1 math-floating-point V> constexpr typename math-common-simd-t <V0, V1> deduced-vec-t <V>::mask_type isgreaterequal(const V0& x, const V1& y); template<class V0, class V1 math-floating-point V> constexpr typename math-common-simd-t <V0, V1> deduced-vec-t <V>::mask_type isless(const V0& x, const V1& y); template<class V0, class V1 math-floating-point V> constexpr typename math-common-simd-t <V0, V1> deduced-vec-t <V>::mask_type islessequal(const V0& x, const V1& y); template<class V0, class V1 math-floating-point V> constexpr typename math-common-simd-t <V0, V1> deduced-vec-t <V>::mask_type islessgreater(const V0& x, const V1& template<class V0, class V1 math-floating-point V> constexpr typename math-common-simd-t <V0, V1> deduced-vec-t <V>::mask_type isunordered(const V0& x, const V1& y); 11 Let Ret denote the return type of the specialization of a function template with the name math-func . Let math-func-vec denote: template<class... Args> Ret math-func-vec (Args... args) { return Ret([&]( simd-size-type i) { return math-func ( make-compatible-simd-t <Ret, Args>static_cast<const deduced-vec-t <V>&>(args)[i]...); }); } 12 Returns: A value ret of type Ret , that is element-wise equal to the result of calling math-func-vec with the arguments of the above functions. If in an invocation of a scalar overload of math-func for index i in math-func-vec a domain, pole, or range error would occur, the value of ret[i] is unspecified. 13 Remarks: It is unspecified whether errno ([errno]) is accessed. template< math-floating-point V> constexpr deduced-vec-t <V> ldexp(const V& x, const rebind_t<int, deduced-vec-t <V>>& exp); template< math-floating-point V> constexpr deduced-vec-t <V> scalbn(const V& x, const rebind_t<int, deduced-vec-t <V>>& n); template< math-floating-point V> constexpr deduced-vec-t <V> scalbln(const V& x, const rebind_t<long int, deduced-vec-t <V>>& n); -?-Let Ret be deduced-vec-t <V> . Let math-func denote the name of the function template. Let math-funcvec denote: Ret math-func-vec (const deduced-vec-t <V>& a, const auto& b) { return Ret([&]( simd-size-type i) { return math-func (a[i], b[i]); }); } -?-Returns: A value ret of type Ret , that is element-wise equal to the result of calling math-func-vec with the arguments of the above functions. If in an invocation of a scalar overload of math-func for index i in math-func-vec a domain, pole, or range error would occur, the value of ret[i] is unspecified. -?-Remarks: It is unspecified whether errno ([errno]) is accessed. template<signed_integral T, class Abi> constexpr basic_vec<T, Abi> abs(const basic_vec<T, Abi>& j); -?-Preconditions : all_of(j >= -numeric_limits<T>::max()) is true . -?-Returns: An object where the 𝑖 th element is initialized to the result of std::abs(j[ 𝑖 ]) for all 𝑖 in the range [ 0 , j.size() ) .
```

```
template< math-floating-point V> constexpr deduced-vec-t <V> acos(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> asin(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> atan(const V& x); template<class V0, class V1 math-floating-point V> constexpr math-common-simd-t <V0, V1> deduced-vec-t <V> atan2(const V0& y, const V1& x); template< math-floating-point V> constexpr deduced-vec-t <V> cos(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> sin(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> tan(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> acosh(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> asinh(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> atanh(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> cosh(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> sinh(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> tanh(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> exp(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> exp2(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> expm1(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> log(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> log10(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> log1p(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> log2(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> logb(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> cbrt(const V& x); template<class V0, class V1 math-floating-point V> constexpr math-common-simd-t <V0, V1> deduced-vec-t <V> hypot(const V0& x, const V1& y); template<class V0, class V1, class V2 math-floating-point V> constexpr math-common-simd-t <V0, V1, V2> deduced-vec-t <V> hypot(const V0& x, const V1& y, const V2& z); template<class V0, class V1 math-floating-point V> constexpr math-common-simd-t <V0, V1> deduced-vec-t <V> pow(const V0& x, const V1& y); template< math-floating-point V> constexpr deduced-vec-t <V> sqrt(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> erf(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> erfc(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> lgamma(const V& x); template< math-floating-point V> constexpr deduced-vec-t <V> tgamma(const V& x); template<class V0, class V1, class V2 math-floating-point V> constexpr math-common-simd-t <V0, V1, V2> deduced-vec-t <V> lerp(const V0& a, const V1& b, const V2& t) noexcept; template< math-floating-point V> deduced-vec-t <V> assoc_laguerre(const rebind_t<unsigned, deduced-vec-t <V>> n, const rebind_t<unsigned, deduced-vec-t <V>> m, const V& x); template< math-floating-point V> deduced-vec-t <V> assoc_legendre(const rebind_t<unsigned, deduced-vec-t <V>> l, const rebind_t<unsigned, deduced-vec-t <V>> m, const V& x); template<class V0, class V1 math-floating-point V> math-common-simd-t <V0, V1> deduced-vec-t <V> beta(const V0& x, const V1& y); template< math-floating-point V> deduced-vec-t <V> comp_ellint_1(const V& k); template< math-floating-point V> deduced-vec-t <V> comp_ellint_2(const V& k); template<class V0, class V1 math-floating-point V> math-common-simd-t <V0, V1> deduced-vec-t <V> comp_ellint_3(const V0& k, const V1& nu); template<class V0, class V1 math-floating-point V> math-common-simd-t <V0, V1> deduced-vec-t <V> cyl_bessel_i(const V0& nu, const V1& x); template<class V0, class V1 math-floating-point V> math-common-simd-t <V0, V1> deduced-vec-t <V> cyl_bessel_j(const V0& nu, const V1& x); template<class V0, class V1 math-floating-point V> math-common-simd-t <V0, V1> deduced-vec-t <V> cyl_bessel_k(const V0& nu, const V1& x);
```

```
template<class V0, class V1 math-floating-point V> math-common-simd-t <V0, V1> deduced-vec-t <V> cyl_neumann(const V0& nu, const V1& x); template<class V0, class V1 math-floating-point V> math-common-simd-t <V0, V1> deduced-vec-t <V> ellint_1(const V0& k, const V1& phi); template<class V0, class V1 math-floating-point V> math-common-simd-t <V0, V1> deduced-vec-t <V> ellint_2(const V0& k, const V1& phi); template<class V0, class V1, class V2 math-floating-point V> math-common-simd-t <V0, V1, V2> deduced-vec-t <V> ellint_3(const V0& k, const V1& nu, const V2& phi); template< math-floating-point V> deduced-vec-t <V> expint(const V& x); template< math-floating-point V> deduced-vec-t <V> hermite(const rebind_t<unsigned, deduced-vec-t <V>> n, const V& x); template< math-floating-point V> deduced-vec-t <V> laguerre(const rebind_t<unsigned, deduced-vec-t <V>> n, const V& x); template< math-floating-point V> deduced-vec-t <V> legendre(const rebind_t<unsigned, deduced-vec-t <V>> l, const V& x); template< math-floating-point V> deduced-vec-t <V> riemann_zeta(const V& x); template< math-floating-point V> deduced-vec-t <V> sph_bessel(const rebind_t<unsigned, deduced-vec-t <V>> n, const V& x); template< math-floating-point V> deduced-vec-t <V> sph_legendre(const rebind_t<unsigned, deduced-vec-t <V>> l, const rebind_t<unsigned, deduced-vec-t <V>> m, const V& theta); template< math-floating-point V> deduced-vec-t <V> sph_neumann(const rebind_t<unsigned, deduced-vec-t <V>> n, const V& x); 14 Let Ret denote the return type of the specialization of a function template with the name math-func . Let math-func-vec denote: template<class... Args> Ret math-func-vec (const Args&... args) { return Ret([&]( simd-size-type i) { return math-func ( make-compatible-simd-t <Ret, Args>static_cast<const deduced-vec-t <V>&>(args)[i]...); }); } 15 Returns: A value ret of type Ret , that is element-wise approximately equal to the result of calling mathfunc-vec with the arguments of the above functions. If in an invocation of a scalar overload of math-func for index i in math-func-vec a domain, pole, or range error would occur, the value of ret[i] is unspecified. 16 Remarks: It is unspecified whether errno ([errno]) is accessed. template< math-floating-point V> deduced-vec-t <V> assoc_laguerre(const rebind_t<unsigned, deduced-vec-t <V>>& n, const rebind_t<unsigned, deduced-vec-t <V>>& m, const V& x); template< math-floating-point V> deduced-vec-t <V> assoc_legendre(const rebind_t<unsigned, deduced-vec-t <V>>& l, const rebind_t<unsigned, deduced-vec-t <V>>& m, const V& x); template< math-floating-point V> deduced-vec-t <V> sph_legendre(const rebind_t<unsigned, deduced-vec-t <V>>& l, const rebind_t<unsigned, deduced-vec-t <V>>& m, const V& theta); -?-Let math-func denote the name of the function template. Let math-func-vec denote: auto math-func-vec (const auto& a, const auto&b, const deduced-vec-t <V>& c) { return deduced-vec-t <V>([&]( simd-size-type i) { return std:: math-func (a[i], b[i], c[i]); }); }
```

```
-?-Returns: An object that is element-wise approximately equal to the result of calling math-func-vec with the arguments of the above functions. template< math-floating-point V> deduced-vec-t <V> hermite(const rebind_t<unsigned, deduced-vec-t <V>>& n, const V& x); template< math-floating-point V> deduced-vec-t <V> laguerre(const rebind_t<unsigned, deduced-vec-t <V>>& n, const V& x); template< math-floating-point V> deduced-vec-t <V> legendre(const rebind_t<unsigned, deduced-vec-t <V>>& l, const V& x); template< math-floating-point V> deduced-vec-t <V> sph_bessel(const rebind_t<unsigned, deduced-vec-t <V>>& n, const V& x); template< math-floating-point V> deduced-vec-t <V> sph_neumann(const rebind_t<unsigned, deduced-vec-t <V>>& n, const V& x); -?-Let math-func denote the name of the function template. Let math-func-vec denote: auto math-func-vec (const auto& a, const deduced-vec-t <V>& b) { return deduced-vec-t <V>([&]( simd-size-type i) { return std:: math-func (a[i], b[i]); }); } -?-Returns: An object that is element-wise approximately equal to the result of calling math-func-vec with the arguments of the above functions. template< math-floating-point V> constexpr deduced-vec-t <V> frexp(const V& value, rebind_t<int, deduced-vec-t <V>>* exp); 17 Let Ret be deduced-vec-t <V> . Let frexp-vec denote: template<class V> pair<Ret, rebind_t<int, Ret>> frexp-vec (const deduced-vec-t <V>& x) { int r1[Ret::size()]; Ret r0([&]( simd-size-type i) { return frexp( make-compatible-simd-t <Ret, V>(x)x[i], &r1[i]); }); return {r0, rebind_t<int, Ret>(r1)}; } Let ret be a value of type pair<Ret, rebind_t<int, Ret>> that is the same value as the result of calling frexp-vec (x) . 18 Effects : Sets *exp to ret.second . 19 Returns: ret.first . template<class V0, class V1 math-floating-point V> constexpr math-common-simd-t <V0, V1> deduced-vec-t <V> remquo(const V0& x, const V1& y, rebind_t<int, math-common-simd-t <V0, V1> deduced-vec-t <V>>* quo); 20 Let Ret be math-common-simd-t <V0, V1>V0 be deduced-vec-t <V> . Let remquo-vec denote: template<class V0, class V1> pair<RetV0, rebind_t<int, RetV0>> remquo-vec (const V0& x, const V1V0& y) { int r1[RetV0::size()]; V0 r0([&]( simd-size-type i) { return remquo( make-compatible-simd-t <Ret, V0>(x)x[i], make-compatible-simd-t <Ret, V1>(y)y[i], &r1[i]); }); return {r0, rebind_t<int, RetV0>(r1)}; }
```

Let ret be a value of type pair<Ret, rebind\_t<int, Ret>pair<V0, rebind\_t<int, V0> that is the same value as the result of calling remquo-vec (x, y) . If in an invocation of a scalar overload of remquo for index i in remquo-vec a domain, pole, or range error would occur, the value of ret[i] is unspecified.

```
21 Effects : Sets *quo to ret.second . 22 Returns: ret.first . 23 Remarks: It is unspecified whether errno ([errno]) is accessed. template<class T, class Abi> constexpr basic_vec<T, Abi> modf(const type_identity_t<basic_vec<T, Abi>>& value, basic_vec<T, Abi>* iptr); 24 Let V be basic_vec<T, Abi> . Let modf-vec denote: pair<V, V> modf-vec (const V& x) { T r1[Ret::size()]; V r0([&]( simd-size-type i) { return modf(V(x)[i], &r1[i]); }); return {r0, V(r1)}; } Let ret be a value of type pair<V, V> that is the same value as the result of calling modf-vec (value) . 25 Effects : Sets *iptr to ret.second . 26 Returns: ret.first .
```

```
template< math-floating-point V> constexpr deduced-vec-t <V> fmod(const deduced-vec-t <V>& x, const V& y); template< math-floating-point V> constexpr deduced-vec-t <V> fmod(const V& x, const deduced-vec-t <V>& y); template< math-floating-point V> constexpr deduced-vec-t <V> remainder(const deduced-vec-t <V>& x, const V& y); template< math-floating-point V> constexpr deduced-vec-t <V> remainder(const V& x, const deduced-vec-t <V>& y); template< math-floating-point V> constexpr deduced-vec-t <V> copysign(const deduced-vec-t <V>& x, const V& y); template< math-floating-point V> constexpr deduced-vec-t <V> copysign(const V& x, const deduced-vec-t <V>& y); template< math-floating-point V> constexpr deduced-vec-t <V> nextafter(const deduced-vec-t <V>& x, const V& y); template< math-floating-point V> constexpr deduced-vec-t <V> nextafter(const V& x, const deduced-vec-t <V>& y); template< math-floating-point V> constexpr deduced-vec-t <V> fdim(const deduced-vec-t <V>& x, const V& y); template< math-floating-point V> constexpr deduced-vec-t <V> fdim(const V& x, const deduced-vec-t <V>& y); template< math-floating-point V> constexpr deduced-vec-t <V> fmax(const deduced-vec-t <V>& x, const V& y); template< math-floating-point V> constexpr deduced-vec-t <V> fmax(const V& x, const deduced-vec-t <V>& y); template< math-floating-point V> constexpr deduced-vec-t <V> fmin(const deduced-vec-t <V>& x, const V& y); template< math-floating-point V> constexpr deduced-vec-t <V> fmin(const V& x, const deduced-vec-t <V>& y);
```

| template< math-floating-point                                            | V>                                                     |
|--------------------------------------------------------------------------|--------------------------------------------------------|
| template< math-floating-point                                            | V>                                                     |
| constexpr deduced-vec-t <V>                                              | isgreater(const V& x, const deduced-vec-t <V>& y);     |
| template< math-floating-point                                            | V>                                                     |
| constexpr deduced-vec-t <V>                                              | islessequal(const deduced-vec-t <V>& x, const V& y);   |
| template< math-floating-point                                            | V>                                                     |
| constexpr deduced-vec-t <V>                                              | islessequal(const V& x, const deduced-vec-t <V>& y);   |
| template< math-floating-point                                            | V>                                                     |
| constexpr deduced-vec-t <V>                                              | islessgreater(const deduced-vec-t <V>& x, const V& y); |
| template< math-floating-point                                            | V>                                                     |
| constexpr deduced-vec-t <V>                                              | islessgreater(const V& x, const deduced-vec-t <V>& y); |
| template< math-floating-point                                            | V>                                                     |
| constexpr deduced-vec-t <V>                                              | isunordered(const deduced-vec-t <V>& x, const V& y);   |
| template< math-floating-point                                            | V>                                                     |
| constexpr deduced-vec-t <V>                                              | isunordered(const V& x, const deduced-vec-t <V>& y);   |
| template< math-floating-point                                            | V>                                                     |
| constexpr deduced-vec-t <V>                                              | atan2(const deduced-vec-t <V>& x, const V& y);         |
| template< math-floating-point                                            | V>                                                     |
| constexpr deduced-vec-t <V>                                              | atan2(const V& x, const deduced-vec-t <V>& y);         |
| template< math-floating-point                                            | V>                                                     |
| constexpr deduced-vec-t <V>                                              | hypot(const deduced-vec-t <V>& x, const V& y);         |
| template< math-floating-point                                            | V>                                                     |
| constexpr deduced-vec-t <V>                                              | hypot(const V& x, const deduced-vec-t <V>& y);         |
| template< math-floating-point V> constexpr deduced-vec-t <V>             | pow(const deduced-vec-t <V>& x, const V& y);           |
| template< math-floating-point                                            | V>                                                     |
| constexpr deduced-vec-t <V>                                              | pow(const V& x, const deduced-vec-t <V>& y);           |
| template< math-floating-point                                            | V>                                                     |
| deduced-vec-t <V> beta(const                                             | deduced-vec-t <V>& x, const V& y);                     |
| template< math-floating-point                                            | V> V& x, const deduced-vec-t <V>& y);                  |
| deduced-vec-t <V> beta(const template< math-floating-point               | V>                                                     |
| deduced-vec-t <V> comp_ellint_3(const                                    | deduced-vec-t <V>& x, const V& y);                     |
| template< math-floating-point V> deduced-vec-t <V>                       | V& x, const deduced-vec-t <V>& y);                     |
| comp_ellint_3(const template< math-floating-point V>                     |                                                        |
| deduced-vec-t <V> cyl_bessel_i(const template< math-floating-point V>    | deduced-vec-t <V>& x, const V& y);                     |
| deduced-vec-t <V>                                                        | V& x, const deduced-vec-t <V>& y);                     |
| cyl_bessel_i(const math-floating-point V>                                |                                                        |
| template< deduced-vec-t <V> cyl_bessel_j(const                           | deduced-vec-t <V>& x, const V& y);                     |
| template< math-floating-point V>                                         | const deduced-vec-t <V>& y);                           |
| deduced-vec-t <V> cyl_bessel_j(const V& x, template< math-floating-point | V>                                                     |
| deduced-vec-t <V>                                                        | deduced-vec-t <V>& x, const V& y);                     |
| cyl_bessel_k(const                                                       | V>                                                     |
| template< math-floating-point deduced-vec-t <V>                          | V& x, const deduced-vec-t <V>& y);                     |
| cyl_bessel_k(const                                                       |                                                        |
| template< math-floating-point V>                                         | <V>& x, const V& y);                                   |
| deduced-vec-t <V> cyl_neumann(const deduced-vec-t                        | V>                                                     |
| template< math-floating-point deduced-vec-t <V> cyl_neumann(const        | V& x, const deduced-vec-t <V>& y);                     |
| template< math-floating-point                                            | V>                                                     |
| deduced-vec-t <V> ellint_1(const                                         | deduced-vec-t <V>& x, const V& y);                     |

| template< math-floating-point V>                                                                                                            |
|---------------------------------------------------------------------------------------------------------------------------------------------|
| template< math-floating-point V>                                                                                                            |
| deduced-vec-t <V> ellint_2(const deduced-vec-t <V>& x, const V& y);                                                                         |
| template< math-floating-point V>                                                                                                            |
| deduced-vec-t <V> ellint_2(const V& x, const deduced-vec-t <V>& y);                                                                         |
| template< math-floating-point V>                                                                                                            |
| constexpr deduced-vec-t <V> remquo(const deduced-vec-t <V>& x, const V& y, rebind_t<int, deduced-vec-t <V>>                                 |
| quo); template< math-floating-point V>                                                                                                      |
| constexpr deduced-vec-t <V> remquo(const V& x, const deduced-vec-t <V>& y, rebind_t<int, deduced-vec-t <V>> quo);                           |
| template< math-floating-point V> constexpr deduced-vec-t <V> fma(const deduced-vec-t <V>& x, const V& y, const V& z);                       |
| template< math-floating-point V>                                                                                                            |
| constexpr deduced-vec-t <V> fma(const V& x, const deduced-vec-t <V>& y, const V& z);                                                        |
| template< math-floating-point V> constexpr deduced-vec-t <V> fma(const V& x, const V& y, const deduced-vec-t <V>& z);                       |
| template< math-floating-point V> constexpr deduced-vec-t <V> fma(const deduced-vec-t <V>& x, const deduced-vec-t <V>& y,                    |
| const V& z); template< math-floating-point V>                                                                                               |
| constexpr deduced-vec-t <V> fma(const deduced-vec-t <V>& x, const V& y, const deduced-vec-t <V>& z); template< math-floating-point V>       |
| constexpr deduced-vec-t <V> fma(const V& x, const deduced-vec-t <V>& y, const deduced-vec-t <V>& z);                                        |
| template< math-floating-point V> constexpr deduced-vec-t <V> hypot(const deduced-vec-t <V>& x, const V& y, const V& z);                     |
| template< math-floating-point V> constexpr deduced-vec-t <V> hypot(const V& x, const deduced-vec-t <V>& y, const V& z);                     |
| template< math-floating-point V> constexpr deduced-vec-t <V> hypot(const V& x, const V& y, const deduced-vec-t <V>&                         |
| template< math-floating-point V>                                                                                                            |
| z); constexpr deduced-vec-t <V> hypot(const deduced-vec-t <V>& x, const deduced-vec-t                                                       |
| <V>& y, const math-floating-point V>                                                                                                        |
| V& z); template< constexpr deduced-vec-t <V> hypot(const deduced-vec-t <V>& x, const V& y, const deduced-vec-t <V>&                         |
| z); template< math-floating-point V> constexpr deduced-vec-t <V> hypot(const V& x, const deduced-vec-t <V>& y, const deduced-vec-t <V>& z); |
| template< math-floating-point V>                                                                                                            |
| constexpr deduced-vec-t <V> lerp(const deduced-vec-t <V>& x, const V& y, const V& z); template< math-floating-point V> z);                  |
| constexpr deduced-vec-t <V> lerp(const V& x, const deduced-vec-t <V>& y, const V& math-floating-point V>                                    |
| template< constexpr deduced-vec-t <V> lerp(const V& x, const V& y, const deduced-vec-t <V>&                                                 |
| z); template< math-floating-point V>                                                                                                        |
| constexpr deduced-vec-t <V> lerp(const deduced-vec-t <V>& x, const deduced-vec-t <V>& y, const V& z); math-floating-point V>                |
| template< constexpr deduced-vec-t <V> lerp(const deduced-vec-t <V>& x, const V& y, const deduced-vec-t <V>& z);                             |
| template< math-floating-point V> constexpr deduced-vec-t <V> lerp(const V& x, const deduced-vec-t <V>& y, const deduced-vec-t <V>& z);      |
| math-floating-point V>                                                                                                                      |
| deduced-vec-t <V> ellint_3(const deduced-vec-t <V>& x, const V& y, const V& z);                                                             |
| template<                                                                                                                                   |
| template< math-floating-point V>                                                                                                            |
| deduced-vec-t <V> ellint_3(const V& x, const deduced-vec-t <V>& y, const V& math-floating-point V>                                          |
| deduced-vec-t <V> ellint_3(const V& x, const V& y, const deduced-vec-t <V>& z);                                                             |
| template<                                                                                                                                   |
| z);                                                                                                                                         |

```
template< math-floating-point V> deduced-vec-t <V> ellint_3(const deduced-vec-t <V>& x, const deduced-vec-t <V>& y, const V& z); template< math-floating-point V> deduced-vec-t <V> ellint_3(const deduced-vec-t <V>& x, const V& y, const deduced-vec-t <V>& z); template< math-floating-point V> deduced-vec-t <V> ellint_3(const V& x, const deduced-vec-t <V>& y, const deduced-vec-t <V>& z);
```

## -?-Let

- math-func denote the name of the function template;
- args... be x and y , or x , y , and z ;
- rest... be all remaining arguments besides x , y , and z .
- -?-Effects : Equivalent to: math-func (static\_cast<const deduced-vec-t <V>&>(args)..., rest...)

## A

## REALLY\_CONVERTIBLE\_TO DEFINITION

```
template < typename To, typename From> consteval bool converting_limits_throws() { try { using L = std::numeric_limits <From >; [[maybe_unused]] To x = L::max(); x = L::min(); x = L::lowest(); } catch (...) { return true; } return false; } template < typename From, typename To> concept really_convertible_to = std::convertible_to <From, To> and not converting_limits_throws <To, From >();
```

## B

## BIBLIOGRAPHY

[P3430R3] Matthias Kretz. simd issues: explicit, unsequenced, identity-element position, and members of disabled simd . ISO/IEC C ++ Standards Committee Paper. 2025. url : https : //wg21.link/p3430r3 .