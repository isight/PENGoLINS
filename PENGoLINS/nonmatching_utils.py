"""
The "nonmatching_utils" module
------------------------------
contains functions that can be used to compute coupling 
of non-matching.
"""

import os
from math import *
import numpy as np 

from mpi4py import MPI as pyMPI
from petsc4py import PETSc
from tIGAr.common import *
from tIGAr.BSplines import *
from tIGAr.NURBS import *
from igakit.cad import *

from PENGoLINS.transfer_matrix import *
from PENGoLINS.calculus_utils import *

DOLFIN_FUNCTION = function.function.Function
DOLFIN_VECTOR = cpp.la.Vector
DOLFIN_MATRIX = cpp.la.Matrix
DOLFIN_PETSCVECTOR = cpp.la.PETScVector
DOLFIN_PETSCMATRIX = cpp.la.PETScMatrix
PETSC4PY_VECTOR = PETSc.Vec
PETSC4PY_MATRIX = PETSc.Mat

SAVE_PATH = "./"

def v2p(v):
    """
    Convert "dolfin.cpp.la.PETScVector" to 
    "petsc4py.PETSc.Vec".
    """
    return as_backend_type(v).vec()

def m2p(A):
    """
    Convert "dolfin.cpp.la.PETScMatrix" to 
    "petsc4py.PETSc.Mat".
    """
    return as_backend_type(A).mat()

def arg2v(x):
    """
    Convert dolfin Function or dolfin Vector to petsc4py.PETSc.Vec.
    """
    if isinstance(x, DOLFIN_FUNCTION):
        x_PETSc = x.vector().vec()
    elif isinstance(x, DOLFIN_PETSCVECTOR):
        x_PETSc = v2p(x)
    elif isinstance(x, DOLFIN_VECTOR):
        # x_PETSc = zero_petsc_vec(x.size())
        # x_PETSc.setArray(x[:])
        # x_PETSc.assemble()
        x_PETSc = v2p(x)
    elif isinstance(x, PETSC4PY_VECTOR):
        x_PETSc = x
    else:
        raise TypeError("Type " + str(type(x)) + " is not supported.")
    return x_PETSc

def arg2m(A):
    """
    Convert dolfin Matrix to petsc4py.PETSc.Mat.
    """
    if isinstance(A, DOLFIN_PETSCMATRIX):
        A_PETSc = m2p(A)
    elif isinstance(A, DOLFIN_MATRIX):
        A_PETSc = m2p(A)
    elif isinstance(A, PETSC4PY_MATRIX):
        A_PETSc = A
    else:
        raise TypeError("Type " + str(type(A)) + " is not supported.")
    return A_PETSc

def A_x(A, x):
    """
    Compute b = A*x.

    Parameters
    ----------
    A : dolfin Matrix, dolfin PETScMatrix or PETSc.Mat
    x : dolfin Function, dolfin Vector, dolfin PETScVector
        or petsc4py.PETSc.Vec

    Returns
    -------
    b_PETSc : petsc4py.PETSc.Vec
    """
    A_PETSc = arg2m(A)
    x_PETSc = arg2v(x)

    # b_PETSc = PETSc.Vec(comm)
    # b_PETSc.create(comm=comm)
    # b_PETSc.setSizes(A_PETSc.getSizes()[0])  # Contains local size
    # b_PETSc.setUp()
    # # b_PETSc.assemble()

    b_PETSc = A_PETSc.createVecLeft()
    A_PETSc.mult(x_PETSc, b_PETSc)

    return b_PETSc

def A_x_b(A, x, b):
    """
    Compute "Ax = b".

    Parameters
    ----------
    A : dolfin Matrix, dolfin PETScMatrix or petsc4py.PETSc.Mat
    x : dolfin Function, dolfin Vector, dolfin PETScVector
        or petsc4py.PETSc.Vec
    b : dolfin Function, dolfin Vector, dolfin PETScVector
        or petsc4py.PETSc.Vec
    """
    return m2p(A).mult(v2p(x), v2p(b))

def AT_x(A, x):
    """
    Compute b = A^T*x.

    Parameters
    ----------
    A : dolfin Matrix, dolfin PETScMatrix or petsc4py.PETSc.Mat
    x : dolfin Function, dolfin Vector, dolfin PETScVector
        or petsc4py.PETSc.Vec

    Returns
    -------
    b_PETSc : petsc4py.PETSc.Vec
    """
    A_PETSc = arg2m(A)
    x_PETSc = arg2v(x)

    # b_PETSc = PETSc.Vec(A_PETSc.getComm())
    # b_PETSc.create(A_PETSc.getComm())
    # # # Raised error in parallel since local size is not passed
    # # b_PETSc.setSizes(A_PETSc.getSizes()[1][1]) 
    # b_PETSc.setSizes(A_PETSc.getSizes()[1])
    # b_PETSc.setUp()
    # # b_PETSc.assemble()

    b_PETSc = A_PETSc.createVecRight()
    A_PETSc.multTranspose(x_PETSc, b_PETSc)

    return b_PETSc

