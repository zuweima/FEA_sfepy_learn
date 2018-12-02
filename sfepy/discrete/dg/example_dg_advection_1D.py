import numpy as nm
import matplotlib.pyplot as plt

# sfepy imports
from sfepy.discrete.fem import Mesh
from sfepy.discrete.fem.meshio import UserMeshIO
from sfepy.base.base import Struct
from sfepy.base.base import IndexedStruct
from sfepy.discrete import (FieldVariable, Material, Integral, Function,
                            Equation, Equations, Problem)
from sfepy.discrete.fem import Mesh, FEDomain, Field
from sfepy.discrete.conditions import InitialCondition, EssentialBC, Conditions
from sfepy.terms.terms import Term
from sfepy.solvers.ls import ScipyDirect
from sfepy.solvers.nls import Newton
from sfepy.solvers.ts_solvers import SimpleTimeSteppingSolver

from sfepy.base.conf import ProblemConf


# local import
from dg_terms import AdvFluxDGTerm, AdvVolDGTerm
# from dg_equation import Equation
from dg_tssolver import EulerStepSolver, DGTimeSteppingSolver, RK3StepSolver
from dg_field import DGField

from my_utils.inits_consts import left_par_q, gsmooth, const_u, ghump, superic
from my_utils.visualizer import load_vtks, plot1D_DG_sol

X1 = -.5
XN1 = .5
n_nod = 100
n_el = n_nod - 1
coors = nm.linspace(X1, XN1, n_nod).reshape((n_nod, 1))
conn = nm.arange(n_nod, dtype=nm.int32).repeat(2)[1:-1].reshape((-1, 2))
mat_ids = nm.zeros(n_nod - 1, dtype=nm.int32)
descs = ['1_2']
mesh = Mesh.from_data('advection_1d', coors, None,
                      [conn], [mat_ids], descs)

t0 = 0
t1 = .8
tn = 200
speed = 1.0

approx_order = 2

integral = Integral('i', order=5)
domain = FEDomain('domain', mesh)
# FEDomain contains default lagrange polyspace in its geometry
omega = domain.create_region('Omega', 'all')
left = domain.create_region('Gamma1',
                              'vertices in x == %.10f' % X1,
                              'vertex')
right = domain.create_region('Gamma2',
                              'vertices in x == %.10f' % XN1,
                              'vertex')
field = DGField('dgfu', nm.float64, 'scalar', omega,
                approx_order=approx_order, integral=integral)
# field = Field.from_args('fu', nm.float64, 'scalar', omega, approx_order=approx_order)
u = FieldVariable('u', 'unknown', field, history=1)
v = FieldVariable('v', 'test', field, primary_var_name='u')


IntT = AdvVolDGTerm(integral, omega, u=u, v=v)

a = Material('a', val=[speed])
FluxT = AdvFluxDGTerm(integral, omega, u=u, v=v, a=a)

eq = Equation('balance', IntT + FluxT)
eqs = Equations([eq])

left_fix_u = EssentialBC('left_fix_u', left, {'u.all' : 0.0})
right_fix_u = EssentialBC('right_fix_u', right, {'u.all' : 0.0})


def ic_wrap(x, ic=None):
    return ghump(x)


ic_fun = Function('ic_fun', ic_wrap)
ics = InitialCondition('ic', omega, {'u.0': ic_fun})

pb = Problem('advection', equations=eqs)
pb.setup_output(output_dir="./output/" )#, output_format="h5")
pb.set_bcs(ebcs=Conditions([left_fix_u, right_fix_u]))
pb.set_ics(Conditions([ics]))

# state0 = pb.get_initial_state()

ls = ScipyDirect({})
nls_status = IndexedStruct()
nls = Newton({'is_linear' : True}, lin_solver=ls, status=nls_status)
# nls = EulerStepSolver({}, lin_solver=ls, status=nls_status)
nls = RK3StepSolver({}, lin_solver=ls, status=nls_status)


dt = float(t1 - t0) / tn
dx = nm.max(mesh.coors[1:] - mesh.coors[:-1])
dtdx = dt / dx
maxa = nm.max(nm.abs(speed))
print("Space divided into {0} cells, {1} steps, step size is {2}".format(mesh.n_el, len(mesh.coors), dx))
print("Time divided into {0} nodes, {1} steps, step size is {2}".format(tn - 1, tn, dt))
print("Courant number c = max(abs(u)) * dt/dx = {0}".format(maxa * dtdx))

tss = DGTimeSteppingSolver({'t0' : t0, 't1' : t1, 'n_step': tn},
                               nls=nls, context=pb, verbose=True)

# tss = SimpleTimeSteppingSolver({'t0' : t0, 't1' : t1, 'n_step' : tn},
#                                nls=nls, context=pb, verbose=True)
pb.set_solver(tss)

# pb.time_update(tss.ts)
pb.solve()


#--------
#| Plot |
#--------
lmesh, u = load_vtks("./output/", "domain", tn, order=approx_order)
plot1D_DG_sol(lmesh, t0, t1, u, dt=dt,  ic=ic_wrap)
