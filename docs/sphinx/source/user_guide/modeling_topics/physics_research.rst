Research physics: from photons to useful spacecraft power
=========================================================

The :mod:`orbitalpv.physics` namespace provides executable screening models for
thermal balance, radiation exposure, spectral photocurrent, array circuits and
electrical power systems. Every method has explicit units and physical bounds.
These implementations are inspired by the literature below; they are not exact
paper reproductions, manufacturer-qualified component models or flight-qualified
design tools.

Transient thermal balance
-------------------------

``ThermalSurface`` and ``simulate_panel_thermal`` integrate a lumped surface:

.. math::

   C\frac{dT}{dt} = A[\alpha(G_{sun}+G_{albedo})+\epsilon G_{IR}]
   + Q_{internal} - P_{PV} - \epsilon\sigma A_{rad}(T^4-T_{sink}^4)
   - K(T-T_{bus}).

Input fluxes must already contain projection and view factors. Earth infrared
heats the surface but does not enter the photovoltaic irradiance. The emitting
area can include two panel faces while the receiving area refers to the supplied
incident flux. Electrical extraction cools the panel; electrical energy later
dissipated by a payload must enter the payload's own thermal balance.

Radiative and conductive rejection are implicit; temperature-dependent PV
efficiency is evaluated at each substep's initial temperature. This avoids the
unstable explicit ``T**4`` update without pretending to solve a finite-element
spacecraft model. Reduce ``max_step_s`` and compare results when fast eclipse
transitions matter. Interval input, extracted, rejected and stored energies are
returned together with their conservation residual.

.. code-block:: python

   import numpy as np
   from orbitalpv import physics as opv

   time_s = np.arange(0, 5401, 60)
   irradiance = np.where(time_s < 3240, 1100.0, 0.0)
   thermal = opv.simulate_panel_thermal(
       time_s, irradiance,
       surface=opv.ThermalSurface(heat_capacity_j_k=12000),
       earth_ir_w_m2=150, pv_efficiency=0.3,
   )

``analysis/flight_thermal_validation/run.py`` accepts a CSV with time, projected
solar irradiance and observed temperature. **Its default run is an independent
analytic dark-cooling benchmark, not a flight validation result.** Supplying
telemetry does not remove the need to identify surface properties and align
sensor timestamps. The CSV contents are hashed in the output summary.

Radiation exposure and remaining power
--------------------------------------

``radiation_equivalent_fluence`` integrates a supplied differential particle
fluence spectrum against material-specific NIEL, the non-ionizing energy loss:

.. math::

   D_{DDD} = \int \phi(E)\,\tau(E)\,NIEL(E)\,dE,
   \qquad \Phi_{eq}=D_{DDD}/NIEL_{reference}.

The input units are MeV, particles/(cm² MeV), and MeV cm²/g, giving displacement
damage in MeV/g. The reference NIEL is required explicitly. Particle species and
material/reference normalization must agree before exposures are combined.
An input attenuation curve is not a full shielding simulation: it omits energy
redistribution, secondary particles and angular transport. Prefer an externally
transported spectrum when these effects matter.

``RadiationResponse`` requires calibrated parameters for
``R = 1 - C log10(1 + equivalent_fluence / reference_fluence)``.
``retained_power_fraction`` bounds the result between the declared floor and one.
It excludes annealing and perovskite healing; a fit outside its measured fluence
range is an extrapolation. The EOL analysis illustrates how a retained-power
factor and declared optical changes can affect thermal/electrical output.
Its dose, NIEL and optical changes are clearly labeled sensitivity assumptions.

Spectral photocurrent and tandem matching
-----------------------------------------

``spectral_photocurrent_density`` evaluates

.. math::

   J_{ph}=\frac{q}{hc}\int \lambda E_\lambda EQE(\lambda)\,d\lambda.

Wavelength is supplied in nm, irradiance in W/m²/nm, and the returned current
density is A/m². The wavelength grid must be increasing and EQE must be between
zero and one. Arrays may have leading dimensions for several spectra/devices.

``tandem_current_density`` takes subcell EQEs referenced to the same incident
light, enforces wavelength-wise photon conservation, and returns the minimum
subcell current for an equal-area series stack. Independent standalone subcell
EQEs cannot simply be stacked because that double counts absorbed photons.
The reported mismatch is a current-utilization metric. Voltage, fill factor,
radiative coupling and device efficiency require additional models.

The spectral analysis accepts a measured spectrum CSV. Its default is a
blackbody-shaped **synthetic spectrum**, normalized over its declared wavelength
range; it is not an ASTM or measured AM0 reference. Its EQE windows are illustrative.

