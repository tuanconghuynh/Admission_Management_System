function escapeImportHtml(value) { return String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch])); }
/*JS code for import_students.html*/
/* ===== Toast (Tailwind) ===== */
function showToast(msg, type='info', ms=4000) {
    const wrap = document.getElementById('toast-wrap');
    if (!wrap) return;
    const color = { success:'bg-green-600', error:'bg-red-600', warn:'bg-amber-600', info:'bg-slate-600' }[type] || 'bg-slate-600';
    const box = document.createElement('div');
    box.className = `${color} text-white text-sm px-4 py-3 rounded-xl shadow-xl ring-1 ring-black/5 transition transform pointer-events-auto`;
    box.style.opacity = '0';
    box.style.translate = '0 -6px';
    box.textContent = msg;
    wrap.appendChild(box);
    requestAnimationFrame(() => { box.style.opacity='1'; box.style.translate='0 0'; });
    box.addEventListener('click', () => dismiss());
    const t = setTimeout(dismiss, ms);
    function dismiss(){
    clearTimeout(t);
    box.style.opacity='0';
    box.style.translate='0 -6px';
    box.addEventListener('transitionend', () => box.remove(), { once:true });
    }
}

/* ===== Sidebar user dropdown ===== */
(function menuSetup(){
    const btn = document.getElementById('userMenuBtn');
    const menu = document.getElementById('userMenu');
    if(!btn || !menu) return;
    function openMenu(on){ 
    if(on) menu.classList.add('show'); else menu.classList.remove('show');
    btn.setAttribute('aria-expanded', String(on)); 
    }
    btn.addEventListener('click', (e)=>{ 
    e.stopPropagation(); 
    openMenu(!menu.classList.contains('show')); 
    });
    document.addEventListener('click', ()=> menu.classList.contains('show') && openMenu(false));
    document.addEventListener('keydown', (e)=>{ if(e.key==='Escape') openMenu(false); });
    document.getElementById('btnMenuLogout')?.addEventListener('click', ()=>{ openMenu(false); openLogout(); });
})();

/* ===== Modal logout (dùng apiFetch) ===== */
(function(){
    const wrap = document.getElementById('logoutModal');
    const box  = document.getElementById('logoutBox');
    const ok   = document.getElementById('lgOK');
    const cxl  = document.getElementById('lgCancel');
    const x    = document.getElementById('lgClose');
    let last=null;
    function open(){ 
    last=document.activeElement; 
    wrap.classList.add('show'); 
    requestAnimationFrame(()=>box.focus()); 
    document.body.classList.add('overflow-hidden'); 
    }
    function close(){ 
    wrap.classList.remove('show'); 
    document.body.classList.remove('overflow-hidden'); 
    last?.focus?.(); 
    }
    function trap(e){
    if(e.key!=='Tab') return;
    const f=box.querySelectorAll('button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])');
    if(!f.length) return;
    const first=f[0], last=f[f.length-1];
    if(e.shiftKey && document.activeElement===first){ e.preventDefault(); last.focus(); }
    else if(!e.shiftKey && document.activeElement===last){ e.preventDefault(); first.focus(); }
    }
    window.openLogout=open;

    // dùng apiFetch bên dưới
    ok.addEventListener('click', async ()=>{ 
    try{ await apiFetch('/logout',{method:'POST'});}catch{} 
    location.href='/auth_login.html'; 
    });
    cxl.addEventListener('click', close); 
    x.addEventListener('click', close);
    wrap.addEventListener('click', e=>{ if(e.target===wrap) close(); });
    box.addEventListener('keydown', trap);
})();

/* ===== Helpers & API base (import logic) ===== */
const $ = id => document.getElementById(id);
const apiBase = () => $("apiBase").value.trim().replace(/\/+$/,'');
const PREFIX_CANDIDATES = ["", "/api"];
let API_PREFIX = "";

(function initApiBase(){
    if (!$("apiBase").value) $("apiBase").value = window.location.origin;
    $("defaultNgayNhan").value = new Date().toISOString().slice(0,10);
})();

async function detectPrefix() {
    for (const p of PREFIX_CANDIDATES) {
    try {
        const r = await fetch(apiBase() + p + "/health", {credentials:"include"});
        if (r.ok) { API_PREFIX = p; return; }
    } catch(_){}
    }
    API_PREFIX = "";
}
const makeUrl = (path) => apiBase() + API_PREFIX + path;

async function apiFetch(path, init = {}){
    const opts = { credentials: "include", ...init };
    let r;
    try { r = await fetch(makeUrl(path), opts); }
    catch(e){ throw new Error("Không kết nối được API: " + e.message); }

    if (r.status === 404) {
    const alt = API_PREFIX === "" ? "/api" : "";
    try {
        const r2 = await fetch(apiBase() + alt + path, opts);
        if (r2.ok) { API_PREFIX = alt; return r2; }
        return r2;
    } catch (e) { throw new Error("Không kết nối được API (alt): " + e.message); }
    }
    return r;
}

