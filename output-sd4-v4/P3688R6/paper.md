# ASCII character utilities

Document number: P3688R6
Date: 2026-02-21
Audience: LEWG
Project: ISO/IEC 14882 Programming Languages — C++, ISO/IEC JTC1/SC22/WG21
Reply-To: Jan Schultke <janschultke@gmail.com>
Co-Authors: Corentin Jabot <corentin.jabot@gmail.com>
GitHub Issue: wg21.link/P3688/github
Source: github.com/eisenwave/cpp-proposals/blob/master/src/ascii.cow


The utilities in <cctype> or <locale>
are locale-specific,
not constexpr,
and provide no support for Unicode character types.
We propose lightweight, locale-independent alternatives.


## Revision history

1.1

### Changes since R5

1.2

### Changes since R4

1.3

### Changes since R3

1.4

### Changes since R2

1.5

### Changes since R1

1.6

### Changes since R0

2

## Introduction

2.1

### Can't you implement this trivially yourself?

3

## Design

3.1

### List of proposed functions

3.2

### ascii_is_any

3.3

### base parameter in ascii_is_digit

3.4

### ascii_is_bit and ascii_is_octal_digit

3.5

### Case-insensitive comparison functions

3.6

### Why no function objects?

3.7

### What to do for ASCII-incompatible char and wchar_t

3.7.1

#### Conditionally supported char overloads

3.7.2

#### Transcode char to ASCII

3.7.3

#### Treat the input as ASCII, regardless of the literal encoding

3.8

### Naming

3.8.1

#### Why to include ascii in each name

3.8.2

#### ascii_is_* vs. is_ascii_*

3.9

### What if the input is a non-ASCII code unit?

3.10

### Why not accept any integer type?

3.11

### ASCII case-insensitive views and case transformation algorithms

3.12

### Why just ASCII?

3.13

### namespace ascii

4

## Implementation experience

5

## Wording

6

## Acknowledgements

7

## References

## 1. Revision history

### 1.1. Changes since R5

Expand design discussion in §3.5. Case-insensitive comparison functions

Replace a stray use of is_ascii with ascii_is

Remove mention of u32string_view in wording for ascii_is_punctuation

Revise the definition of ASCII-compatible once more

Rebase wording on [N5032]

### 1.2. Changes since R4


Since R4, the paper was seen during two SG16 telecons in Q4 2025.
The changes below incorporate the feedback given during these telecons.


Rename is_ascii_* functions to ascii_is_*
to increase consensus in SG16


Add §3.8. Naming


Change the §3. Design of multiple overloads to a single function template
for all functions



In §3.5. Case-insensitive comparison functions, elaborate why mixing different character types
is not supported


Replace incorrect "C" locale with C locale in §2. Introduction

Fix an asci typo

Remove stray default argument for ascii_is_digit in <ascii> synopsis

Rename is_ascii_printable to ascii_is_printing to match C terminology

Rename is_ascii_graphical to ascii_is_graphic to match C terminology


Rename is_ascii_alpha to ascii_is_alphabetic to avoid
inconsistency with ascii_is_alphanumeric (which is entirely unabbreviated)


Properly define ASCII-compatible in §5. Wording

### 1.3. Changes since R3

Fix a bug in the get_hex_digit_value example in §3.2. ascii_is_any

Split ascii_is_digit (formerly know as is_ascii_digit) into two overloads

Add design discussion in §3.13. namespace ascii

### 1.4. Changes since R2


Expand §3.6. Why no function objects?
based on feedback from BSI (British Standards Institution);
no changes to design are made.


Rebase §5. Wording on N5014.

### 1.5. Changes since R1


In §5. Wording, fix incorrect return type
for ascii_case_insensitive_compare in synopsis.



In §5. Wording, fix superfluous std:: prefix
for strong_ordering in definition of ascii_case_insensitive_compare.


### 1.6. Changes since R0

In §3.3. base parameter in ascii_is_digit, explain why the precondition is not hardened.

In §5. Wording, fix a missing addition to [tab:headers.cpp].

Minor editorial changes.

## 2. Introduction

Testing whether a character falls into a specific subset of ASCII characters
or performing some simple transformations are common tasks in text processing.
For example, applications may need to check if identifiers
are comprised of alphanumeric ASCII characters or underscores;
Unicode properties are not relevant to this task,
and usually, neither are locales.

Unfortunately, these common and simple tasks are only supported
through functions in the <cctype> and <locale> headers, such as:

