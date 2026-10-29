.. _nomenclature:

Nomenclature
============

Consistent naming is essential in a multi-domain space-PV model.

Common symbols
--------------

``BOL``
   Beginning of life.

``EOL``
   End of life.

``AM0``
   Air mass zero solar irradiance reference.

``AOI``
   Angle of incidence between the incoming solar direction and panel normal.

``ECI`` / ``GCRS`` / ``TEME``
   Inertial or quasi-inertial reference frames used for orbital state.

``ECEF`` / ``ITRS``
   Earth-fixed reference frames.

``DDD``
   Displacement damage dose.

``NIEL``
   Non-ionizing energy loss.

``EPS``
   Electrical power system.

``MPPT``
   Maximum-power-point tracking.

Naming rules
------------

* Include units in variable names where ambiguity is likely, for example
  ``altitude_m`` or ``power_w``.
* Include reference frames in persistent vector metadata.
* Use UTC-aware timestamps at application boundaries.
* Distinguish measured, expected, available, and operating power.
