

## 1 Introduction

The optimizer has much of the same functionality as a static analysis tools. It could perform the same verifications as a separate tool, making correctness checks more accessible to the programmer, and at the same time provide better control over the optimizations. What is lacking is a simple way for a programmer to interact with it.

This paper introduces a new type of asserts. We already have assert() that verify a statement at runtime. It is costly performance wise and introduces possible terminations into the application.

Then we have static\_assert() that check things in at compile time. No performance overhead and no terminations. But it can only check a limited set of statements, strictly defined by the language.

A related feature [[assume()]] is sometimes used when we think we know the truth and want to make sure the optimizer know, hoping it will improve performance. With the caveat of introducing UB if our guess is wrong.

But there is one missing to this set. An assert, at compile time, proved by the optimizer based on all its knowledge. What we get is an assert that can prove a lot more than a static\_assert() , without the performance overhead and termination risk of assert() and with the same effect on an [[assume()]] without the risk of UB.

## constant\_assert

Document #:

P4019R0

Date:

2026-01-14

Project:

Programming Language C++

Audience:

EWG, EWGI

Reply-to:

Jonas Persson

<jonas.persson@iar.com>

## 2 Proposal

## 2.1 constant\_assert(expr)

if expr is not dead code, not constant folded and do not evaluate to true at code generation phase, the program is ill formed.

## 3 Use cases

## 3.1 Inspect optimizer abilities

This is a nice but rather niche use. Having a way to check that the optimizer work as expected without resorting to reading assembler output can save many hours when fine tuning code.

## 3.2 Verified [[assume()]]

Macros that assert in debug and assume in release is not uncommon, and also not safe. Sometimes such check can be replaced by a constant\_assert() , giving the same optimization hint but without relying on anecdotal proof and risk of UB.

## 3.3 Contract semantics

As a contract semantic, this will unlock some really powerful uses for both safety and performance as contracts can be forced to resolve at compile time. Use of this in contracts brings a whole lot of intricate details so it is postponed to a separate paper after this basic feature has settled.

## 4 Unspecified behaviour

This feature is by design based on unspecified behaviour.

The part where the compiler figure out if the expression can be resolved at compiler time is not possible to specify. It will differ between compilers, compiler options and context.

But once it has been decided that it is known at compile time, the truth of the expression will be well defined and evaluate the same everywhere.

This is how we want it. The idea here is to tap into the ingeniousness of the unconstrained optimizer and use it as a tool for correctness.

constant\_assert will most likely fail or succeed differently between compilers, but hopefully each compiler brand will improve over time, so once the constant\_assert has passed with a compiler, it will continue to pass with newer versions.

A good thing is that it will make differences in compilers visible and perhaps spur some competition.

## 5 Non optimizing modes

Compilers have different optimization levels and many constant\_assert s will need maximum optimizations.

This mean that constant\_assert will have to be wrapped and replaced with something else in unoptimized builds.

But once in place this will hopefully drive optimizers to work differently. constant\_assert should be seen as a primary optimization driver and the optimizer should start with proving these checks on all levels of optimizations. And once this is done it can use what has been proven to subsequent optimization steps, or throw it away if the no optimization is desired.

## 6 Implementation

constant\_assert has not been added in any implementation yet, but such a check is already implementable in user code.

Gcc implements a \_\_builtin\_constant\_p(expr) [constant\_p] that tells whether the expression has been constant folded by the optimizer or not.

```
[[gnu::always_inline]] constexpr void constant_assert(bool cond) { if (not __builtin_constant_p(cond)) [] [[gnu::error("constant assert - not constant")]] () { }(); if (not cond) [] [[gnu::noinline, gnu::error("constant assert - false")]] () { }(); }
```

## 6.1 Why not a library function?

To extract the expression and present it in the compile output it would need be a macro, and we would need better ways to produce error messages.

Secondly, we do not want to base this on the constant expression query. It already has uses as a way to check if code is optimized and if not replace with something else.

This mean is should strictly follow what the optimizer actually apply to the code. For constant\_assert on the other hand, we want the optimizer to do whatever it takes to prove it, even if it is not going to use the result to optimize the code.

## 6.2 LTO

With LTO, final constant folding and code generation may not take place until linking. Allowing constant\_assert to be deferred to the link step would make it very hard for programmers to act upon and identify the cause of errors.

Is is suggested that constant\_assert is always resolved at the compilation step, and a separate feature is later added for linker resolved assert if needed.

## 7 References

```
[constant_p] Gcc. Built-in Function: int __builtin_constant_p (exp). https://gcc.gnu.org/onlinedocs/gcc/Other-Builtins.html#index-_005f_005fbuiltin_005fconstant_005fp
```