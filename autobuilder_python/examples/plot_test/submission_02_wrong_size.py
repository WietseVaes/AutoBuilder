import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

t = np.linspace(0, 2 * np.pi, 50)   # wrong: 50 points instead of 100
damped_wave = np.exp(-0.2 * t) * np.sin(3 * t)

def make_damped_wave_plot():
    fig, ax = plt.subplots()
    ax.plot(t, damped_wave, label="damped wave")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("amplitude")
    ax.set_title("Damped Sine Wave")
    ax.legend()
    return ax
