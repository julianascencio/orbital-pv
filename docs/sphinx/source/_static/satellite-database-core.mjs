export function hasPower(row) {
  return row.pv_power_w != null || Boolean(row.power_ratings_json?.length);
}
export function filterRows(rows, {search = '', category = '', basis = '', powerOnly = false, sort = 'name'} = {}) {
  const query = search.toLocaleLowerCase().trim();
  const selected = rows.filter(row => (!query || JSON.stringify(row).toLocaleLowerCase().includes(query))
    && (!category || (row.component_type || row.mission_type) === category)
    && (!basis || row.power_basis === basis || row.power_ratings_json?.some(rating => rating.basis === basis))
    && (!powerOnly || hasPower(row)));
  return selected.sort((a, b) => sort === 'pv_power_w'
    ? ((b.pv_power_w ?? -1) - (a.pv_power_w ?? -1) || a.name.localeCompare(b.name))
    : a.name.localeCompare(b.name));
}
export function powerText(row) {
  if (row.pv_power_w == null) return row.power_ratings_json?.length ? 'See qualified ratings' : 'Unknown';
  const signs = {lower_bound: '>', upper_bound: '≤', approximate: '≈', reported: ''};
  return `${signs[row.pv_power_qualifier] || ''}${row.pv_power_w.toLocaleString('en-US')} W`;
}
export function csvValue(value) {
  let text = value == null ? '' : typeof value === 'object' ? JSON.stringify(value) : String(value);
  // Protect spreadsheet users from formula injection, including leading whitespace.
  if (/^[\s]*[=+\-@]/.test(text) || /^[\t\r\n]/.test(text)) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}
export function csvExport(rows, fields) {
  return [fields.map(csvValue).join(','), ...rows.map(row => fields.map(key => csvValue(row[key])).join(','))].join('\r\n');
}
export function safeURL(url) {
  try { const parsed = new URL(url); return ['http:', 'https:'].includes(parsed.protocol) ? parsed.href : null; }
  catch { return null; }
}
