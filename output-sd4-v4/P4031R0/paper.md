# Rename
system_context_replaceability namespace


Document #:

P4031R0
[Latest]
[Status]




Date:
2026-02-23



Project:
Programming Language C++



Audience:

LEWG




Reply-to:

Ruslan Arutyunyan<ruslan.arutyunyan@intel.com>




# Abstract

This paper proposes to rename
system_context_replaceability
namespace.

# 1 Motivation

There was one attempt to rename
system_context_replaceability.
Unfortunately, it didn’t go well because likely the proposed
alternatives for the names were not received well. [P3804R1] proposed several options
favoring replacement and
replacement_functions. As people
pointed out, those names are probably also not great because they don’t
give any sense of what developers try to replace. For example std::execution::replacement::receiver_proxy
doesn’t help to understand what we’re actually replacing. The motivation
to recommend either replacement or
replacement_functions came because
system_context_replaceability felt
too long for a namespace name. However, people don’t seem to care about
the length of the name. The poll below taken in Kona meeting (2025)
shows that:

POLL: Change namespace
system_context_replacability to
replacement as proposed in
P3804R0 Iterating on
parallel_scheduler.

SF

F

N

A

SA

2
1
6
5
1

What is also important to note is that the poll was only about
changing the current status quo to
replacement. We have not voted for
other options in [P3804R1]. Nevertheless, in my opinion
we have to rename
system_context_replaceability to
something else because what we should care about is the consistency of
C++ standard (whenever possible). Adding
system_context_replaceability
namespace name to C++26 will cause a lot of confusion because
system_context does not even exist
in the current working draft. Thus, users would not understand what they
are actually replacing. What we have in the current working draft is
actually named parallel_scheduler
and the replaceability feature was developed specifically for it. I
understand the argument that suggested
replacement option perhaps does not
give us what we want but it doesn’t eliminate the fact that we should
rename system_context_replaceability
to avoid even bigger confusion because std::execution::system_context_replaceability::receiver_proxy
with no system_context presence
anywhere in the C++ working draft is no better.

Based on the above either of
parallel_scheduler_replaceability or
parallel_scheduler_replacement name
should be good enough because people seem to not be bothered by the name
length and also because
parallel_scheduler is exactly the
name we have for the scheduler itself in the current working draft.
Leaving the status quo would be a disaster, in my opinion.

# 2 Proposal

Option 1: Change std::execution::system_context_replaceability
namespace name to std::execution::parallel_scheduler_replaceability.

Option 2: Change std::execution::system_context_replaceability
namespace name to std::execution::parallel_scheduler_replacement.

Modify the formal wording in accordance with the winning option (if
any wins compared to the status quo).

I like the second option slightly better because
replaceability word means the feature to me and
replacement sounds more like a set of the actual API. But I can
live with any of those.

# 3 References

[P3804R1] Lucian Radu Teodorescu, Ruslan Arutyunyan. 2025-12-15.
Iterating on parallel_scheduler.
https://wg21.link/p3804r1