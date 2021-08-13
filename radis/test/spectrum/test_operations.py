# -*- coding: utf-8 -*-
"""
Created on Sun Aug  5 14:26:44 2018

@author: erwan
"""

import numpy as np
import pytest

from radis.los import MergeSlabs, SerialSlabs
from radis.spectrum.compare import get_diff, plot_diff
from radis.spectrum.operations import (
    Radiance,
    Radiance_noslit,
    Transmittance_noslit,
    add_constant,
    crop,
    multiply,
    offset,
    sub_baseline,
)
from radis.test.utils import getTestFile
from radis.tools.database import load_spec


@pytest.mark.fast
def test_crop(verbose=True, *args, **kwargs):
    """Test that update can correctly recompute missing quantities"""

    # 1) A crop example in the same unit as the one stored

    # Work with a Spectrum object that was generated by Specair
    s = load_spec(getTestFile("N2C_specair_380nm.spec"))
    # Focus on N2(C->B), v'=0, v''=2 band:
    s.crop(376, 381, "nm")

    w = s.get_wavelength()
    assert w.min() >= 360
    assert w.max() <= 382

    # 2) A crop example in different unit as the one stored

    # Work with a Spectrum object that was generated by Specair
    s1 = load_spec(getTestFile("CO_Tgas1500K_mole_fraction0.01.spec"), binary=True)
    # Focus on N2(C->B), v'=0, v''=2 band:
    s1.crop(4530, 4533, "nm")

    w = s1.get_wavelength()
    assert w.min() >= 4530
    assert w.max() <= 4533

    return True


@pytest.mark.fast
def test_cut_recombine(verbose=True, *args, **kwargs):
    """
    Use :func:`~radis.spectrum.operations.crop` and :func:`~radis.los.slabs.MergeSlabs`
    to cut a Spectrum and recombine it

    Assert we still get the same spectrum at the end
    """

    s = load_spec(getTestFile("CO_Tgas1500K_mole_fraction0.01.spec"), binary=True)
    # Cut in half
    cut = 2177
    s1 = crop(s, 2000, cut, "cm-1", inplace=False)
    s2 = crop(s, cut, 2300, "cm-1", inplace=False)

    # Recombine
    s_new = MergeSlabs(s1, s2, resample="full", out="transparent")

    # Compare
    assert s.compare_with(s_new, spectra_only=True, plot=False, verbose=verbose)


@pytest.mark.fast
def test_invariants(*args, **kwargs):
    """Ensures adding 0 or multiplying by 1 does not change the spectra"""
    from radis import load_spec
    from radis.test.utils import getTestFile

    s = load_spec(getTestFile("CO_Tgas1500K_mole_fraction0.01.spec"))
    s.update()
    s = Radiance_noslit(s)

    assert s.compare_with(
        add_constant(s, 0, "W/cm2/sr/nm"), plot=False, spectra_only="radiance_noslit"
    )
    assert s.compare_with(multiply(s, 1), plot=False, spectra_only="radiance_noslit")

    assert 3 * s / 3 == s
    assert (1 + s) - 1 == s


@pytest.mark.fast
def test_operations_inplace(verbose=True, *args, **kwargs):

    from radis.spectrum.operations import Radiance_noslit

    s = load_spec(getTestFile("CO_Tgas1500K_mole_fraction0.01.spec"), binary=True)
    s.update("radiance_noslit", verbose=False)
    s = Radiance_noslit(s)

    # Add 1, make sure it worked
    I_max = s.get("radiance_noslit")[1].max()
    s += 1
    assert s.get("radiance_noslit")[1].max() == I_max + 1
    if verbose:
        print("test_operations: s += 1: OK")

    # Multiply, make sure it worked
    I_max = s.get("radiance_noslit")[1].max()
    s *= 10
    assert s.get("radiance_noslit")[1].max() == 10 * I_max
    if verbose:
        print("test_operations: s *= 10: OK")


