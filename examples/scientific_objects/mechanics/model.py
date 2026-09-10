import numpy as np


def displacement(stiffness, applied_load):
    """Solve the constrained linear-elastic equilibrium system."""
    return np.linalg.solve(stiffness, applied_load)