def AT_x_b(A, x, b):
    """
    Compute b = A^T*x.

    Parameters
    ----------
    A : dolfin Matrix, dolfin PETScMatrix or petsc4py.PETSc.Mat
    x : dolfin Function, dolfin Vector, dolfin PETScVector
        or petsc4py.PETSc.Vec
    b : dolfin Function, dolfin Vector, dolfin PETScVector
        or petsc4py.PETSc.Vec
    """
    arg2m(A).multTranspose(arg2v(x), arg2v(b))

def AT_R_B(A, R, B):
    """
    Compute "A^T*R*B". A,R and B are "petsc4py.PETSc.Mat".

    Parameters
    -----------
    A : petsc4py.PETSc.Mat
    R : petsc4py.PETSc.Mat
    B : petsc4py.PETSc.Mat

    Returns
    -------
    ATRB : petsc4py.PETSc.Mat
    """
    ATRB = A.transposeMatMult(R).matMult(B)
    return ATRB

def apply_bcs_vec(spline, v):
    """
    Apply boundary conditions of ``spline`` to vector ``v``.

    Parameters
    ----------
    spline : ExtractedSpline
    v : dolfin Function, dolfin Vector, dolfin PETScVector
        or PETSc.Vec
    """
    v_PETSc = arg2v(v)
    v_PETSc.setValues(spline.zeroDofs, 
        zeros(spline.zeroDofs.getLocalSize()))
    v_PETSc.assemblyBegin()
    v_PETSc.assemblyEnd()

def apply_bcs_mat(spline, A, diag=1):
    """
    Apply boundary conditions of ``spline`` to matrix ``A``.

    Parameters
    ----------
    spline : ExtractedSpline
    A : dolfin Matrix, dolfin PETScMatrix, PETSc.Mat or None
    diag : int, optional, default is 1
        Values put in all diagonals of eliminated rows.
        1 is for diagonal blocks, 0 is for off-diagonal blocks.
    """
    A_PETSc = arg2m(A)

    if diag == 0:
        A_PETSc.zeroRows(spline.zeroDofs, diag=diag)
    else:
        A_PETSc.zeroRowsColumns(spline.zeroDofs, diag=diag)

    A_PETSc.assemblyBegin()
    A_PETSc.assemblyEnd()

def IGA2FE(spline, u_IGA, applyBCs=False):
    """
    Convert the DoFs of ``u_IGA`` from IGA space to FE space. 

    Parameters
    ----------
    spline : ExtractedSpline
    u_IGA : dolfin Function, dolfin Vector, dolfin PETScVector
        or PETSc.Vec
    applyBCs : bool, optional, default is False

    Returns
    -------
    u_FE : dolfin PETScVector
    """
    if applyBCs:
        apply_bcs_vec(spline, u_IGA)
    u_FE_PETSc = A_x(spline.M, u_IGA)
    u_FE = PETScVector(u_FE_PETSc)

    return u_FE

def FE2IGA(spline, u_FE, applyBCs=True):
    """
    Convert the DoFs of``u_F`` from FE space to IGA space.

    Parameters
    ----------
    spline : ExtractedSpline
    u_FE : dolfin Function, dolfin Vector, dolfin PETScVector
        or PETSc.Vec
    applyBCs : bool, optional

    Returns
    -------
    u_IGA : dolfin PETScVector
    """
    u_IGA_PETSc = AT_x(spline.M, u_FE)
    u_IGA = PETScVector(u_IGA_PETSc)
    if applyBCs:
        apply_bcs_vec(spline, u_IGA)
    return u_IGA

def zero_petsc_vec(num_el, vec_type=None, comm=worldcomm):
    """
    Create zero PETSc vector of size ``num_el``.

    Parameters
    ----------
    num_el : int
    vec_type : str, optional, default is None
        For available types, see petsc4py.PETSc.Vec.Type.
    comm : MPI communicator

    Returns
    -------
    v : petsc4py.PETSc.Vec
    """
    v = PETSc.Vec(comm)
    v.create(comm=comm)
    if vec_type is not None:
        v.setType(vec_type)
    v.setSizes(num_el)
    v.setUp()
    v.assemble()
    return v