/* ===== Log & progress (nguyên khối từ file import cũ) ===== */
let parsedRows = [];
let parsedHeaders = [];
let stopFlag = false;
const results = [];

function translateMessage(msg){
    let s = String(msg || "");
    let code = null;
    const m = s.match(/^HTTP\s+(\d+)\s+(.+)$/i);
    if (m) { code = m[1]; s = m[2]; }

    let lower = s.toLowerCase();
    try {
    const j = JSON.parse(s);
    if (j?.detail) {
        if (typeof j.detail === "string") { s = j.detail; }
        else if (Array.isArray(j.detail)) {
        s = j.detail.map(e => (e.msg || e.message || JSON.stringify(e))).join("; ");
        }
        lower = String(s).toLowerCase();
    }
    } catch (_) {}

    const isMSSV10 =
    /mssv|ma\s*so\s*hv|ma_so_hv/.test(lower) &&
    /10\s*ch[ưư]?̣?\s*s[ốo]|10\s*digits|\b\d{1,9}\b(?!\d)/.test(lower);
    if (isMSSV10) return "⚠️ MSSV phải gồm đúng 10 chữ số!";

    if ((code === '409') || /\b409\b/.test(String(msg))) {
    if (/mssv|ma\s*so\s*hv|ma_so_hv/.test(lower) && /exist|tồn tại/.test(lower)) {
        return "❗ Mã số học viên đã tồn tại!";
    }
    return "❗ Trùng dữ liệu (409)!";
    }

    if (code === '422' || /\b422\b/.test(String(msg))) return "⚠️ Dữ liệu không hợp lệ: " + s;
    if (code === '400' || /\b400\b/.test(String(msg))) return "⚠️ Thiếu trường bắt buộc hoặc sai định dạng!";
    if (code === '500' || /\b500\b/.test(String(msg))) return "💥 Lỗi hệ thống (Internal Server Error)!";
    return s;
}

function badge(type){
    if (type==='OK')   return '<span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-700">THÀNH CÔNG</span>';
    if (type==='SKIP') return '<span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700" title="Thiếu dữ liệu bắt buộc">BỎ QUA</span>';
    return '<span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700">LỖI</span>';
}
function rowClass(type){
    return type==='OK' ? 'bg-green-50/50' : (type==='SKIP' ? 'bg-amber-50/50' : 'bg-red-50/50');
}
function refreshExportButtons(){
    const any = results.length > 0;
    const hasErr = results.some(r => r.type !== 'OK');
    $("btnExportAll").disabled = !any;
    $("btnExportErr").disabled = !hasErr;
}
function renderResults(){
    const tbody = $('resBody');
    const ok   = results.filter(r=>r.type==='OK').length;
    const err  = results.filter(r=>r.type==='ERR').length;
    const skip = results.filter(r=>r.type==='SKIP').length;
    $('okCount').textContent = ok;
    $('errCount').textContent = err;
    $('skipCount').textContent = skip;

    tbody.innerHTML = results.map(r => `
    <tr class="${rowClass(r.type)}">
        <td class="text-center border-b">${r.idx}</td>
        <td class="text-center border-b whitespace-nowrap font-medium">${escapeImportHtml(r.data?.ma_ho_so || '—')}</td>
        <td class="text-center border-b">${badge(r.type)}</td>
        <td class="text-left border-b whitespace-normal break-words">${escapeImportHtml(translateMessage(r.msg || ''))}</td>
        <td class="text-center border-b whitespace-nowrap">${r.type === 'OK' && r.data?.ma_so_hv ? `
            <a class="text-blue-600 hover:underline" target="_blank" rel="noopener" href="${escapeImportHtml(makeUrl('/applicants/' + encodeURIComponent(r.data.ma_so_hv) + '/print'))}">In A4</a>
            · <a class="text-blue-600 hover:underline" target="_blank" rel="noopener" href="${escapeImportHtml(makeUrl('/applicants/' + encodeURIComponent(r.data.ma_so_hv) + '/print-a5'))}">In A5</a>` : '—'}</td>
    </tr>
    `).join('');

    refreshExportButtons();
}
function addResult(type, idx, data, msg){
    results.push({type, idx, data, msg});
    renderResults();
}
$('btnClearLog')?.addEventListener('click', ()=>{ results.splice(0, results.length); renderResults(); });

function setBar(done, total){
    const pct = total ? Math.round(done*100/total) : 0;
    $('bar').style.width = pct + "%";
    $('bar').textContent = pct + "%";
    $('stats').textContent = total ? `Đã gửi ${done}/${total}` : "Chưa chạy.";
}

