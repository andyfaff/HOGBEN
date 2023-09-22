"""Tests for the simulation module"""

import pytest

import numpy as np
from refnx.reflect import SLD, ReflectModel

from refl1d.material import SLD as refl1dSLD

from unittest import mock
from hogben.simulate import SimulateReflectivity


@pytest.fixture(scope="module")
def refnx_structure():
    """Defines a structure describing a simple sample."""
    air = SLD(0, name='Air')
    layer1 = SLD(4, name='Layer 1')(thick=100, rough=2)
    layer2 = SLD(8, name='Layer 2')(thick=150, rough=2)
    substrate = SLD(2.047, name='Substrate')(thick=0, rough=2)

    sample_1 = air | layer1 | layer2 | substrate
    return sample_1


@pytest.fixture(scope="module")
def refnx_model(refnx_structure):
    return ReflectModel(refnx_structure)


def refl1d_structure(refnx_structure):
    # Make a refl1d structure out of the refnx structure
    structure = refl1dSLD(rho=0, name='Air')
    for component in refnx_structure[1:]:
        name, sld = component.name, component.sld.real.value,
        thick, rough = component.thick.value, component.rough.value

        # Add the component in the opposite direction to the refnx definition.
        layer = refl1dSLD(rho=sld, name=name)(thick, rough)
        structure = layer | structure

    return structure



class TestSimulate:
    angle_times = [(0.3, 100, 1000)]  # (Angle, Points, Time)
    scale = 1
    bkg = 1e-6
    dq = 2
    instrument = 'OFFSPEC'
    def test_data_streaming(self, refnx_model):
        """Tests that without an input for the datafile, the correct one is picked up"""
        sim = SimulateReflectivity(refnx_model, self.angle_times, self.instrument)
        simulated_datapoints = sim.simulate()
        np.testing.assert_array_less(np.zeros_like(simulated_datapoints), simulated_datapoints)  # counts

        # Check that the default instrument also works
        sim = SimulateReflectivity(refnx_model, self.angle_times)
        simulated_datapoints = sim.simulate()
        np.testing.assert_array_less(np.zeros_like(simulated_datapoints), simulated_datapoints)  # counts
        _, simulated_datapoints = simulate(self.sample_1, angle_times,
                                           self.scale, self.bkg, self.dq)
        np.testing.assert_array_less(np.zeros(len(simulated_datapoints)),
                                     simulated_datapoints[:, 3])  # counts

    def test_direct_beam_path(self):
        """
        Tests that the `direct_beam_path` function correctly returns the path
        - external or hogben internal, or raises an error if neither exist
        """
        simulation = Simulation(sample_structure, angle_times=self.angle_times,
                                scale=self.scale, bkg=self.bkg, dq=self.dq,
                                inst_or_path=self.instrument, polarised=False)
        pass

    def test_refnx_simulate_model(self):
        """
        Checks that a model reflectivity from refnx generated through
        `hogben.simulate` is always greater than zero.
        """
        sim = Simulation(sample_structure(), self.angle_times, self.scale,
                         self.bkg, self.dq, self.instrument)
        model_1, data_1 = sim.simulate()
        q = data_1[:, 0]
        r_model = sim.reflectivity(q)

        np.testing.assert_array_less(np.zeros(len(r_model)), r_model)


def test_refnx_simulate_data(self):
    """
    Checks that simulated reflectivity data points and simulated neutron
    counts generated through `hogben.simulate` are always greater than
    zero (given a long count time).
    """
    angle_times = [(0.3, 100, 1000)]
    _, simulated_datapoints = simulate(self.sample_1, angle_times,
                                       self.scale, self.bkg, self.dq,
                                       self.ref)

    np.testing.assert_array_less(np.zeros(len(simulated_datapoints)),
                                 simulated_datapoints[:,1])  # reflectivity
    np.testing.assert_array_less(np.zeros(len(simulated_datapoints)),
                                 simulated_datapoints[:, 3])  # counts

@pytest.mark.parametrize('instrument',
                         ('OFFSPEC',
                          'POLREF',
                          'SURF',
                          'INTER'))
def test_simulation_instruments(self, instrument):
    """
    Tests that all of the instruments are able to simulate a model and
    counts data.
    """
    angle_times = [(0.3, 100, 1000)]
    _, simulated_datapoints = simulate(self.sample_1, angle_times,
                                       self.scale, self.bkg, self.dq,
                                       inst_or_path=instrument)
    # reflectivity
    np.testing.assert_array_less(np.zeros(angle_times[0][1]),
                                 simulated_datapoints[:, 1])
    np.all(np.less_equal(np.zeros(angle_times[0][1]),
                                 simulated_datapoints[:, 3]))  # counts

@pytest.mark.parametrize('instrument',
                         ('OFFSPEC',
                         'POLREF'))
def test_simulation_magnetic_instruments(self, instrument):
    """
    Tests that all of the instruments are able to simulate a model and
    counts data.
    """
    angle_times = [(0.3, 100, 1000)]
    _, simulated_datapoints = simulate_magnetic(self.sample_1, angle_times,
                                       self.scale, self.bkg, self.dq,
                                       inst_or_path=instrument)

    for i in range(4):
        # reflectivity
        np.testing.assert_array_less(np.zeros(angle_times[0][1]),
                                     simulated_datapoints[i][:, 1])
        # counts
        np.testing.assert_array_less(np.zeros(angle_times[0][1]),
                                     simulated_datapoints[i][:, 3])

