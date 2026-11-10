# Expected: 0/4 -- named it `scores` instead of `final_scores`.
using Statistics

# Survey results: each row is one food truck's scores across three
# categories (taste, value, speed), each out of 10.
reviews = [8.5 7.64 7.65;
           3.0 3.5  3.61;
           4.5 4.0  4.5;
           3.0 3.0  3.06]

scores = vec(mean(reviews; dims=2))