/* ===== Field defs, mapping, file parsing, preview, date helpers, gender, split name ===== */
const FIELD_DEFS = [
    {key:"ma_ho_so",       label:"Mã hồ sơ",        aliases:["ma ho so","ma_hs","ma_hoso","hoso","code"]},
    {key:"ho_ten", label:"Họ và Tên", aliases:["ho ten", "họ tên", "ho_ten", "fullname"]},
    {key:"ho_dem",         label:"Họ đệm",          aliases:["ho dem","hodem","last name","ho"]},
    {key:"ten",            label:"Tên",             aliases:["ten goi","first name","tên gọi"]},
    {key:"ma_so_hv",       label:"Mã số HV",        aliases:["mshv","ma so","ma hoc vien","ma_hv","mahv","mssv"]},
    {key:"gioi_tinh",      label:"Giới tính",       aliases:["gioi tinh","sex","gender","gt"]},
    {key:"dan_toc",        label:"Dân tộc",         aliases:["dan toc","dantoc","ethnicity","dan-toc"]},
    {key:"ngay_sinh",      label:"Ngày sinh",       aliases:["dob","date of birth","ns","sinh nhat"]},
    {key:"so_dt",          label:"Số ĐT",           aliases:["sdt","so dien thoai","dien thoai","so lien he"]},
    {key:"email_hoc_vien", label:"Email học viên",  aliases:["email","email hoc vien","mail","gmail"]},
    {key:"nganh_nhap_hoc", label:"Ngành nhập học",  aliases:["nganh","nganh hoc"]},
    {key:"dot",            label:"Đợt",             aliases:["dot nhap hoc","dot tuyen"]},
    {key:"khoa",           label:"Khóa",            aliases:["nien khoa","khoa hoc","nk"]},
    {key:"da_tn_truoc_do", label:"Đối tượng TN",    aliases:["doi tuong","doi tuong tn","doi tuong tot nghiep","da tn","trinh do"]},
    {key:"ghi_chu",        label:"Ghi chú",         aliases:["note","ghi chu"]},
    {key:"ngay_nhan_hs", label:"Ngày nhận hồ sơ", aliases:["ngay nhan hs", "ngay nhan", "ngay_nhan_hs"]},
    {key:"nguoi_nhan_ky_ten", label:"Người nhận hồ sơ", aliases:["nguoi nhan", "nguoi tiep nhan", "nguoi_nhan_ky_ten"]},
];
const LABEL_BY_KEY = Object.fromEntries(FIELD_DEFS.map(f=>[f.key,f.label]));
const KEY_BY_LABEL = Object.fromEntries(FIELD_DEFS.map(f=>[f.label,f.key]));
const norm = s => String(s||"").toLowerCase().trim().replace(/\s+/g,' ').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g, 'd');
const archivedImport = () => $('importArchived').checked;
function mappingFields() {
    return archivedImport() ? [...FIELD_DEFS, ...(ACTIVE_CHECKLIST?.items || []).map(item => ({
        key: `doc:${item.code}`, label: `SL - ${item.display_name || item.code} [${item.code}]`,
        aliases: [item.code, item.display_name || item.code, `SL - ${item.display_name || item.code}`, `sl_${item.code}`]
    }))] : FIELD_DEFS.filter(field => !['ngay_nhan_hs', 'nguoi_nhan_ky_ten'].includes(field.key));
}

function guessMappings(headers){
    const hNorm = headers.map(h=>norm(h));
    const map = {};
    mappingFields().forEach(f=>{
    const idxExact = hNorm.findIndex(hn => hn === norm(f.key) || hn === norm(f.label));
    if (idxExact >= 0) { map[f.key] = headers[idxExact]; return; }
    if (f.aliases?.length){
        const idxAli = hNorm.findIndex(hn => f.aliases.some(a=> hn === norm(a)));
        if (idxAli >= 0) { map[f.key] = headers[idxAli]; return; }
    }
    });
    return map;
}
function renderMappingUI(headers) {
    parsedHeaders = headers;
    const container = $('mappings');
    container.innerHTML = "";
    const guess = guessMappings(headers);
    mappingFields().forEach(f => {
    const wrap = document.createElement('div');
    wrap.innerHTML = `
        <label class="text-xs text-gray-600">${escapeImportHtml(f.label)}</label>
        <select class="input mt-1" data-field="${escapeImportHtml(f.key)}">
        <option value="">— Chọn cột —</option>
        ${headers.map(h => `<option ${guess[f.key] === h ? 'selected' : ''}>${escapeImportHtml(h)}</option>`).join("")}
        </select>`;
    container.appendChild(wrap);
    });
}
function getMappingFromUI(){
    const selects = Array.from(document.querySelectorAll('#mappings select'));
    const m = {}; 
    selects.forEach(sel => { if(sel.value) m[sel.dataset.field] = sel.value; });
    return m;
}
$('btnResetMap').onclick = ()=>{ document.querySelectorAll('#mappings select').forEach(s=> s.selectedIndex = 0); };
$('importArchived').addEventListener('change', async () => {
    if (archivedImport() && !ACTIVE_CHECKLIST?.items?.length) await fetchActiveChecklist();
    if (parsedHeaders.length) renderMappingUI(parsedHeaders);
});

