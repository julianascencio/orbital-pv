# Classical irradiance nowcasting and weather fusion

```bash
python -m pip install '.[ground-research,examples]'
python analysis/satellite_irradiance_forecasting/run.py \
  --output outputs/satellite_irradiance_forecasting
```

This default is explicitly a **synthetic cloud-transport scenario**. It tests
sign, units, lead times, boundary masking, interpolation and comparison with
clear-sky persistence. Scenario metrics are not operational satellite forecast
skill. The synthetic smoothed weather field is derived from the known scenario
only to illustrate a blend; it is not an independent NWP hindcast.

The public method first estimates global cloud motion by phase correlation,
then optionally refines it with local Lucas-Kanade gradient optical flow.
Frozen retrieved clear-sky index is advected and multiplied by future clear-sky
GHI. Incoming boundaries and missing retrievals remain masked. Clear-sky
persistence refuses to extrapolate an undefined nighttime index into daytime.
Weather fusion uses exponential nowcast weighting, rejects reanalysis as an
operational forecast, and enforces forecast issue time no later than origin.
Metrics compare prediction, observation and persistence on identical valid
support; additional daylight/lead/site stratification is the caller's task.

For real data, `GoesABIConnector` retrieves original public ABI netCDF products,
including downward-shortwave-radiation retrievals where available.
`EumetsatConnector` accesses licensed SEVIRI/MTG products with explicit user
credentials through EUMDAC. Preserve acquisition times, projection, pixel size,
quality flags and product-specific units. Radiances or cloud classes cannot be
passed as irradiance. A physical retrieval or an existing irradiance product,
coincident future clear-sky calculation, and independent surface observations
are required before claiming real irradiance accuracy. Model limitations include
cloud growth, parallax, terrain and uncalibrated retrieval uncertainty.

Outputs: `report.json`, `synthetic_scenario.npz` and `synthetic_nowcast.png`.
The implementation is a transparent baseline; it does not reproduce the
[Baguan-solar preprint](https://arxiv.org/abs/2603.14845), its neural architecture,
training data or reported forecast skill.
