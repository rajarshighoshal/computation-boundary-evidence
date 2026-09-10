# Electrical energy fixture

`power_samples` contains instantaneous electrical power; `sample_times` gives the
corresponding ordered measurement times, which need not be uniformly spaced. Their
integral represents delivered energy, assuming the supplied samples describe the interval.
The separate voltage/current calculation demonstrates explicit unit metadata and power
dimensions. Array units are not inferred from variable names. This is a synthetic fixture.
