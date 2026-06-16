import numpy as np
from scipy.optimize import fsolve
from scipy.integrate import solve_ivp

R = 1e-5
C = 1
def dVdt(t,V):
    return (5 - V)/(R*C)



T = 1e-4
tspan = [0,T]
dt = 1e-7
nT = int(T/dt)
t = 0
V = np.zeros(nT+1)

for i1 in range(nT):
    V[i1+1] = V[i1] + dt*dVdt(t,V[i1])
    t += dt
A0 = V.copy()


T = 1e-4
tspan = [0,T]
dt = 2e-5
nT2 = int(T/dt)
t = 0
V2 = np.zeros(nT2+1)

for i1 in range(nT2):
    V2[i1+1] = V2[i1] + dt*dVdt(t,V2[i1])
    t += dt
A1 = V2.copy()

T = 1e-4
tspan = [0,T]
dt = 2e-5
nT = int(T/dt)
t = 0
V = np.zeros(nT+1)
for i1 in range(nT):
    Vn = lambda Vp: V[i1] + dt*dVdt(t+dt,Vp) - Vp
    V[i1+1] = fsolve(Vn,V[i1])[0]
    t += dt
A2 = V.copy()
sol = solve_ivp(dVdt, tspan, [0])

A3 = sol.y[0].copy()
A4 = sol.t.copy()

E = 5-5*np.exp(-10)

A5 = np.abs(np.array([A0[-1],A1[-1],A2[-1],A3[-1]]) - E)
print(A5)



a = 3/4
b = 1/2
def dRJdt(t,y):
    R = y[0]
    J = y[1]
    return [b*R+J,-R-a*J]


tspan = [0,20]
t = np.linspace(0,20,100)
sol = solve_ivp(dRJdt, tspan, [-1,4],t_eval = t)
A6 = sol.y[0]
A7 = sol.y[1]


A = np.zeros((2,2)); A[0,0] = b; A[0,1] = 1; A[1,0] = -1; A[1,1] = -a;
y = np.zeros((2))
y[0] = -1; y[1] = 4;


T = 20
tspan = [0,T]
dt = .1
nT = int(T/dt)
t = 0
for i1 in range(nT):
    y = y + dt*A@y
    t += dt

A8 = y[0]
A9 = y[1]
