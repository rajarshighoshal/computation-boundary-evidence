# Linear elasticity fixture

`stiffness` maps displacement to force and `applied_load` is the external force vector.
The returned displacement solves static equilibrium. Boundary constraints have already
been incorporated; the remaining stiffness matrix must be square and nonsingular.
This fixture distinguishes the numerical role of a coefficient matrix from its physical
role in the supplied model. It is not a benchmark task or evidence of repair improvement.