def zero_petsc_mat(row, col, mat_type=None, 
                   PREALLOC=500, comm=worldcomm):
    """
    Create zeros PETSc matrix with shape (``row``, ``col``).

    Parameters
    ----------
    row : int
    col : int
    mat_type : str, optional, default is None
        For available types, see petsc4py.PETSc.Mat.Type
    comm : MPI communicator

    Returns
    -------
    A : petsc4py.PETSc.Mat
    """
    A = PETSc.Mat(comm)
    if mat_type is not None:
        mat_type.setType(mat_type)
    A.setSizes([row, col])
    A.setPreallocationNNZ([PREALLOC, PREALLOC])
    A.setOption(PETSc.Mat.Option.NEW_NONZERO_ALLOCATION_ERR, False)
    A.setUp()
    A.assemble()
    return A

def penalty_differentiation(PE, vars1=[], vars2=[]):
    """
    Compute the differentiation of penalty energy ``PE`` w.r.t. 
    variables ``vars1`` and ``vars2``.

    Parameters
    -----------
    PE : ufl Form
    vars1 : list of dolfin Functions
    vars2 : list of dolfin Functions

    Returns
    -------
    R_list : list of ufl Forms, rank 2
    """
    R1_list = []
    R2_list = []
    for i in range(len(vars1)):
        R1_list += [derivative(PE, vars1[i])]
        R2_list += [derivative(PE, vars2[i])]
    R_list = [R1_list, R2_list]
    return R_list

def penalty_linearization(R_list, vars1=[], vars2=[]):
    """
    Compute the Jacobian of residuals of penalty energy "R_list"
    w.r.t. variables "vars1" and "vars2".

    Parameters
    -----------
    R_list : list of ufl Forms, rank 2
    vars1 : list of dolfin Functions
    vars2 : list of dolfin Functions

    Returns
    -------
    dR_du_list : list of ufl Forms, rank 4
    """
    vars_list = [vars1, vars2]
    num_R = len(R_list[0]) #3
    num_vars = len(vars_list[0]) #3

    dR_du_list = [[None for i1 in range(len(vars_list))] \
                        for i2 in range(len(R_list))]
    for i in range(len(R_list)):
        for j in range(len(vars_list)):
            dR_du_list[i][j] = [[None for i1 in range(num_vars)] \
                                      for i2 in range(num_R)]
            for m in range(num_R):
                for n in range(num_vars):
                    dR_du_list[i][j][m][n] = \
                        derivative(R_list[i][m], vars_list[j][n])

    return dR_du_list

def transfer_penalty_differentiation(R_list, A1_list, A2_list):
    """
    Compute the contribution of the residuals of the penalty terms on 
    RHS using transfer matrices.

    Parameters
    ----------
    R_list : list of ufl Forms, rank 2
    A1_list : list of dolfin PETScMatrix
    A2_list : list of dolfin PETScMatrix

    Returns
    -------
    R : list of petsc4py.PETSc.Vecs
    """
    R = [None for i1 in range(len(R_list))]
    A_list = [A1_list, A2_list]
    for i in range(len(R_list)):
        for j in range(len(R_list[i])):
            if R[i] is not None:
                R[i] += AT_x(A_list[i][j], assemble(R_list[i][j]))
            else:
                R[i] = AT_x(A_list[i][j], assemble(R_list[i][j]))
    return R

def transfer_penalty_linearization(dR_du_list, A1_list, A2_list):
    """
    Compute the contribution of the Jacobian of the penalty terms on 
    LHS using transfer matrix.

    Parameters
    ----------
    dR_du_list : list of ufl Forms, rank 4
    A1_list : list of dolfin PETScMatrix
    A2_list : list of dolfin PETScMatrix

    Returns
    -------
    dR_du : list of petsc4py.PETSc.Mats, rank 2 
    """
    dR_du = [[None for i1 in range(len(dR_du_list[0]))] \
                   for i2 in range(len(dR_du_list))]

    A_list = [A1_list, A2_list]
    for i in range(len(dR_du_list)):
        for j in range(len(dR_du_list[i])):
            for m in range(len(dR_du_list[i][j])):
                for n in range(len(dR_du_list[i][j][m])):
                    if dR_du[i][j] is not None:
                        dR_du[i][j] += AT_R_B(m2p(A_list[i][m]), 
                            m2p(assemble(dR_du_list[i][j][m][n])), 
                            m2p(A_list[j][n]))
                    else:
                        dR_du[i][j] = AT_R_B(m2p(A_list[i][m]), 
                            m2p(assemble(dR_du_list[i][j][m][n])), 
                            m2p(A_list[j][n]))
    return dR_du

