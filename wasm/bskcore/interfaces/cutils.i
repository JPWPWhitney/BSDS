/* bskcore rung-A module: expose the C astrodynamics utility functions
   (orbitalMotion.c, linearAlgebra.c, rigidBodyKinematics.c) to Python for the
   wasm numeric-fidelity check. Wrappers use sized-array in typemaps from
   swig_conly_data.i plus a small argout typemap for output vectors. */
%module cutils

%include "architecture/utilities/bskException.swg"
%default_bsk_exception();

%{
#include "architecture/utilities/orbitalMotion.h"
#include "architecture/utilities/linearAlgebra.h"
#include "architecture/utilities/rigidBodyKinematics.h"
#include <string.h>
%}

%pythoncode %{
from Basilisk.architecture.swig_common_model import *
%}

%include "swig_conly_data.i"
ARRAYASLIST(double, PyFloat_FromDouble, PyFloat_AsDouble)

/* ---- output-array typemaps: parameter names ending in Out are returned ---- */
%typemap(in, numinputs=0) double BSKOUT[ANY] (double temp[$1_dim0]) {
    memset(temp, 0, sizeof(temp));
    $1 = temp;
}
/* NB: emit tuples, not lists — SWIG 4.2's AppendOutput appends INTO a list
   result, which would flatten the first output vector. */
%typemap(argout) double BSKOUT[ANY] {
    PyObject* tup$argnum = PyTuple_New($1_dim0);
    for (int i = 0; i < $1_dim0; i++) {
        PyTuple_SetItem(tup$argnum, i, PyFloat_FromDouble($1[i]));
    }
    $result = SWIG_AppendOutput($result, tup$argnum);
}
%apply double BSKOUT[ANY] { double rOut[3], double vOut[3], double cOut9[9] };

/* Wrap the element structs + raw C API (pointer args stay opaque; the sized
   wrappers below are the usable entry points). */
%include "architecture/utilities/orbitalMotion.h"

%inline %{
void elem2rv_sized(double mu, ClassicElements *elements,
                   double rOut[3], double vOut[3]) {
    elem2rv(mu, elements, rOut, vOut);
}
void rv2elem_sized(double mu, double rVec[3], double vVec[3],
                   ClassicElements *elements) {
    rv2elem(mu, rVec, vVec, elements);
}
void v3Cross_sized(double v1[3], double v2[3], double rOut[3]) {
    v3Cross(v1, v2, rOut);
}
double v3Norm_sized(double v1[3]) {
    return v3Norm(v1);
}
void MRP2C_sized(double q[3], double cOut9[9]) {
    double C[3][3];
    MRP2C(q, C);
    memcpy(cOut9, &C[0][0], 9 * sizeof(double));
}
void C2MRP_sized(double c9[9], double rOut[3]) {
    double C[3][3];
    memcpy(&C[0][0], c9, 9 * sizeof(double));
    C2MRP(C, rOut);
}
%}

%pythoncode %{
import sys
protectAllClasses(sys.modules[__name__])
%}
