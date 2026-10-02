(() => {
  const $ = id => document.getElementById(id);
  let token, objectUrl, endpoint;
  $('close').onclick = () => window.close();
  $('print').onclick = () => {
    try { $('pdf').contentWindow.focus(); $('pdf').contentWindow.print(); }
    catch (_) { $('status').textContent = 'Dùng nút máy in trong khung PDF, sau đó xác nhận khi giấy đã in thành công.'; }
  };
  $('confirm').onclick = async () => {
    $('confirm').disabled = true;
    try {
      const response = await fetch(endpoint, {method:'POST', credentials:'include', headers:{'Content-Type':'application/json'}, body:JSON.stringify({token})});
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'Không lưu được xác nhận');
      $('status').textContent = 'Đã ghi nhận in thành công. Anh có thể đóng cửa sổ này.';
      $('print').disabled = true;
    } catch (e) { $('status').textContent = e.message; $('confirm').disabled = false; }
  };
  async function load() {
    try {
      const source = new URL(new URLSearchParams(location.search).get('source') || '', location.origin);
      const path = source.pathname.replace(/^\/api(?=\/)/, '');
      if (source.origin !== location.origin || !/^\/(?:applicants\/|print\/|batch\/print)/.test(path)) throw new Error('Đường dẫn bản in không hợp lệ');
      const response = await fetch(source, {credentials:'include'});
      token = response.headers.get('X-Print-Token');
      if (!response.ok || !token || !response.headers.get('Content-Type')?.includes('application/pdf')) throw new Error('Không tải được bản in. Hãy đóng cửa sổ và mở lại.');
      objectUrl = URL.createObjectURL(await response.blob());
      $('pdf').src = objectUrl;
      endpoint = location.pathname.startsWith('/api/') ? '/api/print-confirm' : '/print-confirm';
      $('print').disabled = $('confirm').disabled = false;
      $('status').textContent = 'Chỉ xác nhận sau khi đã in ra giấy thành công. Mở xem, hủy in hoặc đóng cửa sổ sẽ không ghi nhật ký in.';
    } catch(e) { $('status').textContent = e.message; }
  }
  window.addEventListener('pagehide', () => { if (objectUrl) URL.revokeObjectURL(objectUrl); });
  load();
})();