function toArrayBuffer(file) {
    return new Promise((res, rej)=>{
    const fr = new FileReader();
    fr.onload = () => res(fr.result);
    fr.onerror = rej;
    fr.readAsArrayBuffer(file);
    });
}
function parseCSV(text){
    const workbook = XLSX.read(text.replace(/^\uFEFF/, ''), {type: 'string', raw: true});
    const records = XLSX.utils.sheet_to_json(workbook.Sheets[workbook.SheetNames[0]], {header: 1, defval: ''});
    const headers = (records[0] || []).map(value => String(value).trim());
    validateHeaders(headers);
    const rows = records.slice(1).filter(record => record.some(value => String(value).trim())).map(record =>
        Object.fromEntries(headers.map((header, index) => [header, String(record[index] ?? '').trim()])));
    return {headers, rows};
}
function validateHeaders(headers) {
    if (!headers.length || headers.some(header => !header) || new Set(headers.map(norm)).size !== headers.length)
        throw new Error('Tên cột phải có nội dung và không trùng nhau. Vui lòng dùng file mẫu.');
}

const dz = $('drop'), fileInput = $('file');
dz.addEventListener("click", ()=> fileInput.click());
["dragenter","dragover"].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add("drag"); }));
["dragleave","drop"].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove("drag"); }));
dz.addEventListener("drop", e => {
    if (e.dataTransfer?.files?.length) { fileInput.files = e.dataTransfer.files; fileInput.dispatchEvent(new Event("change")); }
});

fileInput.addEventListener("change", async (e) => {
    const f = e.target.files[0]; 
    if(!f) return;

    parsedRows = []; 
    parsedHeaders = [];
    $('thead').innerHTML=""; 
    $('tbody').innerHTML="";

    try {
    if (f.name.toLowerCase().endsWith(".csv")) {
        const text = await f.text();
        const {headers, rows} = parseCSV(text);
        parsedRows = rows;
        renderMappingUI(headers); 
        preview(headers, rows);
    } else {
        const buf = await toArrayBuffer(f);
        const wb = XLSX.read(buf, {type:"array"});
        const ws = wb.Sheets[wb.SheetNames[0]];
        const rows = XLSX.utils.sheet_to_json(ws, {header:1, defval:""});
        const headers = (rows[0] || []).map(x => String(x).trim());
        validateHeaders(headers);
        const objs = rows.slice(1)
        .filter(r => r.some(c => String(c).trim() !== ""))
        .map(r => {
            const o = {};
            headers.forEach((h, i) => { o[h] = String(r[i] ?? "").trim(); });
            return o;
        });
        parsedRows = objs; 
        renderMappingUI(headers); 
        preview(headers, objs);
    }
    } catch (err) {
    alert("Không đọc được file: " + err.message);
    }
});

function labelForPreview(h){
    const k = String(h||"").trim();
    return LABEL_BY_KEY[k] || k;
}
function preview(headers, rows) {
  // Hiển thị tiêu đề bảng
  $('thead').innerHTML = `<tr>${headers.map(h => `<th class="text-left">${escapeImportHtml(labelForPreview(h))}</th>`).join("")}</tr>`;

  // Hiển thị tất cả các dòng
  $('tbody').innerHTML = rows.map(r => 
    `<tr>${headers.map(h => `<td>${escapeImportHtml(r[h])}</td>`).join("")}</tr>`
  ).join("");

  // Hiển thị số dòng dữ liệu
  const rowCount = rows.length;
  document.getElementById('dataCount').textContent = `Đã tải lên ${rowCount} dòng dữ liệu`;

  // Gọi hàm điều chỉnh chiều cao cho phép cuộn
  requestAnimationFrame(adjustPreviewHeight);
}

function adjustPreviewHeight() {
  const box = document.getElementById('previewBox');
  if (!box) return;

  box.style.maxHeight = 'none';  // Hủy bỏ chiều cao tối đa cũ

  const thead = document.querySelector('#thead');
  const tbody = document.querySelector('#tbody');
  
  const headerH = thead ? thead.getBoundingClientRect().height : 36;  // Chiều cao tiêu đề
  let rowH = 40;  // Chiều cao mỗi hàng mặc định

  const firstRow = tbody?.querySelector('tr');
  if (firstRow) rowH = firstRow.getBoundingClientRect().height || rowH;  // Lấy chiều cao thực tế của dòng đầu tiên

  const desiredHeight = headerH + rowH * 5 + 8;  // Tính chiều cao tối thiểu để hiển thị 5 dòng
  const maxByViewport = Math.floor(window.innerHeight * 0.7);  // Giới hạn chiều cao theo viewport

  box.style.maxHeight = Math.min(desiredHeight, maxByViewport) + 'px';  // Đảm bảo chiều cao không vượt quá 70% viewport
  box.style.overflowY = 'auto';  // Bật cuộn dọc
  box.style.overflowX = 'auto';  // Bật cuộn ngang
}
window.addEventListener('resize', adjustPreviewHeight);