def R2IGA(splines, R):
    """
    Convert residuals ``R`` from FE to IGA space.
    
    Parameters
    ----------
    splines : list of ExtractedSplines
    R : list of dolfin PETScVectors

    Returns
    -------
    R_IGA : list of dolfin PETScVectors
    """
    R_IGA = [None, None]
    for i in range(len(R)):
        R_IGA[i] = v2p(FE2IGA(splines[i], R[i]))
    return R_IGA

def dRdu2IGA(splines, dR_du):
    """
    Convert Jacobians "dR_du" from FE to IGA space.

    Parameters
    ----------
    splines : list of ExtractedSplines
    dR_du : list of petsc4py.PETSc.Mats, rank 2

    Returns
    -------
    dRdu_IGA : list of petsc4py.PETSc.Mats, rank 2
    """
    dRdu_IGA = [[None for i in range(len(dR_du[0]))] \
                      for j in range(len(dR_du))]
    for i in range(len(dR_du)):
        for j in range(len(dR_du[i])):
            if i == j:
                diag = 1
            else:
                diag = 0
            dRdu_IGA[i][j] = AT_R_B(m2p(splines[i].M), dR_du[i][j], 
                                    m2p(splines[j].M))
            apply_bcs_mat(splines[i], dRdu_IGA[i][j], splines[j], diag=diag)
    return dRdu_IGA

def create_nested_PETScVec(v_list, comm=worldcomm):
    """
    Create nested petsc4py.PETSc.Vec from ``v_list``.

    Parameters
    ----------
    v_list : list of PETSc.Vecs

    Returns
    -------
    v : petsc4py.PETSc.Vec
    """
    v = PETSc.Vec(comm)
    v.createNest(v_list, comm=comm)
    v.setUp()
    v.assemble()
    return v

def create_nested_PETScMat(A_list, PREALLOC=500, comm=worldcomm):
    """
    Create nested PETSc.Mat from ``A_list``.

    Parameters
    ----------
    A_list : list of petsc4py.PETSc.Mats, rank 2

    Returns
    -------
    A : petsc4py.PETSc.Mat
    """
    A = PETSc.Mat(comm)
    A.createNest(A_list, comm=comm)
    A.setPreallocationNNZ([PREALLOC, PREALLOC])
    A.setOption(PETSc.Mat.Option.NEW_NONZERO_ALLOCATION_ERR, False)
    A.setUp()
    A.assemble()
    return A

def ksp_solver(ksp_type=PETSc.KSP.Type.CG, pc_type=PETSc.PC.Type.LU, 
               rtol=1e-15):
    """
    Create PETSc KSP solver with type of ``ksp_type``.

    Parameters
    ----------
    ksp_type : type of KSP solver, optional
    rtol : float, solver tolerance, optional
    """
    ksp = PETSc.KSP().create()
    ksp.setType(ksp_type)
    # ksp.getPC().setType(pc_type)
    ksp.setTolerances(rtol=rtol)
    ksp.setFromOptions()
    return ksp

def ksp_solve(A, x, b, ksp_type=PETSc.KSP.Type.CG, 
              pc_type=PETSc.PC.Type.FIELDSPLIT, rtol=1e-15):
    """
    Solve "Ax=b" using PETSc Krylov solver.

    Parameters
    ----------
    A : PETSc.Mat
    x : PETSc.Vec
    b : PETSc.Vec
    ksp_type : type of KSP solver, optional
    rtol : float, solver tolerance, optional
    """
    ksp = PETSc.KSP().create()
    ksp.setType(ksp_type)

    # # Setting preconditioner
    # ksp.getPC().setType(pc_type)
    # ksp.getPC().setType(PETSc.PC.Type.FIELDSPLIT)  # works in parallel
    # ksp.getPC().setFieldSplitType(PETSc.PC.CompositeType.ADDITIVE) 

    PETScOptions.set('pc_type', 'fieldsplit')
    PETScOptions.set('pc_fieldsplit_type', 'additive')
    # # PETScOptions.set('pc_fieldsplit_detect_saddle_point')

    PETScOptions.set('fieldsplit_0_ksp_type', 'preonly')
    PETScOptions.set('fieldsplit_0_pc_type', 'lu')

    PETScOptions.set('fieldsplit_1_ksp_type', 'preonly')
    PETScOptions.set('fieldsplit_1_pc_type', 'jacobi')
    
    ksp.setTolerances(rtol=rtol)
    ksp.setOperators(A)
    ksp.setFromOptions()
    ksp.solve(b, x)

