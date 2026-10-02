const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {value: '', checked: false, disabled: false,
    classList: {add(){}, remove(){}, contains(){return false;}}, style: {},
    addEventListener(){}, setAttribute(){}, querySelectorAll(){return [];}, focus(){}});
  return elements.get(id);
}
const context = vm.createContext({console, URLSearchParams, setTimeout, clearTimeout,
  requestAnimationFrame(){}, alert(){}, location: {search: '', href: ''},
  window: {location: {origin: 'http://localhost'}, addEventListener(){}},
  document: {getElementById: element, addEventListener(){}, querySelectorAll(){return [];}, cookie: ''},
  XLSX: {utils: {
    aoa_to_sheet(rows){return {rows};}, book_new(){return {sheets: {}};},
    book_append_sheet(book, sheet, name){book.sheets[name] = sheet;}
  }, writeFile(book, name){context.download = {book, name};}}
});
for (const file of ['import_archive.js', 'import_students.js'])
  vm.runInContext(fs.readFileSync(path.join(root, 'app/templates/js', file), 'utf8'), context);
async function main() {
  vm.runInContext(`ACTIVE_CHECKLIST = {version_name:'v1', items:[
    {code:'so_yeu_ly_lich', display_name:'Sơ yếu lý lịch'},
    {code:'can_cuoc_cong_dan', display_name:'Căn cước công dân'}]};`, context);
  element('importArchived').checked = true;
  element('defaultNgayNhan').value = '2026-10-02';
  element('nguoiNhan').value = 'Admin';
  assert.equal(vm.runInContext("ArchiveImport.quantity('', 'Giấy tờ')", context), 0);
  assert.equal(vm.runInContext("ArchiveImport.quantity('003', 'Giấy tờ')", context), 3);
  for (const value of ['-1', '1.5', '1001', 'Có', 'NaN', '1e2'])
    assert.throws(() => vm.runInContext(`ArchiveImport.quantity(${JSON.stringify(value)}, 'Giấy tờ')`, context));
  assert.equal(vm.runInContext("ArchiveImport.date('15/09/2025')", context), '2025-09-15');
  assert.equal(vm.runInContext("ArchiveImport.date('45915')", context), '2025-09-15');
  assert.throws(() => vm.runInContext("ArchiveImport.date('31/02/2025')", context));
  assert.throws(() => vm.runInContext("ArchiveImport.documents({}, {}, ACTIVE_CHECKLIST.items)", context));
  await vm.runInContext('exportTemplate(true)', context);
  assert.equal(context.download.name, 'template_ho_so_luu_tru_sample.xlsx');
  const rows = context.download.book.sheets.Template.rows;
  const headers = rows[0];
  assert(headers.includes('Ngày nhận hồ sơ'));
  assert(headers.includes('Người nhận hồ sơ'));
  assert(headers.includes('SL - Sơ yếu lý lịch [so_yeu_ly_lich]'));
  assert.equal(rows[1][headers.indexOf('SL - Sơ yếu lý lịch [so_yeu_ly_lich]')], 1);
  assert.equal(rows[2][headers.indexOf('SL - Sơ yếu lý lịch [so_yeu_ly_lich]')], 0);
  context.importRow = Object.fromEntries(headers.map((header, index) => [header, rows[1][index]]));
  context.importRow['Mã hồ sơ'] = 'HS-CU-0088';
  context.importRow['Mã số HV'] = '0123456789';
  const payload = await vm.runInContext('makeApplicantPayload(importRow, guessMappings(Object.keys(importRow)))', context);
  assert.equal(payload.ma_ho_so, 'HS-CU-0088');
  assert.equal(payload.ma_so_hv, '0123456789');
  assert.equal(payload.ngay_nhan_hs, '2025-09-15');
  assert.equal(payload.nguoi_nhan_ky_ten, 'Nguyễn Thị Người Nhận');
  assert.equal(payload.docs.length, 2);
  assert.equal(payload.docs[0].so_luong, 1);
  assert.equal(payload.import_archived, true);
  context.importRow['SL - Sơ yếu lý lịch [so_yeu_ly_lich]'] = '1.5';
  await assert.rejects(() => vm.runInContext('makeApplicantPayload(importRow, guessMappings(Object.keys(importRow)))', context));
  element('importArchived').checked = false;
  await vm.runInContext('exportTemplate(false)', context);
  assert.equal(context.download.name, 'template_import_hoc_vien.xlsx');
  assert(!context.download.book.sheets.Template.rows[0].some(header => header.startsWith('SL - ')));
  const plain = await vm.runInContext("makeApplicantPayload(importRow, guessMappings(Object.keys(importRow)))", context);
  assert.equal(plain.docs.length, 0);
  assert.equal(plain.ma_ho_so, 'HS-CU-0088');
  console.log('Historical Excel template, mappings, date/quantity validation and payload checks passed');
}
main().catch(error => {console.error(error); process.exitCode = 1;});
