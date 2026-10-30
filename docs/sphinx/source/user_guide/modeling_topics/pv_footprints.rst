PV footprints, farm grouping and capacity
=========================================

The ground workflow has two sources of geometry: polygons predicted from
multispectral imagery, and features already mapped in OpenStreetMap (OSM).
Both can describe a new location outside the Dunnett et al. (2020) inventory.
Keep their origins separate when evaluating predictions or reporting area.

Install the repository with ``ground,examples`` extras. The ground extra
includes Rasterio, Shapely, PyProj, SciPy and scikit-learn; these packages are
loaded when their methods are called, rather than on a base import.

Image-based footprints
----------------------

``build_pv_features`` explicitly calibrates the blue, green, red, near-infrared,
and two shortwave-infrared bands using each asset's scale and offset. It
constructs spectral indices on the red band's native grid. The 20 m SWIR
bands are resampled with bilinear interpolation and scene classification
(SCL) with nearest-neighbour interpolation; the source crops remain unchanged.
Resampling does not create finer spatial information.

``PVFootprintModel.fit`` fits a deterministic random forest to labelled pixels.
There are no globally validated pretrained weights hidden inside the API.
Inference receives spectral features and georeferencing only; it never reads
the target site's OSM boundaries or a list of plants in the paper.

.. code-block:: python

   import orbitalpv as opv

   training = opv.prepare_pv_training_sample(
       cestas, background_is_negative=True, boundary_buffer_m=20,
   )
   model = opv.PVFootprintModel.fit([training], random_state=0)
   features = opv.build_pv_features(new_site.images)
   prediction = model.predict(features, threshold=0.5, min_area_m2=1000)
   opv.plot_pv_detection(new_site, prediction)

The names ``cestas`` and ``new_site`` above are ``PVSite`` objects loaded with
the six spectral assets and ``scl`` (plus ``visual`` for plotting). The
training adapter accepts mapped photovoltaic generator polygons; a plant
perimeter alone is not a panel label. For independently reviewed annotations,
use ``rasterize_pv_labels`` and ``PVTrainingSample`` directly.

``background_is_negative=True`` is an explicit weak-label assumption: pixels
outside the mapped arrays are treated as background. Unmapped arrays can make
that assumption wrong. A buffer excludes uncertain pixels immediately outside
the mapped boundaries from training and evaluation. The default without this
opt-in leaves unlabelled pixels unknown.

Model scores are random-forest class probabilities, not a calibrated estimate
of certainty that a PV plant exists. A threshold creates a mask and a minimum
connected-component area removes small candidate regions. Exported GeoJSON
retains the scene, method and area provenance. Its polygons represent
10 m pixel footprints, not surveyed fence lines or individual modules.

Clouds, shadows, water, defective pixels and snow are excluded by default.
For floating PV, explicitly choose appropriate ``excluded_scl`` values and
validate that setting; a water mask can otherwise exclude the target itself.
An area with no usable pixels cannot be classified as empty of PV.

Validation on another site
~~~~~~~~~~~~~~~~~~~~~~~~~~

Hold out complete plants or regions. Randomly splitting neighbouring pixels
from one image can substantially overstate transfer to a different site.
``model.evaluate`` checks both site identifiers and geographic overlap against
training areas. It reports precision, recall, F1, intersection-over-union and
the number of scored/unknown pixels. Raw and area-filtered predictions are
distinguished.

The gallery trains on Cestas and predicts Tenerife without supplying Tenerife's
OSM data to inference. It then compares the prediction with a later OSM snapshot.
Those scores measure agreement with weak map labels, not independently surveyed
accuracy. Rinconada is shown as a second transfer case; its OSM plant perimeter
includes non-panel land and is not used as panel-level ground truth.

The spectral random forest is an inspectable baseline. Different soils, array
technologies, clouds, seasons, sensor products and map completeness can change
its performance. It requires local evaluation before operational use. The
published Sentinel-2 PV classification work cited below motivates the feature
approach; the example is not a reproduction of that study's trained model.

Farm inventories from mapped features
-------------------------------------

``osm_pv_features`` converts supported OSM geometries with their source IDs and
photovoltaic tags. ``cluster_pv_farms`` groups nearby features and retains
singleton installations. Duplicate representations and overlapping polygons
must not create duplicate area. Generator/panel-group area, whole-plant area
and the surrounding farm extent are different quantities.

The Dunnett paper states a 400 m solar grouping distance and two minimum
features. Its archived processing script applies 400 m to remaining points
and twice that distance to polygon centroids. The implementation documents
that distinction and exposes the distances explicitly. The current OSM
snapshot and stricter geometry provenance are not the original 2020 inventory.

Historical settlement context
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``GHSLSettlementConnector`` retrieves the Joint Research Centre's GHS-SMOD
settlement classes and crops them on their native 1 km Mollweide grid. Sampling
distinguishes urban, rural, water and unknown values. Unknown or out-of-coverage
cells are not silently treated as rural.

The runnable example uses **epoch 2015, release R2023A**. This is a later
reprocessing of historical settlement data. It is explicitly different from
the **R2019A** product used by the paper, whose original download is no longer
available at its former public URL. The connector also supports a supplied
local R2019A raster for analyses that have retained that edition. A 2015
settlement label does not establish land use at the satellite acquisition date.

Capacity calibration
--------------------

Capacity estimates require independent reference capacities and a consistent
area definition. The calibration API fits coefficients from supplied records;
it does not assume a universal MW-per-hectare conversion. The paper's solar
model uses non-urban installations with an OSM polygon-area proxy greater than
one hectare. Its predictor is not guaranteed to be physical module area.

The gallery uses the authors' original anonymised ``wiki_solar_join.csv``
from Figshare version 2. It withholds Spain when fitting and reports error
against those withheld capacity records. The source labels are reported MW
without a declared AC/DC basis, so outputs retain that limitation. Applying a
model fitted on OSM polygon areas directly to pixel-segmented module footprints
would change the predictor definition and requires new calibration.

Uncertainty and validity restrictions accompany estimates. Urban/unknown
settlement classes, insufficient area, absent geometry and predictor values
outside the calibration range must remain visible in exported results.
Reported nameplate capacity, estimated nameplate capacity and measured power
generation are separate quantities.

Reproduce and export
--------------------

The analysis entry point in ``analysis/ground_pv_mapping/run.py`` consumes the
same bundled source snapshots as the gallery and writes predictions, metrics,
model metadata and farm inventories into a chosen output directory. It does
not overwrite the inputs. The image model can be saved and loaded as JSON;
loading does not execute pickled Python objects.

References
----------

* Dunnett, S. et al. (2020), `Harmonised global datasets of wind and solar farm
  locations and power <https://doi.org/10.1038/s41597-020-0469-8>`_.
* Dunnett, S. (2020), `Original data and processing scripts, version 2
  <https://doi.org/10.6084/m9.figshare.11310269.v2>`_.
* `A 10-m national-scale map of ground-mounted photovoltaic power stations in
  China of 2020 <https://pmc.ncbi.nlm.nih.gov/articles/PMC10864270/>`_, Scientific
  Data (2024), and the `authors' classification code
  <https://github.com/MrSuperNiu/PV_ScientificData_Classification_Code>`_.
* European Commission Joint Research Centre, `GHS-SMOD R2023A
  <https://human-settlement.emergency.copernicus.eu/ghs_smod2023.php>`_.
* scikit-learn, `RandomForestClassifier
  <https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html>`_.