def solve_nested_mat(A, x, b, solver=None):
    """
    Solve nested PETSc.Mat "Ax=b".

    Parameters
    ----------
    A : nested PETSc.Mat
    x : nested PETSc.Vec
    b : nested PETSc.Vec
    solver : None, 'ksp', PESTc.KSP, PETScLUSolver, PETScKrylovSolver. 
        If None, use dolfin solver
    """
    if not isinstance(A, PETSC4PY_MATRIX):
        raise TypeError("Type "+str(type(A))+" is not supported yet.")
    if solver is None:
        # Only works in parallel
        # PARALLEL NOTE: PETSc error code 56
        if A.type != 'seqaij':
            A.convert('seqaij')
        solve(PETScMatrix(A), PETScVector(x), PETScVector(b), "mumps")
    elif solver == 'ksp':
        # Works in parallel
        ksp_solve(A, x, b)
    else:
        solver.ksp().setOperators(A=A)
        solver.ksp().solve(b, x)
        solver.ksp().reset()

def save_results(spline, u, index, file_name="u", save_path=SAVE_PATH, 
                 folder="results/", save_cpfuncs=True, comm=worldcomm):
    """
    Save results to .pvd file.

    Parameters
    ----------
    spline : ExtractedSpline
    u : dolfin Function
    index : int, index of the file
    save_cpfuncs : bool, optional
        If True, save spline.cpFuncs to pvd file. Default is True
    save_path : str, optional

    To view the saved files in Paraview:
    ------------------------------------------------------------------------------
    (F0_0/F0_3-coordsX)*iHat + (F0_1/F0_3-coordsY)*jHat + (F0_2/F0_3-coordsZ)*kHat
    (u0_0/F0_3)*iHat + (u0_1/F0_3)*jHat + (u0_2/F0_3)*kHat
    ------------------------------------------------------------------------------
    (F1_0/F1_3-coordsX)*iHat + (F1_1/F1_3-coordsY)*jHat + (F1_2/F1_3-coordsZ)*kHat
    (u1_0/F1_3)*iHat + (u1_1/F1_3)*jHat + (u1_2/F1_3)*kHat
    ------------------------------------------------------------------------------
    (F2_0/F2_3-coordsX)*iHat + (F2_1/F2_3-coordsY)*jHat + (F2_2/F2_3-coordsZ)*kHat
    (u2_0/F2_3)*iHat + (u2_1/F2_3)*jHat + (u2_2/F2_3)*kHat
    ------------------------------------------------------------------------------
    (F3_0/F3_3-coordsX)*iHat + (F3_1/F3_3-coordsY)*jHat + (F3_2/F3_3-coordsZ)*kHat
    (u3_0/F3_3)*iHat + (u3_1/F3_3)*jHat + (u3_2/F3_3)*kHat
    ------------------------------------------------------------------------------
    for index = 0, 1, 2, 3, etc.
    """
    u_split = u.split()

    if len(u_split) == 0:
        name_disp = file_name + str(index)
        u.rename(name_disp,name_disp)
        File(comm, save_path + folder + name_disp + "_file.pvd") << u
    else:
        for i in range(len(u_split)):
            name_disp = file_name + str(index) + "_" + str(i)
            u_split[i].rename(name_disp,name_disp)
            File(comm, save_path + folder + name_disp 
                + "_file.pvd") << u_split[i]

    if save_cpfuncs:
        for i in range(spline.nsd+1):
            name_control_mesh = "F" + str(index) + "_" + str(i)
            spline.cpFuncs[i].rename(name_control_mesh, name_control_mesh)
            File(comm, save_path + folder + name_control_mesh 
                + "_file.pvd") << spline.cpFuncs[i]

