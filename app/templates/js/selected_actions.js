(() => {
  const $ = id => document.getElementById(id);
  let busy = false;
  function selection() { return [...selectedMSHV]; }
  function sync() { for(const id of ['btnEditSelected','btnDeleteSelected']) if($(id))$(id).disabled=busy || !selection().length; }
  document.addEventListener('change', () => queueMicrotask(sync));
  async function responseJson(response) {
    if (!response) throw new Error('Không kết nối được máy chủ');
    const data = await response.json().catch(()=>({}));
    if (!response.ok) throw new Error(typeof data.detail==='string'?data.detail:`Thao tác thất bại (${response.status})`);
    return data;
  }
  $('btnDeleteSelected').onclick = async () => {
    const ids=selection(); if(!ids.length || busy)return;
    const reason=await askDeleteReason(`Xóa tạm ${ids.length} hồ sơ đã chọn? Các hồ sơ vẫn có thể khôi phục từ nhật ký.`, '');
    if(reason===null || !reason.trim())return;
    busy=true;sync();let removed=0;const failures=[];
    try {
      for(const id of ids){
        try {
          const response=await apiFetch('/applicants/'+encodeURIComponent(id),{method:'DELETE',headers:{'Content-Type':'application/json'},body:JSON.stringify({reason})});
          if(!response || response.status!==204) {await responseJson(response);throw new Error('Không xóa được hồ sơ');}
          selectedMSHV.delete(id);removed++;
        } catch(e){failures.push(id+': '+e.message);}
      }
      await runSearch(); updateBulkUI();
      alert(`Đã xóa tạm ${removed}/${ids.length} hồ sơ.`+(failures.length?'\nLỗi:\n'+failures.join('\n'):''));
    } finally {busy=false;sync();}
  };
  $('btnEditSelected').onclick = async () => {
    const ids=selection();if(!ids.length || busy)return;
    const modal=document.createElement('dialog');
    modal.style.cssText='width:min(560px,90vw);border:1px solid #ddd;border-radius:12px;padding:24px';
    modal.innerHTML='<form method="dialog"><h3>Sửa các hồ sơ đã chọn</h3><p>Chỉ đánh dấu các trường cần sửa. Giá trị sẽ áp dụng cho <b>'+ids.length+'</b> hồ sơ. Mã hồ sơ đã cấp được giữ nguyên.</p><div id="bulkFields"></div><p><button type="button" id="bulkSave" class="btn btn-primary">Lưu thay đổi</button> <button class="btn btn-outline">Hủy</button></p><p id="bulkResult" role="status"></p></form>';
    document.body.append(modal);
    const holder=modal.querySelector('#bulkFields');
    const majors=await responseJson(await apiFetch('/applicants/majors')).catch(()=>({items:[]}));
    const fields=[['khoa','Khóa','bulkKhoa',Array.from({length:7},(_,i)=>String(i+24))],['dot','Đợt','bulkDot',Array.from({length:10},(_,i)=>String(i+1))],['nganh_nhap_hoc','Ngành','bulkMajor',majors.items.map(x=>x.name)],['gioi_tinh','Giới tính','bulkGender',['Nam','Nữ','Khác']],['ghi_chu','Ghi chú','bulkNote',null]];
    for(const [key,label,id,values] of fields){
      const row=document.createElement('div');row.style.margin='12px 0';
      const check=document.createElement('input');check.type='checkbox';check.dataset.field=key;check.id=id+'_apply';
      const caption=document.createElement('label');caption.htmlFor=check.id;caption.textContent=' '+label;
      const input=document.createElement(values?'select':'textarea');input.id=id;input.className='input';input.disabled=true;
      if(values){input.add(new Option('-- Chọn '+label.toLowerCase()+' --',''));values.forEach(v=>input.add(new Option(v,v)));}
      check.onchange=()=>{input.disabled=!check.checked;input.dispatchEvent(new Event('change'));};
      row.append(check,caption,input);holder.append(row);
      if(values)window.AMSSearchSelect?.upgrade(input);
    }
    modal.addEventListener('close',()=>modal.remove());modal.showModal();
    modal.querySelector('#bulkSave').onclick=async()=>{
      const changes={};
      for(const [key,label,id] of fields)if(modal.querySelector('#'+id+'_apply').checked){changes[key]=modal.querySelector('#'+id).value.trim();if(key!=='ghi_chu' && !changes[key]){modal.querySelector('#bulkResult').textContent='Nhập '+label;return;}}
      if(!Object.keys(changes).length){modal.querySelector('#bulkResult').textContent='Chọn ít nhất một trường cần sửa.';return;}
      if(!confirm(`Áp dụng thay đổi cho ${ids.length} hồ sơ đã chọn?`))return;
      busy=true;sync();modal.querySelector('#bulkSave').disabled=true;
      try {
        const result=await responseJson(await apiFetch('/applicants/batch-update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({items:ids.map(ma_so_hv=>({ma_so_hv,...changes}))})}));
        const failed=result.results.filter(r=>!['UPDATED','SKIPPED'].includes(r.status));
        await runSearch();updateBulkUI();
        modal.querySelector('#bulkResult').textContent=`Đã sửa ${result.updated}; không thay đổi ${result.skipped}; lỗi ${failed.length}.`+(failed.length?' '+failed.map(r=>r.ma_so_hv+': '+(r.errors?.join(', ')||r.status)).join('; '):'');
      } catch(e){modal.querySelector('#bulkResult').textContent=e.message;}
      finally{busy=false;sync();modal.querySelector('#bulkSave').disabled=false;}
    };
  };
  // Rendering changes selection without a change event.
  new MutationObserver(sync).observe($('bulkCount'),{childList:true});
  sync();
})();
