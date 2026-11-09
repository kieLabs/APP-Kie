(() => {
  'use strict';
  const API_STORAGE_KEY = 'apkie_api_base';
  const API_BASE = (localStorage.getItem(API_STORAGE_KEY) || '').replace(/\/$/, '');
  let apiBase = API_BASE;
  let activeMode = 'quick';
  let pollTimer = null;
  const $ = (id) => document.getElementById(id);
  const form = $('buildForm');

  function toast(message) {
    const node = $('toast'); node.textContent = message; node.classList.add('show');
    clearTimeout(toast.timer); toast.timer = setTimeout(() => node.classList.remove('show'), 3200);
  }
  function setView(name) {
    document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === `view-${name}`));
    document.querySelectorAll('.nav-link').forEach(a => a.classList.toggle('active', a.dataset.view === name));
    $('crumbTitle').textContent = ({home:'Overview',builder:'Create app',builds:'Build history'})[name] || 'Overview';
    $('sidebar').classList.remove('open');
    if (name === 'builds') loadBuilds();
    window.scrollTo({top:0,behavior:'smooth'});
  }
  function openBuilder(mode) {
    activeMode = mode || 'quick';
    $('advancedPanel').hidden = activeMode === 'quick';
    $('summaryMode').textContent = activeMode === 'quick' ? 'Quick' : 'Advanced';
    $('stepBadge');
    setView('builder');
    updatePreview();
  }
  document.querySelectorAll('[data-view]').forEach(a => a.addEventListener('click', e => { e.preventDefault(); setView(a.dataset.view); }));
  document.querySelectorAll('[data-view-link]').forEach(a => a.addEventListener('click', () => setView(a.dataset.viewLink)));
  document.querySelectorAll('[data-open-builder]').forEach(b => b.addEventListener('click', () => openBuilder(b.dataset.openBuilder)));
  $('mobileMenu').addEventListener('click', () => $('sidebar').classList.toggle('open'));

  function updatePreview() {
    const appName = $('appName').value.trim() || 'Your App';
    const url = $('siteUrl').value.trim();
    $('previewName').textContent = appName;
    try { $('previewUrl').textContent = url ? new URL(url).hostname : 'your-website.com'; } catch { $('previewUrl').textContent = 'Enter a valid website URL'; }
    $('previewIcon').textContent = appName.charAt(0).toUpperCase();
    $('summaryType').textContent = $('buildType').value.toUpperCase();
    $('summaryOrientation').textContent = ({portrait:'Portrait',landscape:'Landscape',unspecified:'Auto rotate'})[$('orientation').value];
    [['splashColor','#splashColor'],['statusColor','#statusColor'],['navColor','#navColor']].forEach(([id,selector]) => { const input=$(id); if(input) input.nextElementSibling.textContent=input.value.toUpperCase(); });
  }
  ['appName','siteUrl','buildType','orientation','splashColor','statusColor','navColor'].forEach(id => $(id).addEventListener('input', updatePreview));
  $('appIcon').addEventListener('change', () => { const f=$('appIcon').files[0]; $('iconFileName').textContent=f ? f.name : 'Choose an app icon'; });

  function showApiSettings() { $('apiBaseInput').value = apiBase; $('apiFeedback').textContent=''; $('apiFeedback').className='api-feedback'; $('apiModal').hidden=false; }
  $('openApiSettings').addEventListener('click', showApiSettings);
  $('closeApiSettings').addEventListener('click', () => $('apiModal').hidden=true);
  $('apiModal').addEventListener('click', e => { if(e.target === $('apiModal')) $('apiModal').hidden=true; });
  $('saveApi').addEventListener('click', () => {
    const value=$('apiBaseInput').value.trim().replace(/\/$/,'');
    if(value && !/^https:\/\//i.test(value)) { feedback('Use an HTTPS backend URL.','error'); return; }
    apiBase=value; if(value) localStorage.setItem(API_STORAGE_KEY,value); else localStorage.removeItem(API_STORAGE_KEY);
    $('apiModal').hidden=true; updateServerStatus(); toast(value?'Backend URL saved in this browser.':'Backend URL cleared.');
  });
  function feedback(msg,type='') { $('apiFeedback').textContent=msg; $('apiFeedback').className=`api-feedback ${type}`; }
  async function apiFetch(path, options={}) {
    if(!apiBase) throw new Error('Backend URL is not configured. Open API settings first.');
    const controller=new AbortController(); const timer=setTimeout(()=>controller.abort(),15000);
    try { const response=await fetch(`${apiBase}${path}`,{...options,signal:controller.signal}); const data=await response.json().catch(()=>({})); if(!response.ok) throw new Error(data?.error?.message || data?.detail || `Server error (${response.status})`); return data; }
    finally { clearTimeout(timer); }
  }
  async function testConnection() {
    feedback('Checking backend connection…');
    try { const data=await apiFetch('/api/health'); feedback(data.ok?'Connected. Build API is responding.':'Server responded, but health check is not OK.','success'); setServer(true,data); }
    catch(err) { feedback(err.message,'error'); setServer(false); }
  }
  $('testApi').addEventListener('click', testConnection);
  function setServer(online,data) {
    $('serverDot').classList.toggle('online',online); $('serverLabel').textContent=online?'Backend connected':'Backend not connected';
    $('serverHint').textContent=online?(data?.gradle_available?'Android build tools detected':'API online · build tools need verification'):'Add your API server URL';
    $('statService').textContent=online?'Connected':'Not connected';
  }
  async function updateServerStatus() { if(!apiBase){setServer(false);return;} try{const data=await apiFetch('/api/health');setServer(!!data.ok,data);}catch{setServer(false);} }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if(!form.reportValidity()) return;
    if(!apiBase) { toast('Connect your backend first in API settings.'); showApiSettings(); return; }
    const button=$('submitBuild'); button.disabled=true; button.textContent='Submitting build…';
    try {
      const data=new FormData(form); data.set('mode',activeMode);
      const result=await apiFetch('/api/builds',{method:'POST',body:data});
      toast('Build request accepted.'); setView('builds'); await loadBuilds(); watchBuild(result.build_id);
    } catch(err) { toast(err.message); }
    finally { button.disabled=false; button.innerHTML='Generate Android app <span>→</span>'; }
  });
  function escapeHtml(value) { return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  function renderBuild(build) {
    const status=String(build.status||'queued').toLowerCase();
    const date=build.created_at?new Date(build.created_at).toLocaleString():'';
    const download=status==='completed'?`<a class="download-link" href="${apiBase}/api/builds/${encodeURIComponent(build.id||build.build_id)}/download">Download ↓</a>`:'<span class="muted">—</span>';
    return `<div class="build-row"><div class="build-app"><b>${escapeHtml(build.app_name)}</b><small>${escapeHtml(build.package_name||'') } · ${escapeHtml(date)}</small></div><div><span class="status ${escapeHtml(status)}">${escapeHtml(status)}</span><small style="display:block;color:#9aa69f;margin-top:5px">${escapeHtml(build.message||'')}</small></div><div>${Number(build.progress||0)}%</div><div>${download}</div></div>`;
  }
  async function loadBuilds() {
    if(!apiBase) { $('historyList').innerHTML='<div class="empty-state"><span>⚙</span><b>Backend not connected</b><p>Open API settings and add your backend URL to view build history.</p></div>'; $('statBuilds').textContent='—'; return; }
    $('historyList').innerHTML='<div class="empty-state"><span>◷</span><b>Loading builds…</b></div>';
    try { const data=await apiFetch('/api/builds?limit=20'); const builds=data.builds||[]; $('statBuilds').textContent=String(builds.length); $('historyList').innerHTML=builds.length?builds.map(renderBuild).join(''):'<div class="empty-state"><span>◷</span><b>No builds to show</b><p>Your submitted builds will appear here.</p></div>'; }
    catch(err) { $('historyList').innerHTML=`<div class="empty-state"><span>!</span><b>Could not load build history</b><p>${escapeHtml(err.message)}</p></div>`; }
  }
  $('refreshBuilds').addEventListener('click',loadBuilds);
  function watchBuild(id) {
    clearInterval(pollTimer); let attempts=0;
    pollTimer=setInterval(async()=>{ attempts++; try { const data=await apiFetch(`/api/builds/${encodeURIComponent(id)}`); await loadBuilds(); if(['completed','failed'].includes(data.status)||attempts>120){clearInterval(pollTimer);toast(data.status==='completed'?'Your app is ready to download.':data.message||'Build finished.');} } catch { if(attempts>120) clearInterval(pollTimer); } },5000);
  }
  updatePreview(); updateServerStatus();
  if(location.hash==='#builder') openBuilder('quick');
})();
