"""Methods used to simulate an experiment """

import os.path
from typing import Optional, Union
from enum import Enum

import importlib_resources
import numpy as np

import refnx.reflect


class SimulateReflectivity:
    """
    A class for simulating experimental reflectivity data from a refnx model.
    It takes a single model or list of models for polarised simulations, and
    can simulate a list of experimental conditions, e.g. different angles for
    different times.

    Attributes:
        sample_model: A refnx model or list of models (if magnetic)
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
                 angle_times: list[tuple],
                 inst_or_path: str = 'OFFSPEC',
                 angle_scale: float = 0.3):

        self.sample_model = sample_model if isinstance(sample_model, list)\
                            else [sample_model]
        self.angle_times = angle_times
        self.inst_or_path = inst_or_path
        self.angle_scale = angle_scale


    def _incident_flux_data(self, polarised: bool=False) -> np.ndarray:
        """
        Returns data loaded from the filepath given by self.inst_or_path,
        or the data from the requested instrument

        Returns:
            An np.ndarray of the wavelength, intensity data
        """
        # Check if the key isn't in the dictionary and check if it is a
        # a local filepath instead

        inst_dict = self.pol_instr_dict if polarised is True\
                    else self.non_pol_instr_dict

        if self.inst_or_path not in inst_dict:
            if os.path.isfile(self.inst_or_path):
                return np.loadtxt(self.inst_or_path, delimiter=',')
            else:
                msg = "Please provide an instrument name or a local filepath"
                raise FileNotFoundError(str(msg))

        path = importlib_resources.files('hogben.data.directbeams').joinpath(
               inst_dict[self.inst_or_path])

        return np.loadtxt(str(path), delimiter=',')

    def simulate(self, spin_states: 'Optional[list[int]]' = None) -> \
            list[tuple[np.ndarray]]:
        """Simulates a measurement of self.sample_model taken at the angles and
        for the durations specified in self.angle_times on the instrument
        specified in self.inst_or_path

        Args:
            spin_states: optional, spin states to simulate if the sample
            is magnetic, options are [0, 1], for up (0) and down (1) defaults
            to None i.e. non-magnetic

        Returns:
            list[tuple[np.ndarray]]: simulated data for the given model in the
            form [(q, r, dr, counts),...] with one entry per spin state
        """
        # Non-polarised case
        simulation = []
        if spin_states is None:
            for angle, points, time in self.angle_times:
                simulated_angle = self._run_experiment(angle, points, time)
                simulation.append(simulated_angle)
            return simulation

        # Simulate each spin state for all conditions and then add them
        simulated_spin_states = []
        for spin_state in spin_states:
            simulation = []
            for angle, points, time in self.angle_times:
                simulated_angle = self._run_experiment(angle, points,
                                                       time, spin_state)
                simulation.append(simulated_angle)

            simulated_spin_states.append(simulation)
        return simulated_spin_states


    def reflectivity(self, q: np.ndarray,
                     spin_state: Optional[int] = None) -> np.ndarray:
        """Calculates the model reflectivity at given `q` points.

        Args:
            q: Q points to calculate reflectance at.
            spin_state: optional, 0, or 1 representing an up or a
            down spin state

        Returns:
            numpy.ndarray: reflectivity for each Q point.

        """
        # If there are no data points, return an empty array.
        if len(q) == 0:
            return np.array([])

        # Calculate the reflectance in either refnx or Refl1D.
        if spin_state is None:
            return self.sample_model[0](q)
        else:
            return self.sample_model[spin_state](q)



    def _run_experiment(self, angle: float, points: int, time: float,
                        spin_state: Optional[int] = None) -> tuple:
        """Simulates a single angle measurement of a given 'model' on the
        instrument set in self.incident_flux_data with the defined spin state,
        unpolarised measurements (the default) have the set to None

        Args:
            angle: angle to simulate.
            points: number of points to use for simulated data.
            time: counting time for simulation.
            spin_state: spin state to simulate if given a magnetic sample.

        Returns:
            tuple: simulated Q, R, dR data and incident neutron counts.
        """
        polarised = True if spin_state else False
        wavelengths, flux, _ = self._incident_flux_data(polarised=polarised).T

        # Scale flux by relative measurement angle squared (assuming both slits
        # scale linearly with angle, this should be correct)
        scaled_flux = flux * pow(angle / self.angle_scale, 2)

        q = 4 * np.pi * np.sin(np.radians(angle)) / wavelengths

        # Bin q's in equally geometrically-spaced bins using flux as weighting
        q_bin_edges = np.geomspace(q[-1], q[0], points + 1)
        flux_binned, _ = np.histogram(q, q_bin_edges, weights=scaled_flux)
        # Calculate the number of incident neutrons for each bin.
        counts_incident = flux_binned * time

        # Get the bin centres.
        q_binned = np.asarray(
            [(q_bin_edges[i] + q_bin_edges[i + 1]) / 2 for i in range(points)])

        r_model = self.reflectivity(q_binned, spin_state)

        # Get the measured reflected count for each bin.
        # r_model accounts for background.
        counts_reflected = np.random.poisson(r_model * counts_incident).astype(
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
