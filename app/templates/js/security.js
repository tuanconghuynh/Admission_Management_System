/* Same-origin CSRF for fetch, XMLHttpRequest and native HTML forms. */
(() => {
  const token = () => decodeURIComponent((document.cookie.match(/(?:^|;\s*)(?:__Host-)?ams_csrf=([^;]+)/) || [,''])[1]);
  const unsafe = method => !['GET', 'HEAD', 'OPTIONS'].includes((method || 'GET').toUpperCase());
  const local = url => new URL(url, location.href).origin === location.origin;
  const originalFetch = window.fetch;
  window.fetch = (input, init = {}) => {
    const url = input instanceof Request ? input.url : input;
    const method = init.method || (input instanceof Request ? input.method : 'GET');
    if (unsafe(method) && local(url)) {
      const headers = new Headers(init.headers || (input instanceof Request ? input.headers : undefined));
      headers.set('X-CSRF-Token', token());
      init = {...init, headers};
    }
    return originalFetch.call(window, input, init);
  };
  const open = XMLHttpRequest.prototype.open;
  const send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(method, url, ...args) {
    this.amsCsrf = unsafe(method) && local(url);
    return open.call(this, method, url, ...args);
  };
  XMLHttpRequest.prototype.send = function(body) {
    if (this.amsCsrf) this.setRequestHeader('X-CSRF-Token', token());
    return send.call(this, body);
  };
  const protectForm = form => {
    if (!unsafe(form.method) || !local(form.action)) return;
    let field = form.querySelector('input[name="csrf_token"]');
    if (!field) {
      field = document.createElement('input');
      field.type = 'hidden'; field.name = 'csrf_token'; form.append(field);
    }
    field.value = token();
  };
  document.addEventListener('submit', e => protectForm(e.target), true);
  document.addEventListener('DOMContentLoaded', () => document.querySelectorAll('form').forEach(protectForm));
})();
