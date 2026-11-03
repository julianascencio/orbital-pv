import {csvExport, filterRows, hasPower, powerText, safeURL} from './satellite-database-core.mjs';

const root = document.querySelector('#satellite-db');
if (root) {
  const $ = id => root.querySelector(`#${id}`);
  const base = new URL('_static/satellite-db/', window.location.href);
  let data = [], sources = {}, schema = {}, manifest = {}, page = 0;
  let lastVisible = [];
  let request = 0;
  const pageSize = 20;
  const text = (tag, value, className) => {
    const el = document.createElement(tag); el.textContent = value;
    if (className) el.className = className;
    return el;
  };
  async function fetchVerified(name) {
    const response = await fetch(new URL(name, base));
    if (!response.ok) throw new Error(`${name}: HTTP ${response.status}`);
    const bytes = await response.arrayBuffer();
    if (!crypto.subtle) throw new Error('A secure browser context is required to verify data checksums.');
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    const hex = Array.from(new Uint8Array(digest), x => x.toString(16).padStart(2, '0')).join('');
    if (hex !== manifest.files[name]?.sha256) throw new Error(`Checksum mismatch: ${name}`);
    return JSON.parse(new TextDecoder().decode(bytes));
  }
  function showDetails(row) {
    const trigger = document.activeElement;
    const box = $('record-details'); box.replaceChildren(); box.hidden = false;
    const close = text('button', 'Close details'); close.type = 'button';
    close.onclick = () => { box.hidden = true; if (trigger?.isConnected) trigger.focus(); };
    box.append(close, text('h3', row.name), text('p', row.notes || 'Source specifications; inspect reference conditions.'));
    if (row.pv_power_w != null) box.append(text('p', `${powerText(row)} · ${row.power_basis} · ${row.power_conditions}`));
    for (const rating of row.power_ratings_json || []) {
      box.append(text('p', `${rating.power_w.toLocaleString()} W · ${rating.qualifier} · ${rating.basis} · ${rating.conditions} · source: ${rating.source_id}`));
    }
    box.append(text('h4', 'Sources and evidence'));
    for (const id of row.sources) {
      const source = sources[id]; const item = document.createElement('p');
      const link = text('a', source.title); const url = safeURL(source.url);
      if (url) { link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer'; }
      item.append(link, text('span', ` — ${source.publisher}. Checked ${source.retrieved_at.slice(0, 10)}. `));
      item.append(text('span', `${row.evidence_json[id].locator}: ${row.evidence_json[id].summary}`));
      box.append(item);
    }
    if (row.component_ids?.length) {
      box.append(text('h4', 'Documented components'));
      for (const id of row.component_ids) {
        const link = text('a', `View component ${id.slice(0, 8)}`);
        const url = new URL(window.location.href); url.search = new URLSearchParams({table: 'components', record: id});
        link.href = url.href; box.append(link, document.createElement('br'));
      }
    }
    const table = document.createElement('table'); table.className = 'db-details-table';
    for (const [key, value] of Object.entries(row)) {
      if (value == null) continue;
      const tr = document.createElement('tr');
      tr.append(text('th', key), text('td', typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)));
      table.append(tr);
    }
    box.append(text('h4', 'All fields and provenance'), table);
    box.tabIndex = -1; box.focus({preventScroll: true});
    box.scrollIntoView({behavior: 'smooth', block: 'start'});
  }
  function render() {
    const rows = filterRows(data, {search: $('db-search').value, category: $('db-category').value,
      basis: $('db-basis').value, powerOnly: $('db-power').checked, sort: $('db-sort').value});
    lastVisible = rows;
    const pages = Math.max(1, Math.ceil(rows.length / pageSize)); page = Math.min(page, pages - 1);
    $('kpi-records').textContent = rows.length.toLocaleString();
    $('kpi-power').textContent = rows.filter(hasPower).length.toLocaleString();
    $('kpi-gaps').textContent = rows.filter(row => !hasPower(row)).length.toLocaleString();
    $('kpi-sources').textContent = new Set(rows.flatMap(row => row.sources)).size.toLocaleString();
    const body = $('db-body'); body.replaceChildren();
    for (const row of rows.slice(page * pageSize, (page + 1) * pageSize)) {
      const tr = document.createElement('tr'); const cell = document.createElement('td');
      const button = text('button', row.name, 'db-record-button'); button.type = 'button';
      button.onclick = () => showDetails(row); cell.append(button); tr.append(cell);
      tr.append(text('td', (row.component_type || row.mission_type || 'Unknown').replaceAll('_', ' ')), text('td', powerText(row)),
        text('td', row.power_basis?.replaceAll('_', ' ') || (row.power_ratings_json?.length ? 'Multiple conditions' : '—')),
        text('td', row.cell_efficiency_pct == null ? '—' : `${row.cell_efficiency_pct}%`),
        text('td', row.manufacturer || row.operator || '—'), text('td', row.quality_status.replaceAll('_', ' ')));
      body.append(tr);
    }
    if (!rows.length) { const tr = document.createElement('tr'); const td = text('td', 'No matching records. Clear filters to explore the catalogue.'); td.colSpan = 7; tr.append(td); body.append(tr); }
    $('db-page').textContent = `${page + 1} / ${pages}`;
    $('db-prev').disabled = page === 0; $('db-next').disabled = page >= pages - 1;
    $('db-status').textContent = `${rows.length} of ${data.length} records · checksum-verified snapshot · schema ${manifest.schema_version}`;
  }
  async function loadTable() {
    const token = ++request; $('db-status').textContent = 'Loading and verifying catalogue…';
    $('db-export').disabled = true; $('record-details').hidden = true;
    try {
      const entity = $('db-table').value;
      const rows = await fetchVerified(`${entity}.json`);
      if (token !== request) return;
      data = rows; page = 0; $('db-category').replaceChildren(new Option('All categories', ''));
      for (const category of [...new Set(data.map(r => r.component_type || r.mission_type).filter(Boolean))].sort()) {
        $('db-category').append(new Option(category.replaceAll('_', ' '), category));
      }
      $('db-parquet').href = new URL(`${entity}.parquet`, base).href;
      $('db-json').href = new URL(`${entity}.json`, base).href;
      const url = new URL(window.location.href); url.searchParams.set('table', entity); history.replaceState(null, '', url);
      render(); $('db-export').disabled = false;
      const selected = data.find(row => row.record_id === url.searchParams.get('record'));
      if (selected) showDetails(selected);
    } catch (error) {
      if (token !== request) return;
      data = []; render(); $('db-status').textContent = `Unable to load verified data: ${error.message}`;
    }
  }
  for (const id of ['db-search', 'db-category', 'db-basis', 'db-power', 'db-sort']) {
    $(id).addEventListener(id === 'db-search' ? 'input' : 'change', () => { page = 0; render(); });
  }
  $('db-table').addEventListener('change', loadTable);
  $('db-prev').onclick = () => { page--; render(); }; $('db-next').onclick = () => { page++; render(); };
  $('db-reset').onclick = () => { $('db-search').value = ''; $('db-category').value = ''; $('db-basis').value = ''; $('db-power').checked = false; $('db-sort').value = 'name'; page = 0; render(); };
  $('db-export').onclick = () => {
    const blob = new Blob([csvExport(lastVisible, [...Object.keys(schema.fields), 'source_urls'])], {type: 'text/csv;charset=utf-8'});
    const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url;
    link.download = `orbitalpv-${$('db-table').value}-filtered.csv`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  try {
    const response = await fetch(new URL('manifest.json', base));
    if (!response.ok) throw new Error(`Manifest HTTP ${response.status}`);
    manifest = await response.json();
    [sources, schema] = await Promise.all([fetchVerified('sources.json'), fetchVerified('schema.json')]);
    const entity = new URLSearchParams(window.location.search).get('table');
    if (['satellites', 'components'].includes(entity)) $('db-table').value = entity;
    await loadTable();
  } catch (error) { $('db-status').textContent = `Unable to load catalogue: ${error.message}`; }
}
