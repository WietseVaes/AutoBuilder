# Expected: 0/4 -- a 4×1 matrix instead of a vector (shows the _julia hint).
using Statistics

# Survey results: each row is one food truck's scores across three
# categories (taste, value, speed), each out of 10.
reviews = [8.5 7.64 7.65;
           3.0 3.5  3.61;
           4.5 4.0  4.5;
           3.0 3.0  3.06]

final_scores = mean(reviews; dims=2)