def save_cpfuncs(cpfuncs, index, save_path=SAVE_PATH, folder="results/", 
                 comm=worldcomm):
    """
    Save control point functions ``cpfuncs`` of an ExtractedSpline.

    Parameters
    -----------
    cpfuncs : list of dolfin Functions, or spline.cpFuns
    index : int, index of the save file
    save_path : str, optional

    To view save file in Paraview:
    -----------------------------------------
    (cpfuncs0_0/cpfuncs0_3-coordsX)*iHat \
    + (cpfuncs0_1/cpfuncs0_3-coordsY)*jHat \
    + (cpfuncs0_2/cpfuncs0_3-coordsZ)*kHat
    -----------------------------------------
    (cpfuncs1_0/cpfuncs1_3-coordsX)*iHat \
    + (cpfuncs1_1/cpfuncs1_3-coordsY)*jHat \
    + (cpfuncs1_2/cpfuncs1_3-coordsZ)*kHat
    -----------------------------------------
    (cpfuncs2_0/cpfuncs2_3-coordsX)*iHat \
    + (cpfuncs2_1/cpfuncs2_3-coordsY)*jHat \
    + (cpfuncs2_2/cpfuncs2_3-coordsZ)*kHat
    -----------------------------------------
    (cpfuncs3_0/cpfuncs3_3-coordsX)*iHat \
    + (cpfuncs3_1/cpfuncs3_3-coordsY)*jHat \
    + (cpfuncs3_2/cpfuncs3_3-coordsZ)*kHat
    -----------------------------------------
    for index = 0, 1, 2, 3, etc.
    """
    for i in range(len(cpfuncs)):
        name_control_mesh = "cpfuncs" + str(index) + "_" + str(i)
        cpfuncs[i].rename(name_control_mesh, name_control_mesh)
        File(comm, save_path + folder + name_control_mesh 
            + "_file.pvd") << cpfuncs[i]

def generate_interpolated_data(data, num_pts):
    """
    Given initial data ``data`` and specify the number of points 
    ``num_pts``, return the nearly evenly interpolated data.

    Parameters
    ----------
    data : ndarray
    num_pts : int

    Returns
    -------
    interp_data : ndarray
    """
    if data.ndim == 1:
        data = np.array([data]).transpose()
    rows, cols = data.shape

    if rows > num_pts:
        if mpirank == 0:
            print("Number of points to interpolate {} is smaller than the "
                  "number of given points {}, removing points from data to "
                  "match the number of points.".format(num_pts, rows))
        num_remove = rows - num_pts
        remove_ind = np.linspace(1, rows-2, num_remove, dtype=int)
        interp_data = np.delete(data, remove_ind, axis=0)
    
    elif rows == num_pts:
        interp_data = data

    else:
        num_insert = num_pts - rows
        num_interval = rows - 1
        interp_data = np.zeros((num_pts, cols))

        num1 = round(num_insert/num_interval)
        num_insert_element = np.ones(num_interval).astype(int)*int(num1)
        round_num = int(num1*num_interval)
        diff = int(round_num - num_insert)

        if diff > 0:
            for i in range(abs(int(diff))):
                num_insert_element[i] -= 1
        elif diff < 0:
            for i in range(abs(int(diff))):
                num_insert_element[i] += 1

        num_pts_element = num_insert_element + 1

        for i in range(num_interval):
            for j in range(cols):
                if i == num_interval-1:
                    interp_data[np.sum(num_pts_element[0:i]):num_pts, j] \
                    = np.linspace(data[i,j], data[i+1,j], 
                                  num_pts_element[i]+1)[0:]
                else:
                    interp_data[np.sum(num_pts_element[0:i]):np.sum(\
                        num_pts_element[0:i+1]), j] = np.linspace(data[i,j], \
                        data[i+1,j], num_pts_element[i]+1)[0:-1]

    return interp_data

def generate_mortar_mesh(pts=None, num_el=None, data=None, comm=worldcomm):
    """
    Create topologically 1D, geometrically 1, 2 or 3D mortar mesh with 
    a single row of elements connecting them using given data points.

    Parameters
    ----------
    pts : ndarray or None, optional 
        Locations of nodes of mortar mesh
    num_el : int or None, optional 
        number of elements of mortar mesh
    data : ndarray or None, optional 
        Locations of nodes of mortar mesh. If ``data`` is not given, 
        ``pts`` and ``num_el`` are required.
    comm : mpi4py.MPI.Intarcomm, optional

    Returns
    -------
    mesh : dolfin Mesh
    """
    if data is not None:
        data = data
    else:
        data = generate_interpolated_data(pts, num_el+1)

    MESH_FILE_NAME = generateMeshXMLFileName(comm)

    if MPI.rank(comm) == 0:

        if data.ndim == 1:
            data = np.array([data]).transpose()
        rows, cols = data.shape

        dim = cols
        nverts = rows
        nel = nverts - 1

        fs = '<?xml version="1.0" encoding="UTF-8"?>' + "\n"
        fs += '<dolfin xmlns:dolfin="http://www.fenics.org/dolfin/">' + "\n"
        fs += '<mesh celltype="interval" dim="' + str(dim) + '">' + "\n"

        fs += '<vertices size="' + str(nverts) + '">' + "\n"
        if dim == 1:
            for i in range(nverts):
                x0 = repr(data[i,0])
                fs += '<vertex index="' + str(i) + '" x="' + x0 + '"/>' + "\n"
            fs += '</vertices>' + "\n"

        elif dim == 2:
            for i in range(nverts):
                x0 = repr(data[i,0])
                y0 = repr(data[i,1])
                fs += '<vertex index="' + str(i) + '" x="' + x0 \
                   + '" y="' + y0 + '"/>' + "\n"
            fs += '</vertices>' + "\n"

        elif dim == 3:
            for i in range(nverts):
                x0 = repr(data[i,0])
                y0 = repr(data[i,1])
                z0 = repr(data[i,2])
                fs += '<vertex index="' + str(i) + '" x="' + x0 \
                   + '" y="' + y0 + '" z="' + z0 +'"/>' + "\n"
            fs += '</vertices>' + "\n"

        else:
            raise ValueError("Unsupported parametric"
                " dimension: {}".format(dim))

        fs += '<cells size="' + str(nel) + '">' + "\n"
        for i in range(nel):
            v0 = str(i)
            v1 = str(i+1)
            fs += '<interval index="' + str(i) + '" v0="' + v0 + '" v1="' \
                + v1 + '"/>' + "\n"

        fs += '</cells></mesh></dolfin>'

        f = open(MESH_FILE_NAME,'w')
        f.write(fs)
        f.close()
        
    MPI.barrier(comm)    
    mesh = Mesh(MESH_FILE_NAME)

    if MPI.rank(comm) == 0:
        os.remove(MESH_FILE_NAME)

    return mesh

