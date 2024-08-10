"""Methods used to simulate an experiment """

import os.path
import numbers
from typing import Optional

import importlib_resources
import numpy as np

import refnx.reflect



def _check_random_state(seed):
    """Turn `seed` into a RNG

    Parameters
    ----------
    seed : {None, int, `numpy.random.Generator`, `numpy.random.RandomState`}, optional
        If `seed` is None (or `np.random`), the `numpy.random.RandomState`
        singleton is used.
        If `seed` is an int, a ``Generator`` instance is returned, seeded with `seed`.
        If `seed` is already a ``Generator`` or ``RandomState`` instance then
        that instance is used.

    Returns
    -------
    seed : {`numpy.random.Generator`, `numpy.random.RandomState`}
        Random number generator.

    """
    if seed is None or seed is np.random:
        return np.random.mtrand._rand
    if isinstance(seed, (numbers.Integral, np.integer)):
        return np.random.default_rng(seed)
    if isinstance(seed, (np.random.RandomState, np.random.Generator)):
        return seed

    raise ValueError(f"'{seed}' cannot be used to seed a numpy.random.RandomState"
                      " instance")


class SimulateReflectivity:
    """
    A class for simulating experimental reflectivity data from a refnx model.
    It takes a single model, and can simulate a list of experimental
    conditions, e.g. different angles for different times.

    Attributes:
        sample_model: A refnx model
        angle_times: a list of tuples of experimental conditions to simulate,
                    in the order (angle, # of points, time)
        inst_or_path: either the name of an instrument already in HOGBEN, or
                      the path to a direct beam file, defaults to 'OFFSPEC'
        angle_scale: the angle at which the direct beam was taken (so that it
                     can be scaled appropriately), defaults to 0.3
    """

    non_pol_instr_dict = {'OFFSPEC': 'OFFSPEC_non_polarised_old.dat',
                          'SURF': 'SURF_non_polarised.dat',
                          'POLREF': 'POLREF_non_polarised.dat',
                          'INTER': 'INTER_non_polarised.dat'}

    pol_instr_dict = {'OFFSPEC': 'OFFSPEC_polarised_old.dat',
                      'POLREF': 'POLREF_polarised.dat'}

    def __init__(self,
                 sample_model: refnx.reflect.ReflectModel,
                 angle_times: list[tuple] = None,
                 inst_or_path: str = 'OFFSPEC',
                 angle_scale: float = 0.3):
        """
        Initialises the SimulateReflectivity method
        Args:
            sample_model: a refnx model of a sample
            angle_times: list of tuples of the form (angle, #of points
                         to simulate, length of time to simulate)
            inst_or_path: A full path to your direct beam file, or
                          the name of the hogben instrument you want
                          to use
            angle_scale: The angle at which the direct beam file was
                         was taken, and therefore how it should be
                         scaled to other angles. All hogben files
                         are pre-scaled to 0.3 degrees.
        """

        self.sample_model = sample_model
        self.angle_times = angle_times
        self.inst_or_path = inst_or_path
        self.angle_scale = angle_scale

    def _incident_flux_data(self, polarised: bool = False) -> np.ndarray:
        """
        Returns data loaded from the filepath given by self.inst_or_path,
        or the data from the requested instrument

        Returns:
            An np.ndarray of the wavelength, intensity data
        """
        # Check if the key isn't in the dictionary and check if it is a
        # a local filepath instead

        inst_dict = self.pol_instr_dict if polarised is True \
            else self.non_pol_instr_dict

        if self.inst_or_path not in inst_dict:
            if os.path.isfile(self.inst_or_path):
                return np.loadtxt(self.inst_or_path, delimiter=',')
            else:
                msg = 'Please provide an instrument name or a local filepath'
                raise FileNotFoundError(str(msg))

        path = importlib_resources.files('hogben.data.directbeams').joinpath(
            inst_dict[self.inst_or_path])

        return np.loadtxt(str(path), delimiter=',')

    def simulate(
        self,
        polarised: bool = False,
        rng: Optional[np.random.Generator] = None
    ) -> list[np.ndarray]:
        """Simulates a measurement of self.sample_model taken at the angles and
        for the durations specified in self.angle_times on the instrument
        specified in self.inst_or_path

        Args:
            polarised: defines if the measurement is polarised, and is used to
                select the correct instrument direct beam file
            rng: {None or np.random.Generator} random number generator for
                reproducible simulation

        Returns:
            list: simulated data for the given model in the
            form [q, r, dr, counts]
        """
        # Non-polarised case
        simulation = [np.empty(0,), np.empty(0,), np.empty(0,), np.empty(0,)]
        for condition in self.angle_times:
            simulated_angle = self._run_experiment(*condition, polarised, rng=rng)
            for i, item in enumerate(simulated_angle):
                simulation[i] = np.append(simulation[i], item)

        # Mask out zeros and order points so nested sampling will work
        mask = simulation[1] != 0
        simulation = [data[mask] for data in simulation]  # Filter zeroes
        sort_indices = simulation[0].argsort()
        simulation = [data[sort_indices] for data in simulation]  # Sort by q

        return simulation

    def reflectivity(self, q: np.ndarray) -> np.ndarray:
        """Calculates the model reflectivity at given `q` points.

        Args:
            q: Q points to calculate reflectance at.

        Returns:
            numpy.ndarray: reflectivity for each Q point.

        """
        # If there are no data points, return an empty array.
        if len(q) == 0:
            return np.array([])

        return self.sample_model(q)

    def _run_experiment(
        self,
        angle: float,
        points: int,
        time: float,
        polarised: bool = False,
        rng: Optional[np.random.Generator] = None
    ) -> tuple:
        """Simulates a single angle measurement of a given 'model' on the
        instrument set in self.incident_flux_data

        Args:
            angle: angle to simulate.
            points: number of points to use for simulated data.
            time: counting time for simulation.
            polarised: defines if the measurement is polarised, and is used to
                select the correct instrument direct beam file
            rng: {None or np.random.Generator} random number generator for
                reproducible simulation

        Returns:
            tuple: simulated Q, R, dR data and incident neutron counts.
        """
        rng = _check_random_state(rng)
        wavelengths, flux = self._incident_flux_data(polarised=polarised).T

        # Scale flux by relative measurement angle squared (assuming both slits
        # scale linearly with angle, this should be correct)
        scaled_flux = flux * pow(angle / self.angle_scale, 2)

        q = 4 * np.pi * np.sin(np.radians(angle)) / wavelengths

        # Bin q's in equally geometrically-spaced bins using flux as weighting
        q_bin_edges = np.geomspace(q[-1], q[0], points + 1)
        flux_binned, _ = np.histogram(q, q_bin_edges, weights=scaled_flux)
        # Calculate the number of incident neutrons for each bin.
        counts_incident = np.array(flux_binned * time)

        # Get the bin centres.
        q_binned = np.asarray(
            [(q_bin_edges[i] + q_bin_edges[i + 1]) / 2 for i in range(points)])

        r_model = self.reflectivity(q_binned)

        # Get the measured reflected count for each bin.
        # r_model accounts for background.
        counts_reflected = rng.poisson(lam=r_model * counts_incident).astype(
            float)

        # Convert from count space to reflectivity space.
        # Point has zero reflectivity if there is no flux.
        r_noisy = np.divide(counts_reflected, counts_incident,
                            out=np.zeros_like(counts_reflected),
                            where=counts_incident != 0)

        r_error = np.divide(np.sqrt(counts_reflected), counts_incident,
                            out=np.zeros_like(counts_reflected),
                            where=counts_incident != 0)

        return q_binned, r_noisy, r_error, counts_incident