// <cctype>
int isalnum(int ch);
int isalpha(int ch);
// ...
int toupper(int ch);

// <locale>
template<class charT> bool isalnum(charT c, const locale& loc);

Especially the <cctype> functions are ridden with problems:


There is no support for Unicode character types
(char8_t, char16_t, and char32_t).



These functions are not constexpr,
but performing basic characters tests would be useful at compile time.



There are distinct function names for char and wchar_t
such as std::isalnum and std::iswalnum,
making generic programming more difficult.



If char is signed,
these functions can easily result in undefined behavior
because the input must be representable as unsigned char or be EOF.
If char represents a UTF-8 code unit,
passing any non-ASCII code unit into these functions has undefined behavior.



These functions violate the zero-overhead principle
by also handling an EOF input,
and in many use cases, EOF will never be passed into these functions anyway.
The caller can easily deal with EOF themselves.



The return type of character tests is int,
where a nonzero return value indicates that a test succeeded.
This is very unnatural in C++, where bool is more idiomatic.



Some functions use the currently installed C locale,
which makes their use questionable for high-performance tasks
because each invocation is typically an opaque call that checks the current locale.


We propose lightweight replacement functions which address all these problems.


Many of these problems are resolved by the
std::locale overloads in <locale>,
but their locale dependence makes them unfit for what this proposal aims to achieve.

Testing whether a char8_t (assumed to be a UTF-8 code unit)
is an ASCII digit is obviously a locale-independent task.

### 2.1. Can't you implement this trivially yourself?

It is worth noting that some of the functions can be implemented very easily by the user.
For example, existing code may already use a check like c >= '0' && c <= '9'
to test for ASCII digits,
and our proposed ascii_is_digit does just that.

However, not all of the proposed functions are this simple.
For example, checking whether a char is an
ASCII punctuation character ('#', '?', etc.)
would require lots of separate checks done naively.
In the standard library, it can be efficiently implemented using a 128-bit or 256-bit bitset.

Even if all proposed functions were trivial to implement,
working with ASCII characters is such an overwhelmingly common use case
that it's worth supporting in the standard library.

## 3. Design

All proposed functions are constexpr,
locale-independent,
overloaded (i.e. no separate name for separate input types),
and accept any character type
(char, wchar_t, char8_t, char16_t, and char32_t).
Furthermore, all function names contain ascii
to raise awareness for the fact that these functions do not handle Unicode characters.
A user would expect is_upper(U'Ä') to be true,
but ascii_is_upper(U'Ä') to be false.


The counterpart to std::isalpha is declared follows:

template<character-type T>
constexpr bool ascii_is_alphabetic(T c) noexcept;

character-type is an exposition-only concept
that is modeled by any of the five character types ([basic.fundamental]).
There is nothing unusual noteworthy about this signature;
similar function templates (with an extra const locale& parameter)
can be found in <locale>.


While previous revisions of this paper had several overloads instead of function templates,
there was little to no motivation for this.
<cmath> functions are arguably the only example in the C++ standard
where this design makes sense;
namely because it permits pulling in C header functions into namespace std
via using.

Furthermore, it is obvious that a function template requires less work to implement
for one-liner functions (such as many of the proposed functions),
compared to writing the same function five times.
That is, unless macros are used.

### 3.1. List of proposed functions

Find below a list of proposed functions.
Note that the character set notation [...] is taken from RegEx.

<cctype>
Proposed name
Returns (given ASCII char c)

N/A
ascii_is_any
c <= 0x7F

isdigit
ascii_is_digit
true if c is in [0-9], otherwise false

N/A
ascii_is_bit
c == '0' || c == '1'

N/A
ascii_is_octal_digit
true if c is in [0-7], otherwise false

isxdigit
ascii_is_hex_digit
true if c is in [0-9A-Fa-f], otherwise false

islower
ascii_is_lower
true if c is in [a-z], otherwise false

isupper
ascii_is_upper
true if c is in [A-Z], otherwise false

isalpha
ascii_is_alphabetic
ascii_is_lower(c) || ascii_is_upper(c)

isalnum
ascii_is_alphanumeric
ascii_is_alphabetic(c) || ascii_is_digit(c)