Array topology and faults
-------------------------

``PVSubstring`` represents a generating diode branch, series resistance and an
optional bypass diode. ``array_iv_curve`` combines series substring voltages and
parallel string currents. A constant-drop bypass approximation and ideal string
blocking are used. No shunt leakage, hot spots, reverse breakdown, arcing or
thermal failure propagation is implied.

The ``open`` state opens the generating branch. If its bypass remains connected,
other substrings may still deliver current. Use ``bypass_voltage_v=None`` for an
unbypassed open circuit. The ``short`` state shorts the whole substring. Returned
MPP values are maxima on the sampled voltage grid; refine that grid as needed.

The fault gallery and analysis construct scenarios explicitly. Their curves are
not labels inferred from spacecraft observations.

Battery dispatch and compute scheduling
---------------------------------------

``dispatch_power`` conserves bus power and stored energy, applies charge/discharge
efficiencies and power limits, and exposes curtailment and unmet load. The time
array contains **N+1 interval boundaries**, while each power array has **N values**.
Nominal capacity is Wh; SOC and its bounds are fractions; bus powers are W.

``schedule_compute_workload`` adds released tasks, deadlines and per-task power
limits. A deterministic earliest-deadline heuristic prefers solar surplus and
uses storage for mandatory near-deadline work. It returns both dispatch and task
completion tables, including missed energy. Releases and deadlines must align
with interval boundaries. This is not an optimal mixed-integer scheduler.

``radiator_feasibility`` provides a steady net-radiation bound at a specified
radiator temperature, area and absorbed environmental heat flux. There is no
convective cooling in this vacuum model. Heat transport, junction temperature,
transients, radiator mass and failure tolerance require additional design work.
Its bound can cap delivered bus load in the scheduler; battery/converter heat
must be accounted for separately when closing a complete spacecraft heat budget.

``rainflow_cycles`` returns full and residual half cycles from an SOC trace.
``battery_cycle_damage`` evaluates a declared cycle-depth/Miner relation with a
required full-depth life calibration. The result is **damage**, not remaining
capacity. Calendar aging, C-rate and temperature effects are not included.

Reproducible analyses
---------------------

After installing the repository, execute any analysis from its root::

   python analysis/flight_thermal_validation/run.py
   python analysis/radiation_eol_tradeoffs/run.py
   python analysis/array_fault_signatures/run.py
   python analysis/spectral_cell_comparison/run.py
   python analysis/orbital_compute_dispatch/run.py

Each produces CSV results and a JSON summary under ``outputs/``. The checked-in
``reference_results.json`` files record an actual default execution. They are
reproducibility snapshots, not independent observational validation. Optional
telemetry/spectrum inputs are described in each directory's README.

Validation includes independent analytic cooling and spectral integrals, energy
and power conservation, series/parallel circuit scaling, bypass behavior,
zero-exposure and shielding limits, SOC bounds, rainflow examples and task
deadline handling. Model validation against qualified component measurements
and multiple spacecraft remains necessary.

Research provenance
--------------------

* Xie and Li (2026), coupled optical/thermal/electrical degradation framework:
  `10.1016/j.renene.2026.125716 <https://doi.org/10.1016/j.renene.2026.125716>`_.
* Xie and Li (2026), telemetry-driven physics-informed thermal/electrical prediction:
  `10.1016/j.ast.2026.112268 <https://doi.org/10.1016/j.ast.2026.112268>`_.
* Zhang et al. (2026), environmental damage and spacecraft array configurations:
  `10.1016/j.ast.2026.112139 <https://doi.org/10.1016/j.ast.2026.112139>`_.
* Kim et al. (2026), perovskite/silicon tandem design for satellites:
  `10.1038/s44172-026-00813-2 <https://doi.org/10.1038/s44172-026-00813-2>`_.
* Razmi et al. (2026), scheduling computing/harvesting for battery lifetime:
  `10.1109/ACCESS.2026.3656399 <https://doi.org/10.1109/ACCESS.2026.3656399>`_.
* Yaqoob and Huang (2026), mission-constrained EPS sizing:
  `10.1016/j.asr.2026.06.093 <https://doi.org/10.1016/j.asr.2026.06.093>`_.
* Turyshev (2026), orbital data-center power/thermal/communication constraints,
  **preprint**: `arXiv:2604.27197 <https://arxiv.org/abs/2604.27197>`_.

The repository implementations are independently written reduced-order models.
No external paper's supplementary software is vendored by this addition.
