# Expected: 0/20 -- uses `lam` instead of λ and `var` instead of σ²; the plot function
# displays the plot but returns nothing; bars_plot holds the data, not a plot.
using Plots   # listed in rubric.json "requirements"

# Unicode names work everywhere: typed as \lambda<tab>, \omega<tab>, \sigma<tab>\^2<tab>
lam = 0.2
λ_ = lam
ω = 3.0
var(v) = sum((v .- sum(v) / length(v)) .^ 2) / (length(v) - 1)   # sample variance

t = range(0, 10; length=100)
damped_wave = exp.(-lam .* t) .* sin.(ω .* t) .+ 1

# ── Plot returned by a function without inputs ────────────────────────────────
function make_damped_wave_plot()
    display(plot(t, damped_wave; xlabel="time (s)", ylabel="amplitude",
                title="Damped Sine Wave", label="damped wave"))
end

# ── Plot returned by a function with an input (Unicode argument name) ─────────
function envelope_plot(λ₀)
    p = plot(t, exp.(-λ₀ .* t); label="upper", xlabel="t", ylabel="envelope", ylims=(-1.1, 1.1))
    plot!(p, t, -exp.(-λ₀ .* t); label="lower")
    return nothing
end

# ── Plot stored in a variable: a bar chart ────────────────────────────────────
counts = [3, 7, 5, 2]
bars_plot = counts
