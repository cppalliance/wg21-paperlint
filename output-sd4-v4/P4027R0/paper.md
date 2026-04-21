# P4027R02026-02 Library Evolution Polls


## Published Proposal,
2026-02-22



Authors:
Inbal Levi - Library Evolution Chair (Microsoft LTD)
Fabio Fracassi - Library Evolution Assistant Chair (CODE University of Applied Sciences)
Andreas Weis - Library Evolution Assistant Chair (ekxide IO GmbH)
Corentin Jabot - Library Mailing List Review Manager
Source:
GitHub
Project:
ISO/IEC 14882 Programming Languages — C++, ISO/IEC JTC1/SC22/WG21
Audience:
WG21











## 1. Introduction

This paper contains the decision polls that the C++ Library Evolution group
will take in February 2026.


## 2. Voting

These decision polls will be conducted electronically; see [P2195R2] for
more information on electronic voting procedures.

All committee members may vote, but if you have not participated in the
Library Evolution discussions of a poll (in-person, over telecon, or
over email), please consider whether you sufficiently understand the
topic to be able to vote in an informed manner.
If you do not, please choose to not participate in the poll.


### 2.1. How to Vote

Vote here



A documents.isocpp.org account is necessary to vote.
If you have an isocpp.org/papers account, a documents.isocpp.org account has
been created for you.
Just go to documents.isocpp.org and reset your password.
Email Inbal Levi and Nevin Liber if you
do not have an account or are having trouble accessing your account.

If you see "Form not found" when you go to the above link, you are not signed
in to documents.isocpp.org.
Go to documents.isocpp.org and sign in first.

You will not receive a confirmation email after voting.
The Library Evolution chairs will send a confirmation to all voters before the
close of the poll.

If you need to change how you voted or have any questions or issues about
voting, please email
Inbal Levi.


### 2.2. Voting Timeline



2026-02-20: Draft polls distributed to chairs.


2026-02-23: Start of the polling period.


2026-03-10: End of the polling period.


2026-04-10: Results and summarized comments are shared in the follow-up paper [P4028].



## 3. Poll Structure

Each poll consists of a statement; you vote on whether you support the
statement.
All polls will be 5-way polls; you’ll vote either "strongly favor",
"weakly favor", "neutral", "weakly against", or "strongly against".

Polls phrased as "Return X" indicate that the paper was sent to Library Working
Group in the past, and Libary Working Group returned it to us with
questions.
Polls phrased as "Send X" indicate that the paper has not previously been sent
to Library Working Group.

All committee members may vote, but if you have not participated in the
Library Evolution discussions of a poll (in-person, over telecon, or
over email), please consider whether you sufficiently understand the
topic to be able to vote in an informed manner.
If you do not, please choose to not participate in the poll.

If you do not want to participate in a poll, select the "I do not want to
participate in this poll" option.
Those who do not participate in a poll will not be counted or recorded.
Voting neutral is not the same as choosing to not participate; please
don’t vote neutral if you did not participate in the discussions of
the poll.

Each poll has a comment field.
Please write a few sentences explaining the rationale for your vote.
We recommend drafting your comments in a text editor and then pasting them
into the polling system.

Poll results and selected comments will be shared with Library Evolution after
the end of the polling period, including attribution of your votes and
comments.

If you want to discuss the polls or how you plan on voting, please start an
email thread on the
Library Evolution mailing list.

If you need to see how you voted, change how you voted, or have any questions
or issues about voting, please contact the Library Evolution chair.


### 3.1. Polls

IMPORTANT: Please see the polls form for extended info and links.


#### 3.1.1. US 90-197

POLL: Address
NB US 90-197
by adopting the wording changes affecting define_static_object ([meta.syn] and [meta.define.static]) from P3739R4 and forward to LWG for C++26.


NOTE: This poll is not about appling the full paper, only the specific section related to [meta].




#### 3.1.2. US 67-118, PL-012, GB 03-119, DE-120, and FI-121

POLL: Address US 67-118, PL-012, GB 03-119, DE-120, and FI-121 by applying the changes in "P3842R0: A conservative fix for constexpr uncaught_exceptions() and current_exception()" and forward to LWG for C++26.


#### 3.1.3. US 135-216 and US 136-217

POLL: We want to resolve the issues regarding trivial copyability of expected raised by US 135-216, US 136-217 via LWG 4513 issue that applies the suggested changes to C++26.


#### 3.1.4. FR-030-310

POLL: Apply the changes discussed (make address_return_t exposition-only, apply wording fix) to P3936R0 and apply as the resolution to FR-030-310 and forward to LWG for C++26.


#### 3.1.5. US 254-385

POLL: Resolve the NB comment US 254-385 by applying the wording from P3980R0 section 3.1 (wording change A amended for member overload) and send to LWG for C++26.


#### 3.1.6. US 253-386, US 255-384 and US 261-391

POLL: We accept the changes in P3980R0 as the resolution of:
(1) "US 253-386 33.13.6.5 [task.promise] Allow use of arbitrary allocators for coroutine frame LWG4333" (fixed by applying wording from P3980R0 section 3.1)
(2) "US 255-384: 33.13.6.5 [task.promise] Use allocator from receiver’s environment LWG4335" (Paper: P3980R0) (by wording changes from P3980R0 section 4.1)
(3) US 261-391: 33.13.6.5p3, 16, 17 [task.promise] Bad specification of parameter type (wording removed as part of P3980R0 section 3.1)

and forward to LWG for C++26.


#### 3.1.7. US 68-122, US 150-228, GB 08-225, PL-006, and US 149

POLL: Adopt the proposed changes that apply to inplace_vector try_push_back and try_emplace_back from P3981R0 to address US 68-122, US 150-228 and GB 08-225, partially address PL-006, and reject US 149.



IMPORTANT: Please see the polls form for extended info and links.




## References


### Informative References


[P2195R2]
Bryce Adelstein Lelbach. Electronic Straw Polls. 28 January 2021. URL: https://wg21.link/p2195r2