function excelSerialToISO(n){
    const base = new Date(Date.UTC(1899,11,30));
    base.setUTCDate(base.getUTCDate() + Number(n));
    return base.toISOString().slice(0,10);
}
function parseDateFlexible(v){
    if (v == null) return "";
    const s = String(v).trim();
    if (!s) return "";
    if (/^\d+$/.test(s)) return excelSerialToISO(Number(s));
    let m = s.match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})$/);
    if (m){ const dd=m[1].padStart(2,"0"), mm=m[2].padStart(2,"0"); return `${m[3]}-${mm}-${dd}`; }
    m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return `${m[1]}-${m[2]}-${m[3]}`;
    const d = new Date(s); if (!isNaN(d)) return d.toISOString().slice(0,10);
    return "";
}

function normalizeGender(raw) {
    const s = String(raw || "").trim().toLowerCase();
    if (!s) return null;
    if (["nam","male","m","1"].includes(s)) return "Nam";
    if (["nu","nữ","female","f","0"].includes(s)) return "Nữ";
    return "Khác";
}

function _split_vn(fullname) {
    const s = String(fullname || "").trim().replace(/\s+/g, " ");
    if (!s) return ["", ""];
    const parts = s.split(" ");
    if (parts.length === 1) return ["", parts[0]];
    return [parts.slice(0, -1).join(" "), parts[parts.length - 1]];
}


let ACTIVE_CHECKLIST = null;

async function makeApplicantPayload(src, map){
    const pick = (key, d="") => (map[key] ? String(src[map[key]] ?? "").trim() : d);

    const ho_ten_raw = pick("ho_ten") || [pick("ho_dem"), pick("ten")].filter(Boolean).join(" ").trim();
    const receiptCode = pick("ma_ho_so", "");

    const ngay_nhan_form = $('defaultNgayNhan').value;
    const ngay_nhan_iso = archivedImport() ? ArchiveImport.date(pick('ngay_nhan_hs') || ngay_nhan_form) : (parseDateFlexible(ngay_nhan_form) || ngay_nhan_form);
    const ngay_sinh_iso  = parseDateFlexible(pick("ngay_sinh")) || null;
    const gioi_tinh      = normalizeGender(pick("gioi_tinh")) || null;

    const payload = {
    ngay_nhan_hs: ngay_nhan_iso,
    ho_ten: ho_ten_raw,
    ma_so_hv: pick("ma_so_hv"),
    gioi_tinh,
    dan_toc: pick("dan_toc") || null,
    ngay_sinh: ngay_sinh_iso,
    so_dt: pick("so_dt") || null,
    email_hoc_vien: pick("email_hoc_vien") || null,
    nganh_nhap_hoc: pick("nganh_nhap_hoc") || null,
    dot: pick("dot") || null,
    khoa: pick("khoa") || null,
    da_tn_truoc_do: pick("da_tn_truoc_do") || null,
    ghi_chu: pick("ghi_chu") || null,
    nguoi_nhan_ky_ten: (archivedImport() ? pick('nguoi_nhan_ky_ten') : '') || $('nguoiNhan').value.trim() || null,
    docs: archivedImport() ? ArchiveImport.documents(src, map, ACTIVE_CHECKLIST?.items) : [],
    import_archived: archivedImport(),
    checklist_version_name: ACTIVE_CHECKLIST?.version_name || "v1",
    };

    if (receiptCode) payload.ma_ho_so = receiptCode;
    return payload;
}

function requireMappings(m){
    const hasFull = !!m["ho_ten"];
    const hasSplit = !!m["ho_dem"] && !!m["ten"];
    const need = [];
    if (!(hasFull || hasSplit)) need.push("Họ và Tên (hoặc Họ đệm + Tên)");
    if (!m["ma_so_hv"]) need.push("Mã số HV");
    if (archivedImport() && !ACTIVE_CHECKLIST?.items?.length) need.push('Danh mục giấy tờ (tải lại trang)');
    else if (archivedImport() && !ACTIVE_CHECKLIST.items.some(item => m[`doc:${item.code}`])) need.push('Ít nhất một cột số lượng giấy tờ');
    const chosen = Object.values(m);
    if (new Set(chosen).size !== chosen.length) need.push('Mỗi cột Excel chỉ được gán cho một trường');
    if (need.length){ alert("Thiếu map cột: " + need.join(", ")); return false; }
    return true;
}

$('btnPreview').onclick = async () => {
    if (!parsedRows.length) { showToast('Chưa chọn file dữ liệu.', 'warn'); return; }
    const m = getMappingFromUI();
    if (!requireMappings(m)) return;
    const test = [];
    for (let i=0;i<Math.min(50, parsedRows.length); i++) {
        try {
            const body = await makeApplicantPayload(parsedRows[i], m);
            test.push({'Dòng Excel': i + 2, 'Mã số HV': body.ma_so_hv, 'Họ và Tên': body.ho_ten,
                'Mã hồ sơ': body.ma_ho_so || '', 'Ngày nhận': body.ngay_nhan_hs, 'Người nhận': body.nguoi_nhan_ky_ten,
                ...Object.fromEntries(body.docs.map(doc => [ACTIVE_CHECKLIST.items.find(item => item.code === doc.code)?.display_name || doc.code, doc.so_luong])),
                'Kiểm tra': 'Sẵn sàng gửi; server sẽ kiểm tra trùng'});
        } catch (error) { test.push({'Dòng Excel': i + 2, 'Kiểm tra': error.message}); }
    }
    const headers = [...new Set(test.flatMap(row => Object.keys(row)))];
    preview(headers, test);
    $('dataCount').textContent = `Xem trước ${test.length}/${parsedRows.length} dòng đã chuyển đổi; chưa lưu dữ liệu.`;
};