@pytest.mark.fast
def test_serial_operator(verbose=True, plot=False, *args, **kwargs):
    import matplotlib.pyplot as plt

    s = load_spec(getTestFile("CO_Tgas1500K_mole_fraction0.01.spec"))
    s.update()
    s1 = s.rescale_path_length(10, inplace=False)  # make non optically thin
    s2 = s.rescale_path_length(20, inplace=False)  # make non optically thin
    s3 = s.rescale_path_length(30, inplace=False)  # make non optically thin
    if plot:
        #        s.plot('radiance_noslit', lw=2, nfig='Line of sight (SerialSlabs): s > s > s')
        plt.figure("test_serial_operator").clear()
        SerialSlabs(s1, s2, s3).apply_slit(1).plot(nfig="same")
        ((s1 > s2) > s3).apply_slit(1).plot(nfig="same")
    assert SerialSlabs(s1, s2, s3).compare_with(
        (s1 > s2) > s3, spectra_only=True, plot=False
    )
    assert (s1 > (s2 > s3)) == ((s1 > s2) > s3)
    # Forbidden syntax:
    with pytest.raises(ArithmeticError):
        assert SerialSlabs(s1, s2, s3).compare_with(
            s1 > s2 > s3, spectra_only=True, plot=False
        )


@pytest.mark.fast
def test_multiplyAndAddition(verbose=True, plot=False, *args, **kwargs):

    s = load_spec(getTestFile("CO_Tgas1500K_mole_fraction0.01.spec"), binary=True)
    s.update("radiance_noslit", verbose=False)
    s.apply_slit(0.1)
    s = Radiance(s)
    assert s.units["radiance"] == "mW/cm2/sr/nm"

    s_bis = add_constant(s, 1, "mW/cm2/sr/nm")
    w, Idiff = get_diff(s_bis, s, "radiance")
    test = Idiff[1] - 1
    assert np.all(test < 1e-10)

    s_ter = multiply(multiply(s, 50), 1 / 50)
    #    plot_diff(s_ter, s_5)
    diff = get_diff(s_ter, s, "radiance")
    ratio = abs(np.trapz(diff[1], x=diff[0]) / s.get_integral("radiance"))
    assert ratio < 1e-10


@pytest.mark.fast
def test_offset(verbose=True, plot=False, *args, **kwargs):

    s = load_spec(getTestFile("CO_Tgas1500K_mole_fraction0.01.spec"), binary=True)
    s.update("radiance_noslit", verbose=False)
    s.apply_slit(0.1)

    s2 = offset(s, 10, "nm", name="offset_10nm")
    if plot:
        plot_diff(s, s2)
    assert np.allclose(s2.get_wavelength(), s.get_wavelength() + 10)
    assert np.allclose(
        s2.get_wavelength(),
        s.get_wavelength() + 10,
    )

    # Test inplace version
    s.offset(10, "nm")
    assert np.allclose(s2.get_wavelength(), s.get_wavelength())


