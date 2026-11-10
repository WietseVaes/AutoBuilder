# Expected: 20/20.
using Plots   # listed in rubric.json "requirements"

# Unicode names work everywhere: typed as \lambda<tab>, \omega<tab>, \sigma<tab>\^2<tab>
λ = 0.2
ω = 3.0
σ²(v) = sum((v .- sum(v) / length(v)) .^ 2) / (length(v) - 1)   # sample variance

t = range(0, 10; length=100)
damped_wave = exp.(-λ .* t) .* sin.(ω .* t)

# ── Plot returned by a function without inputs ────────────────────────────────
function make_damped_wave_plot()
    return plot(t, damped_wave; xlabel="time (s)", ylabel="amplitude",
                title="Damped Sine Wave", label="damped wave")
end

# ── Plot returned by a function with an input (Unicode argument name) ─────────
function envelope_plot(λ₀)
    p = plot(t, exp.(-λ₀ .* t); label="upper", xlabel="t", ylabel="envelope", ylims=(-1.1, 1.1))
    plot!(p, t, -exp.(-λ₀ .* t); label="lower")
    return p
end

# ── Plot stored in a variable: a bar chart ────────────────────────────────────
counts = [3, 7, 5, 2]
bars_plot = bar(["A", "B", "C", "D"], counts; label="", title="Counts per group",
                xlabel="group", ylabel="count")
