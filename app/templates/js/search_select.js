/* Searchable selects retain the original elements for existing form logic. */
(() => {
  const normalize = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/gi,'d').toLowerCase();
  function upgrade(select) {
    if (select.dataset.searchReady) return;
    select.dataset.searchReady = '1';
    const free = /^(khoa|dot|dotKhoa|filterKhoa|filterDot|bulkKhoa|bulkDot)$/i.test(select.id) || /(?:khoa|dot)$/i.test(select.id);
    const wrapper = document.createElement('div');
    wrapper.style.position = 'relative';
    wrapper.style.minWidth = '0'; wrapper.style.flex = '1 1 140px';
    const input = document.createElement('input');
    input.className = select.className;
    input.style.width = '100%';
    input.type = 'text'; input.autocomplete = 'off';
    input.id = select.id + '_search';
    input.placeholder = select.options[0]?.textContent || 'Gõ để tìm và chọn';
    input.setAttribute('role','combobox'); input.setAttribute('aria-autocomplete','list');
    input.setAttribute('aria-label', select.title || select.closest('div')?.querySelector('label')?.textContent || input.placeholder);
    if (free) { input.inputMode = 'numeric'; input.placeholder = 'Gõ số hoặc chọn gợi ý'; }
    const list = document.createElement('div');
    list.id = input.id + '_list'; list.setAttribute('role','listbox');
    Object.assign(list.style, {position:'absolute', top:'100%', left:'0', right:'0', maxHeight:'240px', overflowY:'auto', background:'white', border:'1px solid #cbd5e1', boxShadow:'0 4px 12px #0002', zIndex:'100'});
    list.hidden = true;
    input.setAttribute('aria-controls',list.id);
    select.before(wrapper); wrapper.append(select,input,list);
    select.hidden = true; select.style.display = 'none'; select.tabIndex = -1;
    const descriptor = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value');
    const sync = () => { input.value = select.selectedOptions[0]?.value ? select.selectedOptions[0].textContent : ''; input.disabled = select.disabled; };
    Object.defineProperty(select,'value', {get(){return descriptor.get.call(this);}, set(value){
      value = String(value ?? '');
      if (free && value && !Array.from(this.options).some(o=>o.value===value)) this.add(new Option(value,value));
      descriptor.set.call(this,value); sync();
    }});
    function commit(value) { select.value = value; select.dispatchEvent(new Event('change',{bubbles:true})); }
    function draw() {
      list.replaceChildren();
      const term = normalize(input.value);
      const options = Array.from(select.options).filter(o => !o.disabled && (!term || normalize(o.textContent + ' ' + (o.dataset.code || '')).includes(term)));
      for (const option of options) {
        const button = document.createElement('button'); button.type = 'button'; button.setAttribute('role','option');
        button.textContent = option.textContent;
        Object.assign(button.style,{display:'block',width:'100%',textAlign:'left',padding:'8px',background:'white',border:'0',cursor:'pointer'});
        button.onmousedown = e => e.preventDefault();
        button.onclick = () => { commit(option.value); list.hidden=true; input.setAttribute('aria-expanded','false'); input.focus(); };
        list.append(button);
      }
      list.hidden = false; input.setAttribute('aria-expanded','true');
    }
    input.onfocus = () => { input.select(); draw(); };
    input.oninput = () => {
      const exact = Array.from(select.options).find(o => o.value && [o.value,o.textContent,o.dataset.code].some(v=>v && normalize(v)===normalize(input.value)));
      if (free) { const typed=input.value; commit(typed.trim()); input.value=typed; }
      else { const typed=input.value; descriptor.set.call(select, exact?.value || ''); select.dispatchEvent(new Event('change',{bubbles:true})); input.value=typed; }
      draw();
    };
    input.onkeydown = e => {
      if (e.key==='Escape') { list.hidden=true; sync(); }
      if (e.key==='ArrowDown') { e.preventDefault(); if(list.hidden)draw(); list.querySelector('button')?.focus(); }
      if(e.key==='Enter') { e.preventDefault(); list.querySelector('button')?.click(); }
    };
    list.onkeydown = e => { const buttons=Array.from(list.querySelectorAll('button')); const index=buttons.indexOf(document.activeElement);
      if(['ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();buttons[(index+(e.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length]?.focus();}
      if(e.key==='Escape'){list.hidden=true;input.focus();}
    };
    wrapper.addEventListener('focusout', () => setTimeout(()=>{if(!wrapper.contains(document.activeElement)){list.hidden=true;input.setAttribute('aria-expanded','false');sync();}},0));
    select.addEventListener('change',sync);
    new MutationObserver(sync).observe(select,{childList:true,subtree:true,attributes:true});
    sync();
  }
  function boot(){document.querySelectorAll('select').forEach(s=>{if(!['pageSize','bulkPreviewSelect','email_tpl','email_recipient_choice','bulk_recipient_choice'].includes(s.id))upgrade(s);});}
  window.AMSSearchSelect = {upgrade,boot};
  document.addEventListener('DOMContentLoaded',boot);
  // Links produced by historical import use the same confirmed-print workflow.
  document.addEventListener('click',e=>{const a=e.target.closest('a[href]');if(!a)return;const url=new URL(a.href,location.href);
    if(url.origin===location.origin && /\/(?:print\/a[45]\/|applicants\/(?:print\/email-receipt\/|[^/]+\/(?:print|print-a5|folder-cover|postal-print)$))/.test(url.pathname)){
      e.preventDefault();window.open('/print-preview?source='+encodeURIComponent(url.pathname+url.search),'_blank','noopener');
    }
  });
})();