@pytest.mark.fast
def test_other_algebraic_operations(verbose=True, plot=False, *args, **kwargs):

    # An implement of Spectrum Algebra
    # Reload:
    s = load_spec(getTestFile("CO_Tgas1500K_mole_fraction0.01.spec"))
    s.update()

    # Test addition of Spectra
    s.plot(lw=2, nfig="Merge: s//s")
    (s // s).plot(nfig="same")

    # Test substraction of Spectra
    s_tr = Transmittance_noslit(s)
    assert (s_tr - 1.0 * s_tr).get_integral("transmittance_noslit") == 0

    # TODO: add test
    # @EP: the test fails at the moment because multiply only works with radiance,
    # and MergeSlabs only works with non convoluted quantities
    # Do we want that? Up for discussion...

    # There should be an error if algebraic operations are used when
    # multiple quantities are defined:
    with pytest.raises(KeyError):
        2 * s

    s.apply_slit(0.1, "nm")
    s_rad = Radiance(s)

    # Test multiplication with float
    s.plot(lw=2, nfig="Multiplication (by scalar): 2*s", wunit="nm")
    #    (s*s).plot(nfig='same')
    (2 * s_rad).plot(nfig="same", wunit="nm")

    # Test algebraic addition (vs multiplication)
    assert (s_rad + s_rad).compare_with(2 * s_rad, spectra_only="radiance", plot=False)

    # Test algebraic addition with different waveunits
    s_rad_nm = s_rad.resample(s_rad.get_wavelength(), "nm", inplace=False)
    s_sum = 2 * s_rad_nm - s_rad_nm
    s_sum.compare_with(s_rad, spectra_only="radiance", plot=True)
    assert (s_rad_nm + s_rad_nm).compare_with(
        2 * s_rad, spectra_only="radiance", plot=True, rtol=1e-3
    )


@pytest.mark.fast
def test_TestBaseline(plot=False, *args, **kwargs):

    s = load_spec(getTestFile("CO_Tgas1500K_mole_fraction0.01.spec"), binary=True)
    s.update("radiance_noslit", verbose=False)
    s.apply_slit(0.1)
    s = Radiance_noslit(s)
    assert s.units["radiance"] == "mW/cm2/sr/nm"

    s2 = sub_baseline(s, 2e-4, -2e-4)
    if plot:
        plot_diff(s, s2)
    assert s2.get_radiance_noslit()[-1] == s.get_radiance_noslit()[-1] + 2e-4
    assert s2.get_radiance_noslit()[0] == s.get_radiance_noslit()[0] - 2e-4


@pytest.mark.fast
def test_dimensioned_operations(*args, **kwargs):

    import astropy.units as u
    import numpy as np

    from radis import Radiance, load_spec
    from radis.spectrum import sub_baseline
    from radis.test.utils import getTestFile

    # Generate the equivalent of an experimental spectrum
    s = load_spec(getTestFile(r"CO_Tgas1500K_mole_fraction0.01.spec"), binary=True)
    s.update()  # add radiance, etc.
    s.apply_slit(0.5)  # nm
    s = Radiance(s)

    # Test
    assert s.units["radiance"] == "mW/cm2/sr/nm"
    Imax = s.get("radiance", trim_nan=True)[1].max()

    # add a baseline
    s += 0.1 * u.Unit("W/cm2/sr/nm")

    assert np.isclose(s.get("radiance", trim_nan=True)[1].max(), Imax + 100)

    # remove a baseline (we could also have used s=-0.1, but we're testing another function here)
    s = sub_baseline(s, 0.1 * u.Unit("W/cm2/sr/nm"), 0.1 * u.Unit("W/cm2/sr/nm"))

    assert np.isclose(s.get("radiance", trim_nan=True)[1].max(), Imax)

    # Test division
    # Example : a manual normalization
    s /= s.max() * u.Unit("mW/cm2/sr/nm")

    assert s.units["radiance"] == ""  # normalized
    assert s.max() == 1.0

    # Test Multiplication
    # example : a manual Calibration
    s.units["radiance"] = "count"
    s *= 100 * u.Unit("mW/cm2/sr/nm/count")

    assert u.Unit(s.units["radiance"]) == u.Unit(
        "mW/cm2/sr/nm"
    )  # check units are valid
    assert s.units["radiance"] == "mW / (cm2 nm sr)"  # check units have been simplified


def _run_testcases(verbose=True, plot=False, *args, **kwargs):
    """Test procedures"""

    test_crop(verbose=verbose, *args, **kwargs)
    test_cut_recombine(verbose=verbose, *args, **kwargs)
    test_invariants(verbose=verbose, *args, **kwargs)
    test_operations_inplace(verbose=verbose, *args, **kwargs)
    test_serial_operator(verbose=verbose, plot=plot, *args, **kwargs)
    test_multiplyAndAddition(verbose=verbose, plot=plot, *args, **kwargs)
    test_offset(verbose=verbose, plot=plot, *args, **kwargs)
    test_other_algebraic_operations(verbose=verbose, plot=plot, *args, **kwargs)
    test_TestBaseline(verbose=verbose, plot=plot, *args, **kwargs)
    test_dimensioned_operations(*args, **kwargs)

    return True


if __name__ == "__main__":

    _run_testcases(plot=True)
