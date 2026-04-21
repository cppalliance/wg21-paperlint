# [P4003R0](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P4003R0/paper.md) - Coroutines for I/O
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> // Basic: executor only
> run_async( ex )( my_task() );
> 
> // Full: executor, stop_token, frame allocator, success handler, error handler
> run_async( ex, st, alloc, h1, h2 )( my_task() );
> …