$('btnUpload').onclick = async ()=> {
    if (parsedRows.length === 0) { alert("Chưa chọn tệp hoặc tệp rỗng"); return; }
    if (!$('defaultNgayNhan').value) { alert("Vui lòng chọn 'Ngày nhận HS (mặc định)' trước khi import."); return; }
    await detectPrefix();
    stopFlag = false; $('btnStop').classList.remove('hidden');
    $('btnUpload').disabled = true;
    showToast('Đang chạy import… vui lòng giữ tab mở.', 'info', 2500);

    const m = getMappingFromUI();
    if (!requireMappings(m)) { $('btnUpload').disabled=false; return; }
    const lockedControls = ['importArchived', 'file', 'defaultNgayNhan', 'apiBase', 'btnResetMap', 'btnPreview', 'btnTemplateEmpty', 'btnTemplateSample'].map($)
        .concat(Array.from(document.querySelectorAll('#mappings select')));
    lockedControls.forEach(control => { if (control) control.disabled = true; });

    const total = parsedRows.length; let done=0;
    setBar(0,total);

    for (let i=0;i<parsedRows.length;i++){
    if (stopFlag) break;
    let body = {ma_so_hv: m.ma_so_hv ? parsedRows[i][m.ma_so_hv] : ''};
    try {
        body = await makeApplicantPayload(parsedRows[i], m);
    } catch (error) {
        done++; setBar(done, total);
        addResult('ERR', i+1, body, error.message);
        continue;
    }
    if (body.ma_ho_so === "") delete body.ma_ho_so;
    if (!body.ho_ten || !body.ma_so_hv){
        done++; setBar(done,total);
        addResult('SKIP', i+1, body, 'Thiếu bắt buộc (Họ và Tên hoặc Họ đệm+Tên) hoặc Mã số HV');
        continue;
    }
    try{
        const r = await apiFetch("/applicants", {
        method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify(body)
        });
        if(!r.ok){
        const t = await r.text();
        addResult('ERR', i+1, body, `HTTP ${r.status} ${t}`);
        } else {
        const j = await r.json();
        if (j?.ma_so_hv) body.ma_so_hv = j.ma_so_hv;
        body.ma_ho_so = j.ma_ho_so || '';
        addResult('OK', i+1, body, `Đã lưu ${body.docs.length ? 'hồ sơ và giấy tờ' : 'học viên'} (MSSV: ${j.ma_so_hv || j.id || body.ma_so_hv}). Có thể in biên nhận từ Danh sách học viên.`);
        }
    }catch(e){
        addResult('ERR', i+1, body, e.message);
    }finally{
        done++; setBar(done,total);
        await new Promise(res=>setTimeout(res, 25));
    }
    }

    const okC   = results.filter(r=>r.type==='OK').length;
    const errC  = results.filter(r=>r.type==='ERR').length;
    const skipC = results.filter(r=>r.type==='SKIP').length;
    const summary = `Xong import: ${okC} thành công • ${errC} lỗi • ${skipC} bỏ qua.`;
    showToast(summary, errC ? (okC ? 'warn' : 'error') : 'success', 7000);

    if (errC > 0) {
    const btnErr = document.getElementById('btnExportErr');
    btnErr?.classList.add('animate-pulse');
    setTimeout(()=> btnErr?.classList.remove('animate-pulse'), 4000);
    }

    document.getElementById('resultsTable')?.scrollIntoView({ behavior:'smooth', block:'start' });
    $('btnStop').classList.add('hidden');
    $('btnUpload').disabled = false;
    lockedControls.forEach(control => { if (control) control.disabled = false; });
};
$('btnStop').onclick = ()=>{ stopFlag = true; };

async function ensureNguoiNhanFromSession(){
    try{
    await detectPrefix();
    const r = await apiFetch("/me");
    if (!r.ok) throw new Error();
    const me = await r.json();
    const name = me.full_name || me.username || "";

    // Gán sidebar/topbar
    (document.getElementById('helloName')||{}).textContent = name || 'Người dùng';
    (document.getElementById('helloRole')||{}).textContent = me.role || '';

    // Gán người nhập
    $('nguoiNhan').value = name;
    $('nguoiNhan').setAttribute("readonly", "readonly");

    if (me.role === "Admin" || me.role === "NhanVien" || me.role === "Manager") {
        $('meStatus').textContent = `Đã gắn tự động: ${name} (${me.role})`;
        $('btnUpload').disabled = false;
        $('btnPreview').disabled = false;
    } else {
        $('meStatus').innerHTML = `Tài khoản <b>${escapeImportHtml(name)}</b> (${me.role}) không có quyền import.`;
        $('btnUpload').disabled = true;
        $('btnPreview').disabled = true;
    }

    if (me.must_change_password) {
        location.href = '/account?first=1';
        return;
    }
    } catch {
    $('nguoiNhan').value = "";
    $('nguoiNhan').setAttribute("readonly", "readonly");
    $('meStatus').innerHTML = 'Chưa đăng nhập. <a class="text-blue-600 hover:underline" href="/auth_login.html">Đăng nhập</a> để gán người nhận.';
    $('btnUpload').disabled = true;
    $('btnPreview').disabled = true;
    }
}

