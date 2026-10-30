Ground satellite imagery
========================

Retrieve ground imagery and mapped renewable-energy features through Python.
The walkthroughs cover Cestas in France, Rinconada near Rengo in Chile,
and Icor in Tenerife, using the same compact PV mapping utilities.
They retain real Sentinel-2 pixels, native quality information, and raw
OpenStreetMap inputs related to Dunnett et al. (2020). Each site uses
verified local snapshots for offline reproduction.

The image-detection example trains on Cestas and predicts Tenerife and Chile
from multispectral pixels. It reports held-out weak-reference errors openly.
The inventory example groups mapped features, samples historical GHSL classes,
and tests a capacity model against independent records from a withheld country.
