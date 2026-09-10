from astropy.units import Quantity
from scipy.integrate import trapezoid


def delivered_energy(power_samples, sample_times):
    """Integrate sampled power along the supplied chronological coordinates."""
    return trapezoid(power_samples, x=sample_times)


voltage = Quantity(250, "mV")
current = Quantity(2, "mA")
power = voltage * current
