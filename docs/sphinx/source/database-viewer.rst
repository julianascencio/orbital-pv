Satellite PV database
=====================

Explore spacecraft and their power-system components. Select a record for every
available specification, reference condition, source and documented hardware link.
This is an initial research catalogue, not a complete global satellite inventory.

.. raw:: html

   <section id="satellite-db" aria-label="Satellite and component catalogue">
     <div class="db-intro"><span class="db-eyebrow">OrbitalPV · Space power catalogue</span>
       <h2>Solar power, with its evidence.</h2>
       <p>Browse spacecraft and components. BOL, EOL and deep-space conditions stay attached to each rating.
       Unknown capacity stays unknown; spacecraft consumption is separate.</p></div>
     <div class="db-kpis" aria-live="polite">
       <div class="db-kpi"><strong id="kpi-records">—</strong><span>Matching records</span></div>
       <div class="db-kpi"><strong id="kpi-power">—</strong><span>PV ratings documented</span></div>
       <div class="db-kpi"><strong id="kpi-gaps">—</strong><span>PV watts undocumented</span></div>
       <div class="db-kpi"><strong id="kpi-sources">—</strong><span>Supporting sources</span></div>
     </div>
     <div class="db-filters">
       <label>Catalogue<select id="db-table"><option value="satellites">Satellites / spacecraft</option><option value="components">Components</option></select></label>
       <label>Search<input id="db-search" type="search" placeholder="Name, manufacturer, specification…"></label>
       <label>Category<select id="db-category"><option value="">All categories</option></select></label>
       <label>Rating basis<select id="db-basis"><option value="">All conditions</option><option>BOL</option><option>EOL</option><option value="mission_reference">Mission reference</option><option value="unspecified">Unspecified</option></select></label>
       <label>Sort<select id="db-sort"><option value="name">Name</option><option value="pv_power_w">Preferred PV watts ↓</option></select></label>
       <label class="db-check"><input id="db-power" type="checkbox">Has PV wattage evidence</label>
       <button id="db-reset" type="button">Reset filters</button>
     </div>
     <p id="db-status" role="status">Loading catalogue…</p>
     <div class="db-table-wrap" role="region" aria-label="Scrollable catalogue records" tabindex="0">
       <table><thead><tr><th>Name / details</th><th>Category</th><th>Preferred PV output</th><th>Rating basis</th><th>Cell efficiency</th><th>Manufacturer / operator</th><th>Evidence status</th></tr></thead><tbody id="db-body"></tbody></table>
     </div>
     <div class="db-footer"><div><button id="db-prev" type="button" disabled>Previous</button> <span id="db-page">1 / 1</span> <button id="db-next" type="button" disabled>Next</button></div>
       <button id="db-export" type="button" disabled>Export filtered CSV</button></div>
     <div class="db-links"><a id="db-parquet">Download Parquet</a><a id="db-json">Browser JSON</a><a href="_static/satellite-db/manifest.json">Snapshot manifest</a><a href="_static/satellite-db/NOTICE.txt">Attribution</a></div>
     <p><small>Documented ratings can include historical designs, bounds, ranges and conflicting assertions. They are not live telemetry. Efficiency-only cells and batteries are not expected to have an array wattage. No total of unlike PV ratings is shown.</small></p>
     <aside id="record-details" aria-label="Selected record details" hidden></aside>
     <noscript>JavaScript is required for interactive filters. Download <a href="_static/satellite-db/satellites.parquet">satellites.parquet</a> or <a href="_static/satellite-db/components.parquet">components.parquet</a>.</noscript>
   </section>

Use the :doc:`user_guide/modeling_topics/satellite_catalogue` for Python queries,
schema and research rules, or the :doc:`gallery/database/index` for runnable examples.
