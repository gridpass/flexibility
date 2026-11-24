"""Check a returned solver point against the original unscaled constraints."""
from __future__ import annotations

# Absolute tolerance in the native units of each row/variable; never a
# percentage of site capacity. This is a numerical check, not a meter tolerance.
RESIDUAL_TOL = 1e-5


def solution_residuals(x, bounds, A_eq, b_eq, A_ub, b_ub, integrality=None):
    import numpy as np
    x = np.asarray(x, dtype=float)
    if x.shape != (len(bounds),) or not np.isfinite(x).all():
        return None
    lo = np.asarray([v if v is not None else -np.inf for v, _ in bounds])
    hi = np.asarray([v if v is not None else np.inf for _, v in bounds])
    def maximum(a):
        return float(np.max(a, initial=0))
    with np.errstate(over="ignore", invalid="ignore"):
        residuals = {
            "equality": maximum(np.abs(A_eq @ x - b_eq)),
            "inequality": maximum(A_ub @ x - b_ub),
            "bounds": max(maximum(lo - x), maximum(x - hi)),
            "integrality": 0.0,
        }
        if integrality is not None:
            integers = x[np.asarray(integrality, dtype=bool)]
            residuals["integrality"] = maximum(np.abs(integers - np.rint(integers)))
    if not all(np.isfinite(v) for v in residuals.values()):
        return None
    return residuals


def checked_solution(sol, bounds, A_eq, b_eq, A_ub, b_ub, integrality=None):
    """Reject invalid successful results; don't misclassify as infeasibility."""
    if not sol.success:
        return sol
    from scipy.optimize import OptimizeResult
    import math
    residuals = solution_residuals(sol.x, bounds, A_eq, b_eq, A_ub, b_ub, integrality)
    if (residuals is None or not math.isfinite(sol.fun)
            or max(residuals.values()) > RESIDUAL_TOL):
        return OptimizeResult(success=False, status=4,
                              message="Solver result failed independent numerical residual check")
    return sol
