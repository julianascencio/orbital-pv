"""
La Palma and El Hierro through ALISIO-1's infrared camera
=========================================================

DRAGO-2 photographed these islands from orbit. The IAC released the two
false-colour composites in February 2024. In the provider's interpretation,
reddish areas indicate relatively wetter terrain. The colours support a
qualitative comparison. Measuring water content would require calibrated
bands and a retrieval model.

Image credit: IACTEC-Espacio, Instituto de Astrofísica de Canarias (IAC).
See the `original media collection <https://cloud.iac.es/index.php/s/RS9pKNp272N5LEL>`_
and the `IAC image usage terms <https://www.iac.es/en/outreach/multimedia-gallery>`_.
"""

from io import BytesIO

import matplotlib.pyplot as plt

import orbitalpv as opv

# %%
# Display the two original PNGs shipped with OrbitalPV. The connector checks
# each file's SHA-256 before decoding. Each panel uses its own image frame.

fig, axes = plt.subplots(1, 2, figsize=(9, 5.8), layout="constrained")
for ax, scene_id in zip(axes, ("la-palma", "el-hierro"), strict=True):
    scene = opv.AlisioConnector.scenes[scene_id]
    pixels = plt.imread(BytesIO(opv.AlisioConnector.bundled_image(scene_id)), format="png")
    ax.imshow(pixels)
    ax.set_title(scene.title)
    ax.set_axis_off()
    print(f"{scene.title}: {pixels.shape[1]} x {pixels.shape[0]} pixels | SHA-256 {scene.sha256}")

fig.suptitle("ALISIO-1 · Canary Islands in short-wave infrared")
fig.supxlabel(f"Image credit: {opv.AlisioConnector.CREDIT}", fontsize=9)

# %%
# To retrieve another original, select its key from the catalogue and call
# the connector with a destination filename. The download records the IAC
# source, image credit, usage terms and checksum beside the file.
#
# .. code-block:: python
#
#     with opv.AlisioConnector() as iac:
#         receipt = iac.download("donana", "data/donana_crop.jpg")
#         print(receipt.sha256)

for key, scene in opv.AlisioConnector.scenes.items():
    print(f"{key:12} {scene.filename:16} {scene.url}")

plt.show()
