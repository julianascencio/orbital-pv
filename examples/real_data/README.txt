Real on-orbit data
==================

These examples retrieve and analyze public spacecraft telemetry rather than
synthetic data.

The BIRDS workflow uses measured solar-panel voltage, current and temperature
from four 1U CubeSats: RAAVANA, UGUISU, NEPALISAT and TSURU. The source
workbooks contain **48 flight campaigns, 31,725 measurement times and 158,625
panel observations**. Each measurement time is counted within its spacecraft
and campaign and contains five panel observations.

The walkthrough retains its original RAAVANA example address and includes:

* an overview of all four spacecraft and their measurement coverage;
* full-resolution plots of RAAVANA's two approximately 90-minute campaigns,
  containing 1,079 and 1,080 measurements at five-second intervals;
* five-minute power envelopes within each recorded campaign;
* TSURU's longer history of 40 flight campaigns.

TSURU's two undated test sheets, ``Test1 w batt`` and ``Test2 wo batt``, are
excluded. Its yearless March--December sheets use an explicitly inferred
``campaign_year=2021``, followed by the sheets explicitly dated January 2022.
This inference is consistent with TSURU's 14 March 2021 deployment. The
normalized timestamps are campaign-date anchors plus recorded elapsed
seconds; the actual UTC session start is unknown. The example does not
interpolate measurements across campaign gaps or claim precise UTC timing.

The dataset is published by Jara and Lepcha (2022), DOI
`10.17632/8kp25ycf63.1 <https://data.mendeley.com/datasets/8kp25ycf63/1>`_,
under CC BY 4.0. Counts refer to the `official source workbooks
<https://github.com/BIRDSOpenSource/EPS_dataset/tree/67ad4435c5329abde65afc16e30d725cd5f2653c>`_;
the `associated article <https://pmc.ncbi.nlm.nih.gov/articles/PMC9679683/>`_
describes the instrumentation and collection method.

Install the workbook reader and plotting dependencies with
``pip install -U "orbital-pv[excel,examples]>=0.4.2"``. The first run downloads the
upstream workbooks and requires network access; subsequent runs reuse the
downloaded files. The public ``opv.fetch_birds_eps`` and
``opv.load_birds_eps_workbook`` helpers both accept ``campaign_year=2021``
for the TSURU yearless campaign names.
