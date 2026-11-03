import test from 'node:test';
import assert from 'node:assert/strict';
import {csvExport, csvValue, filterRows, hasPower, powerText, safeURL} from '../../docs/sphinx/source/_static/satellite-database-core.mjs';

const rows = [
  {name:'Unknown', pv_power_w:null, mission_type:'Science', quality_status:'partial'},
  {name:'Mars', pv_power_w:500, pv_power_qualifier:'lower_bound', power_basis:'mission_reference', mission_type:'Science'},
  {name:'Zero', pv_power_w:0, pv_power_qualifier:'reported', mission_type:'Science'},
  {name:'Range', pv_power_w:null, power_ratings_json:[{power_w:100, basis:'EOL'}], mission_type:'Technology'},
];
test('unknown, zero and multiple ratings stay distinct', () => {
  assert.equal(hasPower(rows[0]),false); assert.equal(hasPower(rows[2]),true); assert.equal(hasPower(rows[3]),true);
  assert.equal(powerText(rows[0]),'Unknown'); assert.equal(powerText(rows[2]),'0 W');
  assert.equal(powerText(rows[1]),'>500 W'); assert.equal(powerText(rows[3]),'See qualified ratings');
});
test('combined filters, sorting and empty results', () => {
  assert.equal(filterRows(rows, {powerOnly:true}).length,3);
  assert.equal(filterRows(rows,{basis:'EOL'})[0].name,'Range');
  assert.equal(filterRows(rows,{search:'mar',category:'Science',powerOnly:true})[0].name,'Mars');
  assert.equal(filterRows(rows,{search:'absent'}).length,0);
  assert.equal(filterRows(rows,{sort:'pv_power_w'})[0].name,'Mars');
});
test('CSV preserves qualifiers and escapes formulas, quotes and newlines', () => {
  assert.equal(csvValue(' =HYPERLINK("x")'), '"\' =HYPERLINK(""x"")"');
  assert.equal(csvValue('line\n"quoted"'), '"line\n""quoted"""');
  const csv=csvExport([rows[1]],['name','pv_power_w','pv_power_qualifier']);
  assert.match(csv,/lower_bound/); assert.match(csv,/500/);
});
test('source links permit only HTTP(S)',()=>{
  assert.equal(safeURL('javascript:alert(1)'),null);
  assert.equal(safeURL('data:text/html,unsafe'),null);
  assert.equal(safeURL('https://science.nasa.gov/'),'https://science.nasa.gov/');
});