def deformed_position(spline, xi, u_hom):
    """
    Return deformed position of a point in physical domain by giving 
    the parametric location and displacement.

    Parameters
    ----------
    spline : ExtractedSpline
    xi : ndarray, parametric location of point
    u_hom : dolfin Function, displacement of point

    Returns
    -------
    position : ndarray
    """
    position = np.zeros(3)
    for i in range(3):
        # # Direct evaluation doesn't work in parallel
        # position[i] = (spline.cpFuncs[i](xi)
        #     +u_hom(xi)[i])/spline.cpFuncs[3](xi)
        cp_funcs_i = eval_func(spline.mesh, spline.cpFuncs[i], xi)
        u_hom_i = eval_func(spline.mesh, u_hom[i], xi)
        w = eval_func(spline.mesh, spline.cpFuncs[3], xi)
        position[i] = (cp_funcs_i + u_hom_i)/w
    return position

def undeformed_position(spline, xi):
    """
    Return undeformed position of a point in the physical domain by 
    specifying the parametric location.

    Parameters
    ----------
    spline : ExtractedSpline
    xi : ndarray, parametric location of point

    Returns
    -------
    position : ndarray
    """
    position = np.zeros(3)
    for i in range(3):
        # position[i] = spline.cpFuncs[i](xi)/spline.cpFuncs[3](xi)
        cp_funcs_i = eval_func(spline.mesh, spline.cpFuncs[i], xi)
        w = eval_func(spline.mesh, spline.cpFuncs[3], xi)
        position[i] = cp_funcs_i/w
    return position

def compute_line_Jacobian(X):
    """
    Compute line Jacobian for mortar mesh.

    Parameters
    ----------
    X : dolfin ListTensor 
        Geometric mapping of the mortar mesh

    Returns
    -------
    line_Jacobian : ufl Sqrt
    """
    dXdxi = grad(X)
    line_Jacobian = sqrt(tr(dXdxi*dXdxi.T))
    return line_Jacobian

def move_mortar_mesh(mortar_mesh, mesh_location):#, um=None):
    """
    Move the mortar mesh to a specified location.

    Parameters
    ----------
    mortar_mesh : dolfin Mesh
    mesh_location : ndarray
    """
    Vm = VectorFunctionSpace(mortar_mesh, 'CG', 1)
    um = Function(Vm)

    num_node = int(um.vector().vec().getSizes()[1]\
                   /mortar_mesh.geometric_dimension())

    if num_node == mesh_location.shape[0]:
        mesh_location_data = mesh_location
    else:
        mesh_location_data = generate_interpolated_data(mesh_location, 
                                                        num_node)

    mesh_location_flat = mesh_location_data[::-1].reshape(-1, 1)
    v2p(um.vector()).setValues(np.arange(mesh_location_flat.size, 
                                dtype='int32'), mesh_location_flat)
    v2p(um.vector()).ghostUpdate()
    set_coordinates(mortar_mesh.geometry(), um)