ispunct
ascii_is_punctuation
true if c is in [!"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~], otherwise false

isgraph
ascii_is_graphic
ascii_is_alphanumeric(c) || ascii_is_punctuation(c)

isprint
ascii_is_printing
ascii_is_graphic(c) || c == ' '

isblank
ascii_is_horizontal_whitespace
c == ' ' || c == '\t'

isspace
ascii_is_whitespace
true if c is in [ \f\n\r\t\v], otherwise false

iscntrl
ascii_is_control
(c >= 0 && c <= 0x1F) || c == '\N{DELETE}'

tolower
ascii_to_lower
the respective lower-case character if ascii_is_upper(c) is true, otherwise c

toupper
ascii_to_upper
the respective upper-case character if ascii_is_lower(c) is true, otherwise c

N/A
ascii_case_insensitive_compare
see §3.5. Case-insensitive comparison functions

N/A
ascii_case_insensitive_equals
see §3.5. Case-insensitive comparison functions


The proposed names are mostly unabbreviated
to fit the rest of the standard library style.
Shorter names such as ascii_is_alphanum or ascii_is_alnum
could also be used.


isgraph should perhaps have no new version.
It is of questionable use,
and both the old and new name aren't obvious.
In the default "C" locale,
isgraph is simply isprint without ' '.

Similarly, isblank should perhaps have no new version either.
This proposal simply has a new version for every <cctype> function;
if need be, they are easy to remove.

### 3.2. ascii_is_any

This additional function is mainly useful for checking if a character "is ASCII",
i.e. falls into the basic latin block,
before performing an ASCII-only evaluation.


In the following overload set, the char32_t implementation delegates
to the char8_t implementation to avoid repetition of its logic.
The std::ascii_is_any(c) check is needed because
because an unconditional get_hex_digit_value(char8_t(c))
may result in treating U+0130 LATIN CAPITAL LETTER I WITH DOT ABOVE as U+0030 DIGIT ZERO.

int get_hex_digit_value(char8_t c) {
return c >= u8'0' && c <= u8'9' ? c - u8'0'
: c >= u8'A' && c <= u8'F' ? c - u8'A' + 10
: c >= u8'a' && c <= u8'f' ? c - u8'a' + 10
: -1;
}

int get_hex_digit_value(char32_t c) {
return std::ascii_is_any(c) ? get_hex_digit_value(char8_t(c)) : -1;
}

### 3.3. base parameter in ascii_is_digit

Similar to std::to_chars,
std::ascii_is_digit can also take a base parameter.
There are two overloads:

template<character-type T>
constexpr bool ascii_is_digit(T c, int base) /* not noexcept */;
template<character-type T>
constexpr bool ascii_is_digit(T c) noexcept;

If base ≤ 10,
the range of valid ASCII digit character is simply limited.
For greater base, a subset of alphabetic characters is also accepted,
starting with 'a' or 'A'.
Such a function is useful when parsing numbers with a base of choice,
which is what std::to_chars does, for example.

Similar to std::from_chars and std::to_chars,
the given base has to be between 2 and 36 (inclusive).
This is a non-hardened precondition because all functions in <ascii>
are low-level, high-performance, and spiritually numeric.
Hardened preconditions are not used within that context.


The benefit of having two separate overloads is mainly
that the one without a base parameter can be made noexcept.

### 3.4. ascii_is_bit and ascii_is_octal_digit

C++ and various other programming languages support binary and octal literals,
so it seems like an arbitrary choice to only have dedicated overloads for (hexa)decimal digits.
ascii_is_bit may be especially useful,
such as when dealing with bit-strings like one of the std::bitset constructors.

In conclusion, we may as well have functions for bases 2, 8, 10, and 16;
they're not doing much harm, they're trivial to implement,
and some users may find them useful.


None of the authors feel strongly about this,
so if LEWG insists,
we could remove ascii_is_bit and ascii_is_octal_digit,
and even remove ascii_is_hex_digit,
leaving only the multi-base ascii_is_digit.

### 3.5. Case-insensitive comparison functions

As shown in the table above,
we also propose the case-insensitive comparison functions.

template<character-type T>
constexpr strong_ordering ascii_case_insensitive_compare(
T a,
T b
) {
return ascii_to_upper(a) <=> ascii_to_upper(b);
}

template<character-type T>
constexpr strong_ordering ascii_case_insensitive_equals(
T a,
T b
) {
return ascii_to_upper(a) == ascii_to_upper(b);
}

These functions deliberately have only one template type parameter.
Comparing code units of different encodings is typically meaningless,
and ascii_to_upper only has an effect if ascii_is_lower returns true;
therefore, a comparison such as
ascii_case_insensitive_equals(c, U'\N{NO-BREAK SPACE}')
could yield false positives for some UTF-8 code unit c with value 0xA0.

Also note that the choice of ascii_to_upper over ascii_to_lower matters:

// OK, passes because U'A' < U'^' is true, whereas U'a' < U'^' is false.
static_assert(ascii_case_insensitive_compare(U'a', U'^') < 0);

The choice of ascii_to_upper is arbitrary, and this is fine.
However, it may be worth pointing out that the ordering here is
radically different from the case-insensitive string ordering
using the DUCET (Default Unicode Collation Element Table),
which reorders the Basic Latin block almost entirely.
The use of ascii_to_upper deliberately produces different results than Unicode
comparisons because those would essentially involve a 128-character lookup table,
whereas ascii_case_insensitive_compare is easily SIMD-parallelizable
and requires no memory lookup.
Most users probably don't care whether U'a'
compares case-insensitively-less than U'^',
as long as they get a strict weak ordering and the implementation is fast and correct.
The (possibly non-existent) minority who cares
should either use the ICU or emulate the DUCET behavior using a lookup table.


During the 2026-01-14 SG16 meeting,
concerns were raised about whether the proposal should include these functions;
the following poll was taken:

Poll 1: P3688R5: Remove the case-insensitive character comparison functions.

Attendees: 9


SFFNASA

10341

Consensus against.

### 3.6. Why no function objects?

For case-insensitive comparisons and for character tests in general,
function objects may be convenient because they can be more easily used in algorithms:

std::string_view str = "abc123";
// This does not work if ascii_is_digit is an overloaded function or function template.
auto it = std::ranges::find(str, ascii_is_digit);

However, there is no reason why ascii_is_digit needs to be a function object.
It is not a customization point, but a simple utility,
and the established practice is to make these utilities free functions.

There are countless functions in the standard library that the user
may desire to put directly into an algorithm.
For example, a user may want to put std::sqrt or std::abs
in ranges::transform,
or use them as a projection in an algorithm.
Cherry-picking the functions in <ascii> to be function objects
is far from solving the general problem;
in fact, encouraging direct use of <ascii> function objects in algorithms
could mislead the user into attempting the same with various non-addressable functions,
such as std::abs, making the program IFNDR.

This problem should be solved generally, such as:


Overhauling the standard library to convert most functions into function objects.



Standardizing a LIFT macro that wraps an overload set in a lambda,
or some other means of wrapping,
possibly as a core language feature
similar to the one proposed in [P3312R1] "Overload Set Types".


Any solution to the general problem far exceeds the scope of this paper.
Perhaps one will emerge via C++26 reflection with further C++29 additions.

### 3.7. What to do for ASCII-incompatible char and wchar_t

Not every ordinary and wide character encoding is ASCII-compatible,
such as EBCDIC, Shift JIS, and (defunct) ISO-646,
i.e. code units ≤ 0x7f do not represent the same characters as ASCII.

This begs the question:
what should ascii_is_digit('0') do on an EBCDIC platform,
where this call is ascii_is_digit(char(0xf0)) ?
We have three options, discussed below.


ascii_is_digit(u8'0') is equivalent to ascii_is_digit(char8_t(0x30))
on any platform.
In general, the behavior for Unicode character types is obvious,
unlike that for char and wchar_t.

#### 3.7.1. Conditionally supported char overloads

We could mandate that the ordinary literal encoding is an ASCII superset
for the char overload to exist.
This would force a cast (to char8_t) to use the functions on EBCDIC platforms.
It is not clear how implementations would treat Shift JIS;
GCC assumes '\\' == '¥' to be true
(when linked against some iconv implementations),
so this option may not be enough to alleviate
the awkwardness of ascii_is_punctuation('¥').

Also, this option is not very useful.
It is reasonable to have UTF-8 data stored in a char[] on EBCDIC platforms,
and having to perform casts to char8_t would be awkward.

#### 3.7.2. Transcode char to ASCII

We could transcode from the ordinary literal encoding
to ASCII and produce an answer for the result of that transcoding.
This would be a greater burden for implementations,
especially on EBCDIC platforms.
The benefit is that ascii_is_digit('0') is always true,
although ascii_is_digit(char(0x30)) may not be.
However, ascii_is_digit(char8_t(0x30)) is always true.

It probably does not solve the ascii_is_punctuation('¥') case,
as implementers may keep transcoding '¥' and '\\' in the same way.
It would also give incorrect answers for stateful encodings.
There are EBCDIC control characters that do not have an ASCII equivalent,
so if we were to do conversions, we would have to decide what,
for example, ascii_is_control('\u008B') should produce.


This option was originally preferred by one of the authors,
but proved to be hugely unpopular in discussion of the proposal.

#### 3.7.3. Treat the input as ASCII, regardless of the literal encoding

This is our proposed behavior.

The most simple option is to ignore literal encoding entirely,
and assume that char inputs are ASCII-encoded.
The greatest downside is that depending on encoding,
ascii_is_digit('0') may be false,
which may be surprising to the user.
However, the main purpose of these functions is to be called with characters taken from ASCII text,
so what results they yield when passing literals is not so important.

There are use cases for this behavior on EBCDIC platforms.
A lot of protocols (HTTP, POP) and file formats (JSON, XML) are ASCII/UTF-8-based
and need to be supported on EBCDIC systems,
making these functions universally useful,
especially as <cctype> functions cannot easily be used to deal with ASCII on these platforms.

Ultimately, do we want functions to deal with ASCII or the literal encoding?
If we want them to be a general way to query the ordinary literal encoding,
ascii_is_* is a terrible name,
and finding a more general name would prove difficult.


If we choose this option,
we can still provide the same transcoding functionality as the previous option
by offering a (literal-encoded) char → (code point) char32_t function,
although that may be outside the scope of this proposal.

### 3.8. Naming

#### 3.8.1. Why to include ascii in each name

All proposed functions should have ascii somewhere in their name.
This emphasizes that rather than using the literal encoding or execution encoding,
these functions operate only on ASCII characters
(or Basic Latin code points, depending on how you think of it).

ascii also makes it obvious that no Unicode property tests are performed.
Names such as std::is_digit are worth reserving for more general tests.

#### 3.8.2. ascii_is_* vs. is_ascii_*

R4 and previous revisions of this paper used the naming scheme is_ascii_*
rather than is_ascii_* for character rests.
This was chosen because the name is more natural for English readers.
After discussion of R4 in SG16, the scheme was changed to use the ascii_ prefix
in all cases because:


is_ascii_* could be understood as asking:
Is this thing I have, whatever it is, considered an ASCII digit?
This is a problematic question when considering the
is_ascii_digit('0') problem described in §3.7. What to do for ASCII-incompatible char and wchar_t.
The ascii_is_* scheme more clearly signals that all functions
assume a domain of ASCII, as an encoding assumption.



The ascii_* scheme can be applied consistently to all functions,
including ascii_case_insensitive_compare.


### 3.9. What if the input is a non-ASCII code unit?

Text input is rarely guaranteed to be pure ASCII,
i.e. some code units may be > 0x7f.
However, we're still interested in ASCII characters within that input.
For example, we may

parse pure ASCII numbers like 123 in a UTF-8 JSON (or other config) file,

trim ASCII whitespace in HTTP headers, which are encoded with ISO-8859-1,


parse ASCII-alphanumeric variable names in Lua scripts,
where non-ASCII characters can appear (comments, string),


...

It is possible (and expected) that the user calls say,
ascii_is_digit(U'ö'), at least indirectly.
For the sake of convenience, all proposed functions should handle such inputs by

returning false in the case of all testing functions, and

applying an identity transformation in transformation/case-insensitive comparison functions.


With these semantics, the user can safely write:

std::u8string_view str = u8"öab 123";
// it is an iterator to '1' because 'ö' is skipped
auto it = std::ranges::find(str, [](char8_t c) { return std::ascii_is_digit(c); });

If ascii_is_digit doesn't simply return false on non-ASCII inputs,
the proposal is useless for the common use case where some non-ASCII characters exist in the input.

The proposed behavior also works excellently with any ASCII-compatible encoding, such as UTF-8.
Surrogate code units in UTF-8 are all greater than 0x7F,
so if we implement say, ascii_is_digit naively by checking
c >= '0' && c <= '9', it "just works".

### 3.10. Why not accept any integer type?

Some people argue that a test like ascii_is_digit('0')
is a purely numerical test using the ASCII table,
and so passing ascii_is_digit(0x30) should also be valid.

However, this permissive interface would invite bugs.
For example, c - '0' is the difference between ASCII characters, not an ASCII character,
so passing it into ascii_is_digit would be nonsensical.
Static type systems exist for a reason:
to protect us from stupid mistakes.
While char, char32_t etc. are not required to be ASCII-encoded,
they are at least characters,
so passing them into our functions is likely something the user intended to do,
which we cannot say with confidence about int, unsigned int, etc.

Additionally, if we allowed passing signed integers,
we may want to make the behavior erroneous or undefined for negative inputs
because ascii_is_digit(-1'000'000) is most likely a developer mistake.
Our interface is very simple:
it has a wide contract and almost all functions are noexcept.
Let's keep it that way!

Lastly, even proponents of passing integer types would not want
ascii_is_digit(true) to be valid.

### 3.11. ASCII case-insensitive views and case transformation algorithms

Ignoring or transforming ASCII case in algorithms is a fairly common problem.
Therefore, it may be useful to provide views such as std::views::ascii_lower,
algorithms like std::ranges::equal_ascii_case_insensitive, etc.


HTML tag names are case-insensitive and comprised of ASCII characters,
like <div>, <DIV> etc.
To identify a <div> element, it would be nice if the user could write:

std::ranges::equal(tag_name | std::views::ascii_lower, "div");
// or
std::ranges::ascii_case_insensitive_equal(tag_name, "div");
// or
tag_name.ascii_case_insensitive_equals("div");

While case transformations can be implemented naively using std::transform,
dedicated functions would allow an efficient vectorized implementation for contiguous ranges,
which can be many times faster ([AvoidCharByChar], [AVX-512CaseConv])
Similarly, a case-insensitive comparison function can be vectorized.
In fact, POSIX's strncasecmp has been heavily optimized in glibc ([AVX2strncasecmp]),
and providing range-based interfaces would allow delegating to these heavily optimized functions.

We intend to propose such utilities in a future paper or revision of this paper.
Currently, this proposal is focused exclusively on operations involving character types.

### 3.12. Why just ASCII?

It may be tempting to generalize the proposed utilities beyond ASCII, e.g. to UTF-8.
However, this is not proposed for multiple reasons:


You cannot pass char8_t into a UTF-8 is_upper function
and expect meaningful results.
In general, operations on variable-length encodings require sequences of code units.
The interface we propose only makes sense for ASCII.



Unicode utilities are tremendously more complex than ASCII utilities.
Some Unicode case conversions even require multi-code-point changes.


### 3.13. namespace ascii

Instead of "pseudo-namespacing" the proposed functions by including ascii in the name,
it would also be possible to create a new namespace ascii
which houses all functions.
This would have the notable benefit of letting the user opt into shorter functions like:

using std::ascii::is_lower;
is_lower('a');

However, we chose not to do this because it is unusual to create distinct namespace
for these small sets of utilities.
Furthermore, it may be desirable to have SIMD overloads of these utilities in the future.
This begs the question:
would it be std::simd::ascii::is_lower or std::ascii::simd::is_lower?
Would it be std::views::ascii::lower or std::ascii::views::lower?
The simpler option is to avoid namespaces.

## 4. Implementation experience

A naive implementation of all proposed functions can be found at [CompilerExplorer],
although these are implemented as function templates,
not as overload sets (as proposed).

A more advanced implementation of some functions can be found in [µlight].
Character tests can be optimized using 128-bit or 256-bit bitsets.

## 5. Wording

The wording changes are relative to [N5032].

In [tab:headers.cpp], add a new element to C++ library headers table:

<ascii>

In subclause [version.syn],
update the synopsis as follows:

[…]
#define __cpp_lib_as_const 201510L // freestanding, also in <utility>
#define __cpp_lib_ascii 20XXXXL // freestanding, also in <ascii>
#define __cpp_lib_associative_heterogeneous_erasure 202110L // also in […]
[…]

In Clause [text],
append a new subclause:

## ASCII utilities [ascii]

¶
Subclause [ascii] describes components for dealing with characters
that are encoded using ASCII
or encodings that are ASCII-compatible,
which are encodings where


any code unit c
for which ascii_is_any(c) is true
is valid and is the complete encoding of exactly one Unicode code point
with the same numeric value as c, and



no other sequence of code units
encodes a Unicode code point in the Basic Latin block.


[Example: ASCII, UTF-8, UTF-16, and UTF-32 are ASCII-compatible.
EBCDIC and Shift JIS are not ASCII-compatible. — end example]

¶
Recommended practice:
Implementations should emit a warning when a function in this subclause is invoked
using a value produced by a string-literal
or character-literal whose encoding is not ASCII-compatible.

[Example:
ascii_is_digit('0') is false if the
ordinary literal encoding ([lex.charset]) is EBCDIC
or some other ASCII-incompatible encoding,
which can be surprising to the user.
However, ascii_is_digit(char{0x30})
is true regardless of the ordinary literal encoding.
— end example]

### Header <ascii> synopsis [ascii.syn]

// all freestanding
namespace std {
// exposition-only helpers
template<class T>
concept character-type = same_as<T, char> || same_as<T, wchar_t> // exposition only
|| same_as<T, char8_t> || same_as<T, char16_t> || same_as<T, char32_t>;

// [ascii.chars.test], ASCII character testing
template<character-type T> constexpr bool ascii_is_any(T c) noexcept;

template<character-type T> constexpr bool ascii_is_digit(T c, int base);
template<character-type T> constexpr bool ascii_is_digit(T c) noexcept;
template<character-type T> constexpr bool ascii_is_bit(T c) noexcept;
template<character-type T> constexpr bool ascii_is_octal_digit(T c) noexcept;
template<character-type T> constexpr bool ascii_is_hex_digit(T c) noexcept;

template<character-type T> constexpr bool ascii_is_lower(T c) noexcept;
template<character-type T> constexpr bool ascii_is_upper(T c) noexcept;
template<character-type T> constexpr bool ascii_is_alphabetic(T c) noexcept;
template<character-type T> constexpr bool ascii_is_alphanumeric(T c) noexcept;

template<character-type T> constexpr bool ascii_is_punctuation(T c) noexcept;
template<character-type T> constexpr bool ascii_is_graphic(T c) noexcept;
template<character-type T> constexpr bool ascii_is_printing(T c) noexcept;

template<character-type T> constexpr bool ascii_is_horizontal_whitespace(T c) noexcept;
template<character-type T> constexpr bool ascii_is_whitespace(T c) noexcept;

template<character-type T> constexpr bool ascii_is_control(T c) noexcept;

// [ascii.chars.transform], ASCII character transformation
template<character-type T> constexpr T ascii_to_lower(T c) noexcept;
template<character-type T> constexpr T ascii_to_upper(T c) noexcept;

// [ascii.chars.case.compare], ASCII case-insensitive character comparison
template<character-type T>
constexpr strong_ordering ascii_case_insensitive_compare(T a, T b) noexcept;
template<character-type T>
constexpr bool ascii_case_insensitive_equals(T a, T b) noexcept;
}

### ASCII character testing [ascii.chars.test]

template<character-type T> constexpr bool ascii_is_any(T c) noexcept;

Returns:
static_cast<char32_t>(c) <= 0x7F.

template<character-type T> constexpr bool ascii_is_digit(T c, int base);

Preconditions:
base has a value between 2 and 36 (inclusive).

Returns:
(static_cast<char32_t>(c) >= U'0' && static_cast<char32_t>(c) < U'0' + min(base, 10))
|| (static_cast<char32_t>(c) >= U'a' && static_cast<char32_t>(c) < U'a' + max(base - 10, 0))
|| (static_cast<char32_t>(c) >= U'A' && static_cast<char32_t>(c) < U'A' + max(base - 10, 0))

Remarks:
A function call expression that violates the precondition
in the Preconditions: element
is not a core constant expression.

template<character-type T> constexpr bool ascii_is_digit(T c) noexcept;

Returns:
ascii_is_digit(c, 10).

template<character-type T> constexpr bool ascii_is_bit(T c) noexcept;

Returns:
ascii_is_digit(c, 2).

template<character-type T> constexpr bool ascii_is_octal_digit(T c) noexcept;

Returns:
ascii_is_digit(c, 8).

template<character-type T> constexpr bool ascii_is_hex_digit(T c) noexcept;

Returns:
ascii_is_digit(c, 16).

template<character-type T> constexpr bool ascii_is_lower(T c) noexcept;

Returns:
static_cast<char32_t>(c) >= U'a' && static_cast<char32_t>(c) <= U'z'.

template<character-type T> constexpr bool ascii_is_upper(T c) noexcept;

Returns:
static_cast<char32_t>(c) >= U'A' && static_cast<char32_t>(c) <= U'Z'.

template<character-type T> constexpr bool ascii_is_alphabetic(T c) noexcept;

Returns:
ascii_is_lower(c) || ascii_is_upper(c).

template<character-type T> constexpr bool ascii_is_alphanumeric(T c) noexcept;

Returns:
ascii_is_alphabetic(c) || ascii_is_digit(c).

template<character-type T> constexpr bool ascii_is_punctuation(T c) noexcept;

Returns:
true if static_cast<char32_t>(c) equals one of
U'!',
U'"',
U'#',
U'$',
U'%',
U'&',
U'\'',
U'(',
U')',
U'*',
U'+',
U',',
U'-',
U'.',
U'/',
U':',
U';',
U'<',
U'=',
U'>',
U'?',
U'@',
U'[',
U'\\',
U']',
U'^',
U'_',
U'`',
U'{',
U'|',
U'}', or
U'~',
otherwise false.

template<character-type T> constexpr bool ascii_is_graphic(T c) noexcept;

Returns:
ascii_is_alphanumeric(c) || ascii_is_punctuation(c).

template<character-type T> constexpr bool ascii_is_printing(T c) noexcept;

Returns:
ascii_is_graphic(c) || static_cast<char32_t>(c) == U' '.

template<character-type T> constexpr bool ascii_is_horizontal_whitespace(T c) noexcept;

Returns:
static_cast<char32_t>(c) == U' ' || static_cast<char32_t>(c) == U'\t'.

template<character-type T> constexpr bool ascii_is_whitespace(T c) noexcept;

Returns:
u32string_view(U" \f\n\r\t\v").contains(static_cast<char32_t>(c)).

template<character-type T> constexpr bool ascii_is_control(T c) noexcept;

Returns:
static_cast<char32_t>(c) <= 0x1F || static_cast<char32_t>(c) == U'\N{DELETE}'.

### ASCII character transformation [ascii.chars.transform]

template<character-type T> constexpr T ascii_to_lower(T c) noexcept;

Returns:
ascii_is_upper(c) ? static_cast<T>(static_cast<char32_t>(c) - U'A' + U'a') : c.

template<character-type T> constexpr T ascii_to_upper(T c) noexcept;

Returns:
ascii_is_lower(c) ? static_cast<T>(static_cast<char32_t>(c) - U'a' + U'A') : c.

### ASCII case-insensitive character comparison [ascii.chars.case.compare]

template<character-type T>
constexpr strong_ordering ascii_case_insensitive_compare(T a, T b) noexcept;

Returns:
ascii_to_upper(a) <=> ascii_to_upper(b).

template<character-type T>
constexpr bool ascii_case_insensitive_equals(T a, T b) noexcept;

Returns:
ascii_to_upper(a) == ascii_to_upper(b).


The wording for ascii_is_punctuation was originally more compact by utilizing
std::u32string_­view(U"...").contains(c),
but this approach was scrapped because it suggests a dependence between
<ascii> and <string_view> which does not exist.

The list of character literals is sorted by their integer values, ascending.


Some uses of static_cast are unnecessary to describe semantics.
For example, static_cast<char32_t>(c) == U' '
is equivalent to c == U' '.

However, these uses of static_cast may improve readability and avoid
the use of behavior which is proposed to be deprecated in [P3695R0].

## 6. Acknowledgements

Thanks to Joe Gottman for spotting a mistake in get_hex_digit_value.
Thanks to Hubert Tong for suggesting improvements to discussion and wording.

## 7. References

[N5032]
Thomas Köppe.
Working Draft, Programming Languages — C++
2025-12-15
https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2025/n5032.pdf

[P3312R1]
Bengt Gustafsson.
Overload Set Types
2025-04-16
https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2025/p3312r1.pdf

[P3695R0]
Jan Schultke.
Deprecate implicit conversions between char8_t, char16_t, and char32_t
2025-05-18
https://isocpp.org/files/papers/P3695R0.html

[CompilerExplorer]
Jan Schultke, Corentin Jabot.
Partial implementation of character utilities
https://godbolt.org/z/5nvWzdf8G

[µlight]
Jan Schultke.
ascii_chars.hpp utilities in µlight
https://github.com/Eisenwave/ulight/blob/main/include/ulight/impl/ascii_chars.hpp

[AVX2strncasecmp]
Noah Goldstein.
glibc [PATCH v1 21/23] x86: Add AVX2 optimized str{n}casecmp
2022-03-23
https://sourceware.org/pipermail/libc-alpha/2022-March/137272.html

[AvoidCharByChar]
Daniel Lemire.
Avoid character-by-character processing when performance matters
2020-07-21
https://lemire.me/blog/2020/07/21/avoid-character-by-character-processing-when-performance-matters/

[AVX-512CaseConv]
Daniel Lemire.
Converting ASCII strings to lower case at crazy speeds with AVX-512
2024-08-03
https://lemire.me/blog/2024/08/03/converting-ascii-strings-to-lower-case-at-crazy-speeds-with-avx-512/