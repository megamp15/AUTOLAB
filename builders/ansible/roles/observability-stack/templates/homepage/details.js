/* Node, VM and container inspection. The overview owns topology; this module owns detail navigation. */
window.createAutolabDetails = function ({ rows, getModel, renderPage, lessMotion }) {
  let request = null, version = 0, range = '1h', viewKey = '', pendingFocus = false, refreshData = null;
  const node = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; };
  const bytes = value => value == null ? '—' : value >= 1099511627776 ? (value / 1099511627776).toFixed(2) + ' TiB' : value >= 1073741824 ? (value / 1073741824).toFixed(1) + ' GiB' : value >= 1048576 ? (value / 1048576).toFixed(0) + ' MiB' : (value / 1024).toFixed(0) + ' KiB';
  const route = () => {
    if (location.hash.split('?')[0] !== '#architecture') return null;
    const q = new URLSearchParams(location.hash.split('?')[1] || '');
    return q.get('node') ? { node: q.get('node'), vm: q.get('vm') || '', container: q.get('container') || '' } : null;
  };
  const hash = selection => {
    const q = new URLSearchParams();
    for (const key of ['node', 'vm', 'container']) if (selection[key]) q.set(key, selection[key]);
    return '#architecture' + (q.size ? '?' + q : '');
  };
  function navigate(selection, source) {
    if (window.getSelection().toString()) return;
    pendingFocus = true;
    const change = () => { history.pushState(null, '', hash(selection)); rows.scrollTop = 0; renderPage(); };
    if (source && document.startViewTransition && !lessMotion()) {
      rows.querySelectorAll('[style*="view-transition-name"]').forEach(e => { e.style.viewTransitionName = ''; });
      source.style.viewTransitionName = 'inspect';
      document.startViewTransition(change).finished.catch(() => {}).finally(() => { source.style.viewTransitionName = ''; });
    } else change();
  }
  function button(text, selection, cls) {
    const b = node('button', cls || 'd-button', text); b.type = 'button';
    b.addEventListener('click', () => navigate(selection, b.closest('.d-entity'))); return b;
  }
  function external(text, url) {
    const a = node('a', 'd-button', text); a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; return a;
  }
  function table(headers, records) {
    const scroller = node('div', 'd-table-scroll'); const t = node('table', 'd-table');
    const head = node('thead'), tr = node('tr'); headers.forEach(h => tr.append(node('th', '', h))); head.append(tr); t.append(head);
    const body = node('tbody'); records.forEach(record => { const row = node('tr'); record.forEach(value => { const cell = node('td'); cell.append(value instanceof Node ? value : document.createTextNode(String(value))); row.append(cell); }); body.append(row); });
    t.append(body); scroller.append(t); return scroller;
  }
  function section(title, content) { const s = node('section', 'd-section'); s.append(node('h2', '', title), content); return s; }
  function chart(item) {
    const panel = node('section', 'd-chart'); panel.append(node('h2', '', item.title));
    const values = item.values.filter(p => Number.isFinite(p[1]));
    if (values.length < 2) { panel.append(node('p', 'd-empty', item.error || 'No samples received in this time range.')); return panel; }
    const last = values.at(-1)[1], fmt = v => item.unit === '%' ? v.toFixed(1) + '%' : item.unit === 'cores' ? v.toFixed(2) + ' cores' : bytes(v) + (item.unit === 'B/s' ? '/s' : '');
    panel.append(node('p', 'd-reading mono', fmt(last)));
    const start = item.values[0][0], end = item.values.at(-1)[0], max = item.unit === '%' ? Math.max(100, ...values.map(p => p[1])) : Math.max(1, ...values.map(p => p[1])) * 1.15;
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('viewBox', '0 0 600 150'); svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', `${item.title} over ${range}. Latest ${fmt(last)}.`);
    const add = (tag, attrs) => { const e = document.createElementNS(svg.namespaceURI, tag); Object.entries(attrs).forEach(([k,v]) => e.setAttribute(k,v)); svg.append(e); return e; };
    for (const y of [12, 67, 122]) add('path', { d: `M0 ${y}H600`, class: 'd-chart-grid' });
    let d = '', connected = false;
    for (const [t, v] of item.values) { if (!Number.isFinite(v)) { connected = false; continue; } const x = (t - start) / Math.max(1,end-start) * 600, y = 122 - v/max*110; d += `${connected?'L':'M'}${x.toFixed(2)} ${y.toFixed(2)} `; connected = true; }
    add('path', { d, class:'d-chart-line' });
    const caption = node('div', 'd-chart-caption mono'); caption.append(node('span', '', new Date(start*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})), node('span', '', new Date(end*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})));
    panel.append(svg, caption); return panel;
  }
  function poolTable(pools) {
    if (!pools.length) return node('p', 'd-empty', 'No storage-pool readings received from Proxmox.');
    return table(['Pool', 'Type', 'Used / total', 'Free', 'Status'], pools.map(p => {
      const usage = node('div', 'd-pool-usage');
      usage.append(node('span', 'mono', p.total ? `${bytes(p.used)} / ${bytes(p.total)}` : '—'));
      if (p.total) { const value=p.used/p.total*100; usage.dataset.level=value>=85?'critical':value>=80?'high':'normal'; const meter=node('span','a-bar-track d-pool-track'); meter.setAttribute('role','meter');meter.setAttribute('aria-label',p.name+' storage used');meter.setAttribute('aria-valuemin','0');meter.setAttribute('aria-valuemax',String(p.total));meter.setAttribute('aria-valuenow',String(p.used));const fill=node('i');fill.style.width=Math.min(100,value).toFixed(2)+'%';meter.append(fill);meter.title=value.toFixed(1)+'% used';usage.append(meter); }
      return [p.name + (p.shared ? ' · shared' : ''), p.type || '—', usage, bytes(p.free), node('span', p.active && p.total ? 'd-good' : 'd-bad', p.active && p.total ? 'Available' : 'Unavailable')];
    }));
  }
  function render() {
    const selection = route(); if (!selection) { request?.abort(); viewKey = ''; return; }
    const m = getModel(), host = m.nodes.find(n => n.name === selection.node);
    const guest = selection.vm && host?.guests?.find(g => g.name === selection.vm);
    const title = selection.container || selection.vm || selection.node;
    const signature = hash(selection), changed = signature !== viewKey;
    if (!changed && rows.querySelector('.a-detail') && refreshData) { refreshData(); return; }
    viewKey = signature; request?.abort();
    const scroll = rows.scrollTop; let shownRange = '';
    const root = node('div', 'a-detail');
    const nav = node('nav', 'd-nav'); nav.setAttribute('aria-label', 'Architecture breadcrumbs');
    nav.append(button('Architecture', {}));
    if (selection.vm) nav.append(node('span', 'muted', '/'), button(selection.node, {node:selection.node}));
    if (selection.container) nav.append(node('span','muted','/'), button(selection.vm,{node:selection.node,vm:selection.vm}));
    nav.append(node('span','muted','/'),node('span','',title)); root.append(nav);
    const head = node('header', 'd-header'); head.style.viewTransitionName = 'inspect';
    const heading = node('div'); const h = node('h1','',title); h.tabIndex = -1; heading.append(h);
    heading.append(node('p','muted',selection.container ? `Container on ${selection.vm}` : guest ? `${guest.type || 'VM'} ${guest.vmid} · ${guest.maxcpu || '?'} vCPU · ${bytes(guest.maxmem)} · ${guest.status}` : 'Proxmox host · management view'));
    const actions = node('div','d-actions'); const parent = selection.container ? {node:selection.node,vm:selection.vm} : selection.vm ? {node:selection.node} : {};
    actions.append(button('Back',parent)); const url = m.link.byName[selection.vm || selection.node]; if (url) actions.append(external('Open Proxmox ↗',url));
    const grafana = m.link.byName.Grafana; if (grafana) actions.append(external('Grafana ↗',grafana)); head.append(heading,actions); root.append(head);
    if (!host || (selection.vm && !guest)) { root.append(node('p','d-empty','This machine is no longer in the inventory.')); rows.replaceChildren(root); return; }
    const bar = node('div','d-range'); bar.append(node('span','muted','History'));
    for (const value of ['1h','6h','24h']) { const b = node('button','d-button',value); b.type='button'; b.setAttribute('aria-pressed',String(range===value)); b.onclick=()=>{if(range===value)return;range=value;bar.querySelectorAll('button').forEach(item=>item.setAttribute('aria-pressed',String(item.textContent===value)));refreshData();};bar.append(b); }
    const updated = node('span','d-updated muted','Loading current readings…'); updated.setAttribute('role','status'); updated.setAttribute('aria-live','polite'); bar.append(updated);root.append(bar);
    const chartGrid = node('div','d-charts'); chartGrid.append(node('p','d-empty','Loading metric history…'));root.append(chartGrid);
    const inventory = node('div');
    if (!selection.vm) {
      const records = (host.guests || []).filter(g=>!g.template).map(g=>[button(g.name,{node:host.name,vm:g.name},'d-entity'),g.status, g.maxcpu || '—',bytes(g.maxmem),String(g.tags || '').split(';').filter(t=>t.startsWith('tenant-')).join(', ').replaceAll('tenant-','') || 'Autolab']);
      inventory.append(section('Virtual machines',table(['VM','Status','vCPU','Memory assigned','Owner'],records)));
    }
    root.append(inventory);
    const storage = node('div'), containers = node('div'), logs = node('div');root.append(storage,containers,logs);
    rows.replaceChildren(root); rows.scrollTop = changed ? 0 : scroll;
    if (pendingFocus) { pendingFocus=false;h.focus({preventScroll:true}); }
    refreshData = () => {
    request?.abort(); request = new AbortController(); const current = ++version;
    updated.dataset.loading = 'true';
    updated.textContent = 'Refreshing…';
    const params = new URLSearchParams({...selection,range});
    fetch('api/detail?'+params,{signal:request.signal,cache:'no-store'}).then(async r=>{const d=await r.json();if(!r.ok)throw new Error(d.error || 'Detail data unavailable');return d;}).then(data=>{
      if(current!==version)return;
      storage.replaceChildren();containers.replaceChildren();logs.replaceChildren();
      shownRange=data.range;
      updated.dataset.loading='false';
      updated.textContent='Updated '+new Date(data.generated*1000).toLocaleTimeString();
      const available = data.charts.filter(c=>c.values.some(p=>Number.isFinite(p[1])));
      chartGrid.replaceChildren(...(available.length?available.map(chart):[node('p','d-empty','No machine metrics received in this time range.')]));
      if (data.pools.length) {storage.append(section('Proxmox storage pools',poolTable(data.pools)),node('p','d-note muted','Actual pool usage reported by Proxmox. Shared stores appear per host; capacities are not added together. Thin-provisioned disk assignments are separate from physical bytes used.'));}
      if(data.filesystems.length && !selection.container) storage.append(section('Host filesystems',table(['Mount','Type','Used / total','Available to workloads'],data.filesystems.map(f=>[f.mount,f.type,`${bytes(f.used)} / ${bytes(f.total)}`,bytes(f.available)]))));
      if(selection.vm && !selection.container){
        if(data.containers.length)containers.append(section('Containers',table(['Container','CPU cores','Working memory'],data.containers.map(c=>[button(c.name,{...selection,container:c.name},'d-entity'),c.cpu==null?'—':c.cpu.toFixed(3),bytes(c.mem)]))));
        else if(!data.tenant)containers.append(section('Containers',node('p','d-empty','No container metrics received for this VM.')));
        else containers.append(node('p','d-note muted','Tenant-managed VM. This view shows the provider baseline; application containers and logs remain with the tenant.'));
      }
      if(data.backups?.length && !selection.container){const fresh=data.backup_collected&&Date.now()/1000-data.backup_collected<3600;storage.append(section('Backup snapshots',table(['VM','Latest completed snapshot','State'],data.backups.map(b=>[b.name,b.last?new Date(b.last*1000).toLocaleString():'—',!fresh?'Collector stale':b.excluded?'Excluded':!b.last?'No snapshot reported':Date.now()/1000-b.last>26*3600?'Overdue':'Recent']))));}
      const logBody = node('div','d-logs');
      if(data.logs.length)for(const line of data.logs){const row=node('div','d-log');row.append(node('time','mono',new Date(line.time*1000).toLocaleTimeString()),node('span','mono',line.text));logBody.append(row);}
      else logBody.append(node('p','d-empty',data.log_error || 'No log entries received in this time range.'));
      logs.append(section(selection.container?'Recent container logs':data.tenant?'Recent system logs':'Recent logs',logBody));
    }).catch(error=>{if(error.name==='AbortError'||current!==version)return;updated.dataset.loading='false';updated.textContent=shownRange?'Refresh failed · showing '+shownRange:'Source unavailable';if(!chartGrid.querySelector('.d-chart'))chartGrid.replaceChildren(node('p','d-empty',error.message));if(!bar.querySelector('[data-retry]')){const retry=node('button','d-button','Retry');retry.dataset.retry='1';retry.onclick=()=>{retry.remove();refreshData();};bar.append(retry);}});
    };
    refreshData();
  }
  rows.addEventListener('click',event=>{
    if(event.defaultPrevented||event.ctrlKey||event.metaKey||event.target.closest('a,input,label'))return;
    const vm=event.target.closest('[data-detail-vm]'), host=event.target.closest('[data-detail-node]');
    if(!host || (event.target.closest('button')&&!event.target.closest('.a-title-inspect')))return;
    navigate({node:host.dataset.detailNode,...(vm?{vm:vm.dataset.detailVm}:{})},vm||host);
  });
  window.addEventListener('popstate',renderPage);
  return {active:()=>!!route(),refresh:render,navigate};
};