def spline_mesh_phy_coordinates(spline, reshape=True):
    """
    Return the physical coordiantes of the spline mesh.

    Parameters
    ----------
    spline : ExtractedSpline
    reshape : bool, optional

    Returns
    -------
    phy_coordinates : ndarray
    """
    para_coordinates = spline.mesh.coordinates()
    phy_coordinates = np.zeros((para_coordinates.shape[0], 3))
    for i in range(para_coordinates.shape[0]):
        for j in range(3):
            phy_coordinates[i, j] = spline.F[j](para_coordinates[i])
    if reshape:
        num_rows = int(np.where(para_coordinates[:,0]==0.)[0][1])
        num_cols = int(para_coordinates.shape[0]/num_rows)
        phy_coordinates = phy_coordinates.reshape(num_rows, num_cols, 3)
    return phy_coordinates

def spline_mesh_size(spline):
    """
    Compute the mesh size in the physical space of 
    ExtractedSpline.

    Parameters
    ----------
    spline : ExtractedSpline

    Returns
    -------
    h : ufl math functions
    """
    # dxi_dxiHat = 0.5*ufl.Jacobian(spline.mesh)
    # dX_dxi = grad(spline.F)
    # dX_dxiHat = dX_dxi*dxi_dxiHat
    # h = sqrt(tr(dX_dxiHat*dX_dxiHat.T))
    h_param = CellDiameter(spline.mesh)
    dX_dxi = grad(spline.F)
    h = h_param*sqrt(tr(dX_dxi*dX_dxi.T))
    return h

def point_in_mesh(mesh, xi):
    """
    Check if a point of location ``xi`` is inside mesh.

    Parameters
    ----------
    mesh : dolfin mesh
    xi : ndarray

    Returns
    -------
    res : bool
    """
    return len(mesh.bounding_box_tree()\
        .compute_entity_collisions(Point(xi)))>0

def eval_func(mesh, f, xi, allreduce=True):
    """
    Evaluate function ``f`` at point ``xi``, where ``f`` has 
    domain of ``mesh``. This function is used in parallel.

    Parameters
    ----------
    mesh : dolfin mesh
    f : dolfin Function
    xi : ndarray
    allreduce : bool, optional, default is True.
    """
    pt_in_mesh = point_in_mesh(mesh, xi)
    pt_in_mesh_allgather = worldcomm.allgather(pt_in_mesh)

    if pt_in_mesh:
        res = f(xi)
    else:
        if len(f.ufl_shape) > 0:
            res = f.ufl_shape[0]*[0.0,]
        else:
            res = 0.

    if allreduce:
        if pt_in_mesh_allgather.count(True) > 1:
            mpi_op = pyMPI.MAX
        else:
            mpi_op = pyMPI.SUM
        res = worldcomm.allreduce(res, op=mpi_op)
    return res


# import matplotlib.pyplot as plt 
# from mpl_toolkits.mplot3d import Axes3D 

# def set_axes_equal(ax):
#     """
#     Set the 3D plot axes equal.

#     Parameters
#     ----------
#     ax : Axes3DSubplot
#     """
#     x_limits = ax.get_xlim3d()
#     y_limits = ax.get_ylim3d()
#     z_limits = ax.get_zlim3d()
#     x_range = abs(x_limits[1] - x_limits[0])
#     x_middle = np.mean(x_limits)
#     y_range = abs(y_limits[1] - y_limits[0])
#     y_middle = np.mean(y_limits)
#     z_range = abs(z_limits[1] - z_limits[0])
#     z_middle = np.mean(z_limits)
#     plot_radius = 0.5*max([x_range, y_range, z_range])
#     ax.set_xlim3d([x_middle - plot_radius, x_middle + plot_radius])
#     ax.set_ylim3d([y_middle - plot_radius, y_middle + plot_radius])
#     ax.set_zlim3d([z_middle - plot_radius, z_middle + plot_radius])

# def plot3D(data, style="-", color=None, label=None, 
#            linewidth=1, fig=None, axes_equal=False,
#            x_label="x", y_label="y", z_label="z"):
#     """
#     3D plot.

#     Parameters
#     ----------
#     data : ndarray, 3-dimensional
#     style : str, optional
#     color : str, optional
#     label : str, optional
#     linewidth : int, optional
#     fig : matplotlib Figure, optional
#     axes_equal : bool, optional
#     xlabel : str, optional
#     ylabel : str, optional
#     zlabel : str, optional
#     """
#     if fig is None:
#         fig = plt.figure()
#     ax = fig.gca(projection='3d')
#     ax.plot(data[:,0], data[:,1], data[:,2], style, 
#             color=color, label=label, linewidth=linewidth)
#     ax.set_xlabel(x_label)
#     ax.set_ylabel(y_label)
#     ax.set_zlabel(z_label)
#     if axes_equal:
#         set_axes_equal(ax)

if __name__ == "__main__":
    pass