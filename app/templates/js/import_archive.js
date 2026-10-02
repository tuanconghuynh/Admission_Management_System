/* Independently testable rules for historical Excel imports. */
const ArchiveImport = (() => {
  function quantity(value, label) {
    const raw = String(value ?? '').trim();
    if (!raw) return 0;
    if (!/^\d+$/.test(raw) || !Number.isSafeInteger(Number(raw)) || Number(raw) > 1000)
      throw new Error(`${label}: số lượng phải là số nguyên 0–1000 (ô trống = chưa nộp).`);
    return Number(raw);
  }
  function date(value) {
    const raw = String(value ?? '').trim();
    if (!raw) return '';
    let iso;
    if (/^\d+(\.\d+)?$/.test(raw)) {
      const serial = Number(raw);
      if (serial < 1 || serial > 2958465) throw new Error('Ngày nhận hồ sơ không hợp lệ.');
      iso = new Date(Date.UTC(1899, 11, 30) + Math.floor(serial) * 86400000).toISOString().slice(0, 10);
    } else {
      const match = raw.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$/);
      iso = match ? `${match[3]}-${match[2].padStart(2,'0')}-${match[1].padStart(2,'0')}` : raw;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) throw new Error('Ngày nhận hồ sơ phải là dd/MM/yyyy hoặc yyyy-MM-dd.');
    const parsed = new Date(iso + 'T00:00:00Z');
    if (Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== iso)
      throw new Error('Ngày nhận hồ sơ không tồn tại.');
    return iso;
  }
  function documents(row, mapping, items) {
    if (!items?.length) throw new Error('Chưa tải được danh mục giấy tờ. Vui lòng tải lại trang.');
    if (!items.some(item => mapping[`doc:${item.code}`])) throw new Error('Chọn ít nhất một cột số lượng giấy tờ.');
    return items.map(item => ({code: item.code,
      so_luong: quantity(mapping[`doc:${item.code}`] ? row[mapping[`doc:${item.code}`]] : '', item.display_name || item.code)}));
  }
  return {quantity, date, documents};
})();
