Ground PV research methods
==========================

Compare geographically held-out mapping, infer geometry with calibrated
capacity intervals, match dated footprints, and test cloud-motion nowcasts.
Examples say explicitly which inputs are real cached observations and which
are synthetic algorithm scenarios. All calls use the public orbitalpv API.

Install ``orbital-pv[ground-research,examples]``. Native spectral assets and
their scale/offset metadata are unchanged; 20 m SWIR resampling creates no
new spatial observations. Optional gated model checkpoints and authenticated
weather products are never downloaded by the gallery.
