Frequently Asked Questions
==========================

Is OrbitalPV a replacement for pvlib?
-------------------------------------

No. OrbitalPV reuses pvlib equations where they are appropriate and adds the
spacecraft-specific geometry, environment, telemetry, degradation, and
mission context needed around them.

Why not use terrestrial ModelChain directly?
--------------------------------------------

A spacecraft does not have terrestrial atmosphere, weather, or conventional
plane-of-array assumptions. OrbitalPV computes AM0, eclipse, attitude, AOI,
thermal state, and degradation explicitly before calling reusable PV
equations.

Why are orbit vectors not stored as PostGIS geometry?
-----------------------------------------------------

Inertial scientific vectors are time- and frame-dependent. They are stored as
scientific state. Only derived Earth-fixed longitude/latitude products belong
in normal GIS geometry.

Does the project already model radiation degradation?
----------------------------------------------------

Not end to end. The architecture and literature roadmap are in place, while
the current implemented environment package is still a foundation layer.

Which open telemetry dataset should I start with?
------------------------------------------------

BIRDS EPS is the current recommended first benchmark because it contains open
panel/battery voltage, current, and temperature data and includes known panel
failures on some spacecraft.