async function fetchActiveChecklist() {
    try {
    await detectPrefix();
    const r = await apiFetch("/checklist/active");
    if (r.ok) {
        ACTIVE_CHECKLIST = await r.json();
    } else {
        ACTIVE_CHECKLIST = { version_name: "v1" };
    }
    } catch {
    ACTIVE_CHECKLIST = { version_name: "v1" };
    }
    $('checklistStatus').textContent = ACTIVE_CHECKLIST?.items?.length
        ? `Danh mục ${ACTIVE_CHECKLIST.version_name}: ${ACTIVE_CHECKLIST.items.length} loại giấy tờ.`
        : 'Chưa có danh mục giấy tờ. Cần tải được danh mục trước khi import hồ sơ lưu trữ.';
}

function isoToVN(iso){
    if (!iso) return "";
    const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})$/);
    return m ? `${m[3]}/${m[2]}/${m[1]}` : String(iso);
}
function anyToVNDate(v){
    if (!v) return "";
    const s = String(v).trim();
    if (/^\d+$/.test(s)) return isoToVN(excelSerialToISO(Number(s)));
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return isoToVN(s);
    return s;
}
function nowTag(){
    const d = new Date();
    const pad = n => String(n).padStart(2,"0");
    return `${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}
function toAoAFull(list) {
    const header = [
        "MaHS","Họ đệm","Tên","MSSV","Giới tính","Dân tộc","Ngày sinh","Số ĐT","Email",
        "Ngành nhập học","Đợt","Khóa","Đối tượng TN","Ngày nhận","Kết quả","Ghi chú kết quả"
    ];
    const aoa = [header];
    for (const r of list){
        const d = r.data || {};
        const label = r.type === 'OK' ? 'THÀNH CÔNG' : (r.type === 'SKIP' ? 'BỎ QUA' : 'LỖI');
        aoa.push([
            d.ma_ho_so || "",
            d.ho_dem || "", // Cột "Họ đệm"
            d.ten || "", // Cột "Tên"
            d.ma_so_hv || "",
            d.gioi_tinh || "",
            d.dan_toc || "",
            anyToVNDate(d.ngay_sinh),
            d.so_dt || "",
            d.email_hoc_vien || "",
            d.nganh_nhap_hoc || "",
            d.dot || "",
            d.khoa || "",
            d.da_tn_truoc_do || "",
            anyToVNDate(d.ngay_nhan_hs),
            label,
            (r.msg ? translateMessage(r.msg) : "")
        ]);
    }
    return aoa;
}

function exportResults(onlyErrors=false){
    const data = onlyErrors ? results.filter(r=>r.type !== 'OK') : results.slice();
    if (!data.length) return;
    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.aoa_to_sheet(toAoAFull(data));
    ws['!cols'] = [
        {wch:12},{wch:28},{wch:12},{wch:12},{wch:12},{wch:12},{wch:18},
        {wch:26},{wch:24},{wch:8},{wch:8},{wch:16},{wch:12},{wch:60},{wch:60}
    ];
    XLSX.utils.book_append_sheet(wb, ws, "KetQuaImport");
    const fname = onlyErrors ? `import_errors_${nowTag()}.xlsx` : `import_result_${nowTag()}.xlsx`;
    XLSX.writeFile(wb, fname);
}

/* ===== Template headers & sample rows cho file mẫu ===== */
function buildTemplateHeaders(){
    return mappingFields().filter(field => field.key !== 'ho_ten').map(field => field.label);
}

function sampleRows(){
    return [
        {
            ma_ho_so:"",ho_dem:"Nguyễn Văn",ten:"A",ma_so_hv:"1234567890",gioi_tinh:"Nam",dan_toc:"Kinh",
            ngay_sinh:"15/01/2005",so_dt:"0901234567",email_hoc_vien:"vana@example.com",
            nganh_nhap_hoc:"Công nghệ thông tin",dot:"1",khoa:"25",da_tn_truoc_do:"THPT",ghi_chu:""
        },
        {
            ma_ho_so:"",ho_dem:"Trần Thị",ten:"B",ma_so_hv:"0987654321",gioi_tinh:"Nữ",dan_toc:"Hoa",
            ngay_sinh:"20/12/2004",so_dt:"0912345678",email_hoc_vien:"tran@example.com",
            nganh_nhap_hoc:"Quản trị kinh doanh",dot:"1",khoa:"25",da_tn_truoc_do:"Cao đẳng",ghi_chu:""
        }
    ];
}

/* ===== Template Excel mẫu ===== */
async function exportTemplate(withSample = false) {
    if (archivedImport() && !ACTIVE_CHECKLIST?.items?.length) await fetchActiveChecklist();
    if (archivedImport() && !ACTIVE_CHECKLIST?.items?.length) {
        showToast('Chưa tải được danh mục giấy tờ để tạo mẫu.', 'error');
        return;
    }
    const headers = buildTemplateHeaders();
    const aoa = [headers];

    if (withSample) {
        const samples = sampleRows();
        for (const row of samples) {
            const line = headers.map(h => {
                const key = mappingFields().find(field => field.label === h)?.key;
                if (key?.startsWith('doc:')) return aoa.length === 1 ? 1 : 0;
                if (key === 'ngay_nhan_hs') return '15/09/2025';
                if (key === 'nguoi_nhan_ky_ten') return 'Nguyễn Thị Người Nhận';
                return key ? (row[key] ?? "") : "";
            });
            aoa.push(line);
        }
    }

    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.aoa_to_sheet(aoa);

    // set width cho cột cho dễ đọc
    ws['!cols'] = [
        {wch:12}, // Mã hồ sơ
        {wch:20}, // Họ đệm
        {wch:12}, // Tên
        {wch:14}, // Mã số HV
        {wch:10}, // Giới tính
        {wch:12}, // Dân tộc
        {wch:12}, // Ngày sinh
        {wch:16}, // Số ĐT
        {wch:26}, // Email học viên
        {wch:24}, // Ngành nhập học
        {wch:8},  // Đợt
        {wch:8},  // Khóa
        {wch:18}, // Đối tượng TN
        {wch:24}  // Ghi chú
    ];

    XLSX.utils.book_append_sheet(wb, ws, "Template");
    if (archivedImport()) {
        ws['!cols'] = headers.map(header => ({wch: header.startsWith('SL - ') ? 30 : 20}));
        const instructions = XLSX.utils.aoa_to_sheet([
            ['HƯỚNG DẪN IMPORT HỒ SƠ ĐÃ LƯU TRỮ'],
            ['Bật Import hồ sơ đã lưu trữ trước khi tải mẫu và khi nhập file.'],
            ['Mỗi học viên một dòng. Giữ Mã số HV, Mã hồ sơ và số điện thoại ở dạng Text để không mất số 0 đầu.'],
            ['Các cột SL: nhập số nguyên 0–1000. Ô trống/0 hoặc cột không gán = chưa nộp.'],
            ['Ngày nhận hồ sơ: dd/MM/yyyy, yyyy-MM-dd hoặc ô ngày Excel. Trống lấy ngày mặc định trên màn hình.'],
            ['Người nhận hồ sơ trống: lấy tên tài khoản đang nhập. Nhật ký vẫn ghi đúng người thực hiện import.'],
            ['Mã hồ sơ cũ được giữ nguyên; bỏ trống để cấp mã ngành + STT khi tiếp nhận. STT riêng theo ngành/khóa/đợt.'],
            ['Học viên/mã hồ sơ trùng sẽ báo lỗi, không cập nhật hoặc ghi đè hồ sơ có sẵn.'],
            ['Danh mục giấy tờ: ' + ACTIVE_CHECKLIST.version_name],
            ['Bấm Xem trước để kiểm tra số lượng, sau đó Bắt đầu import.'],
            ['Sau khi lưu: Danh sách học viên → chọn học viên → in biên nhận A4/A5.']
        ]);
        instructions['!cols'] = [{wch: 110}];
        XLSX.utils.book_append_sheet(wb, instructions, 'HuongDan');
    }

    const fname = archivedImport() ? (withSample ? 'template_ho_so_luu_tru_sample.xlsx' : 'template_ho_so_luu_tru.xlsx') : withSample
        ? "template_import_hoc_vien_sample.xlsx"
        : "template_import_hoc_vien.xlsx";

    XLSX.writeFile(wb, fname);
}

// Gán event cho nút template (nếu có trên trang)
$("btnTemplateEmpty")?.addEventListener("click", () => exportTemplate(false));
$("btnTemplateSample")?.addEventListener("click", () => exportTemplate(true));

// Gán event export kết quả (chỉ 1 lần)
$("btnExportAll").addEventListener("click", () => exportResults(false));
$("btnExportErr").addEventListener("click", () => exportResults(true));

/* ===== Khởi động ===== */
window.addEventListener("load", async () => {
    await ensureNguoiNhanFromSession();
    await fetchActiveChecklist();

    const params = new URLSearchParams(location.search);
    const byQuery = params.get('expired') === '1';
    const byCookie = document.cookie.split(';').some(c => c.trim().startsWith('__session_expired=1'));
    if (byQuery || byCookie) {
        if (typeof showToast === 'function') {
            showToast('Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.', 'warn', 4500);
        } else {
            alert('Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.');
        }
        document.cookie = '__session_expired=; Max-Age=0; Path=/; SameSite=Lax';
    }
});
