# [P3724R3](https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4/P3724R3/paper.md) - Integer division
Answered 1 of 1 applicable questions.

**Q1. Does the paper show code of the feature it is proposing?**
> const int bucket_size = 1000;
> int elements = 100;
> 
> int buckets_required = elements / bucket_size; // WRONG, zero
> int buckets_required = std::div_to_pos_inf(elements, bucket_size); // OK, one bucket
