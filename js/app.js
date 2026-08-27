const LS_TUNNEL = 'tunnela_tunnel_url'
const LS_HISTORY = 'tunnela_history'
const LS_PARAMS = 'tunnela_last_params'
const LS_THEME = 'tunnela_theme'
const $ = s => document.querySelector(s)
const $$ = s => Array.from(document.querySelectorAll(s))
const els = {
  themeToggle: $('#themeToggle'),
  headerTitle: $('#headerTitle'),
  headerSubtitle: $('#headerSubtitle'),
  headerStatus: $('#headerStatus'),
  sidebarStatus: $('#sidebarStatus'),
  tunnelInput: $('#tunnelInput'),
  tunnelError: $('#tunnelError'),
  connectBtn: $('#connectBtn'),
  forgetBtn: $('#forgetBtn'),
  connectStatus: $('#connectStatus'),
  connectStatusText: $('#connectStatusText'),
  connectTroubleshoot: $('#connectTroubleshoot'),
  connectSuccess: $('#connectSuccess'),
  workspaceBanner: $('#workspaceBanner'),
  promptInput: $('#promptInput'),
  charCount: $('#charCount'),
  clearPromptBtn: $('#clearPromptBtn'),
  randomPromptBtn: $('#randomPromptBtn'),
  paramCollapsible: $('#paramCollapsible'),
  stepsRange: $('#stepsRange'),
  stepsVal: $('#stepsVal'),
  cfgRange: $('#cfgRange'),
  cfgVal: $('#cfgVal'),
  samplerSelect: $('#samplerSelect'),
  seedInput: $('#seedInput'),
  randomSeedBtn: $('#randomSeedBtn'),
  widthSelect: $('#widthSelect'),
  heightSelect: $('#heightSelect'),
  batchSelect: $('#batchSelect'),
  negativeInput: $('#negativeInput'),
  generateBtn: $('#generateBtn'),
  progressTrack: $('#progressTrack'),
  progressFill: $('#progressFill'),
  workspaceEmpty: $('#workspaceEmpty'),
  workspaceGrid: $('#workspaceGrid'),
  skeletonGrid: $('#skeletonGrid'),
  canvasMeta: $('#canvasMeta'),
  clearResultsBtn: $('#clearResultsBtn'),
  historyGrid: $('#historyGrid'),
  historyEmpty: $('#historyEmpty'),
  historySearch: $('#historySearch'),
  historyFilter: $('#historyFilter'),
  historyCount: $('#historyCount'),
  exportBtn: $('#exportBtn'),
  clearHistoryBtn: $('#clearHistoryBtn'),
  toastContainer: $('#toastContainer'),
  lightboxModal: $('#lightboxModal'),
  lightboxImg: $('#lightboxImg'),
  lightboxPrompt: $('#lightboxPrompt'),
  lightboxDownload: $('#lightboxDownload'),
  lightboxCopy: $('#lightboxCopy'),
  lightboxUse: $('#lightboxUse'),
  historyModal: $('#historyModal'),
  historyModalBody: $('#historyModalBody'),
  historyReuseBtn: $('#historyReuseBtn'),
  confirmModal: $('#confirmModal'),
  confirmTitle: $('#confirmTitle'),
  confirmDesc: $('#confirmDesc'),
  confirmAction: $('#confirmAction'),
  docTocLinks: null
}
let state = {
  page: 'home',
  tunnelUrl: '',
  history: [],
  workspaceResults: [],
  theme: 'dark',
  lightboxData: null,
  historyDetail: null,
  confirmCallback: null,
  generating: false
}
const pageMeta = {
  home: ['Home', 'Backend lokal, satu link publik'],
  connect: ['Connect', 'Paste link tunnel dari skrip'],
  workspace: ['Workspace', 'Generate gambar'],
  history: ['History', 'Riwayat generate di browser ini'],
  documentation: ['Docs', 'Cara menjalankan backend']
}
const samplePrompts = [
  'a quiet tea house courtyard in Kyoto, moss stones, drizzle, 35mm film look',
  'brutalist library interior, warm afternoon light through concrete slats',
  '1970s field research van parked at a salt flat at dusk, faded paint',
  'macro shot of dew on a fern frond, shallow depth of field',
  'night market alley, steam from food stalls, single hanging bulb'
]
function imgSource(item){
  return item.imageUrl || item.thumb || ''
}
function loadState(){
  try{
    state.tunnelUrl = localStorage.getItem(LS_TUNNEL) || ''
    state.history = JSON.parse(localStorage.getItem(LS_HISTORY) || '[]')
    let p = JSON.parse(localStorage.getItem(LS_PARAMS) || 'null')
    if(p){
      els.promptInput.value = p.prompt || ''
      els.negativeInput.value = p.negative || ''
      els.stepsRange.value = p.steps || 20
      els.cfgRange.value = p.cfg || 7
      els.samplerSelect.value = p.sampler || 'auto'
      els.seedInput.value = p.seed != null ? p.seed : -1
      els.widthSelect.value = p.width || '768'
      els.heightSelect.value = p.height || '768'
      els.batchSelect.value = p.batch || '1'
    }
    state.theme = localStorage.getItem(LS_THEME) || (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark')
  }catch(e){
    state.history = []
  }
}
function collectParams(){
  return {
    prompt: els.promptInput.value,
    negative: els.negativeInput.value,
    steps: els.stepsRange.value,
    cfg: els.cfgRange.value,
    sampler: els.samplerSelect.value,
    seed: els.seedInput.value,
    width: els.widthSelect.value,
    height: els.heightSelect.value,
    batch: els.batchSelect.value
  }
}
function saveParams(){
  localStorage.setItem(LS_PARAMS, JSON.stringify(collectParams()))
}
function applyTheme(){
  document.documentElement.setAttribute('data-theme', state.theme)
  localStorage.setItem(LS_THEME, state.theme)
  let icon = state.theme === 'dark' ? 'moon' : 'sun'
  els.themeToggle.innerHTML = `<i data-lucide="${icon}"></i>`
  if(window.lucide) window.lucide.createIcons()
}
function setStatus(status, text){
  let labels = { connected: 'Connected', checking: 'Memeriksa...', disconnected: 'Disconnected' }
  ;[els.headerStatus, els.sidebarStatus].forEach(el=>{
    if(!el) return
    el.className = 'status-badge ' + status
    let t = el.querySelector('.status-text')
    if(t) t.textContent = text || labels[status] || 'Disconnected'
  })
}
async function pingHealth(base){
  let ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null
  let timer = ctrl ? setTimeout(()=> ctrl.abort(), 4000) : null
  try{
    let res = await fetch(base + '/health', { signal: ctrl ? ctrl.signal : undefined })
    if(res.ok){
      let j = await res.json().catch(()=>null)
      return !!(j && j.ok !== false)
    }
    return false
  }catch(e){
    return false
  }finally{
    if(timer) clearTimeout(timer)
  }
}
function refreshConnection(){
  if(!state.tunnelUrl){
    setStatus('disconnected')
    return
  }
  setStatus('checking')
  pingHealth(state.tunnelUrl.replace(/\/$/,'')).then(ok=>{
    if(state.page && ok !== state.lastPingOk){
      if(!ok && state.lastPingOk) showToast('Koneksi putus','Server tidak merespons lagi','warning')
    }
    state.lastPingOk = ok
    setStatus(ok ? 'connected' : 'disconnected', ok ? 'Connected' : 'Server tak merespons')
    updateWorkspaceBanner()
  })
}
function navigate(page, anchor){
  state.page = page
  $$('.page').forEach(p=> p.classList.remove('active'))
  let target = $('#page-' + page)
  if(target) target.classList.add('active')
  $$('[data-nav]').forEach(b=>{
    if(b.closest('.doc-toc')) return
    b.classList.toggle('active', b.dataset.nav === page && b.matches('.nav-item,.mobile-nav-item'))
  })
  els.docTocLinks.forEach(a=> a.classList.toggle('active', false))
  if(pageMeta[page]){
    els.headerTitle.textContent = pageMeta[page][0]
    els.headerSubtitle.textContent = pageMeta[page][1]
  }
  window.scrollTo({top:0, behavior:'instant'})
  if(page === 'history') renderHistory()
  if(page === 'workspace') renderWorkspace()
  updateWorkspaceBanner()
  if(window.lucide) window.lucide.createIcons()
  if(anchor){
    requestAnimationFrame(()=>{
      let sec = document.getElementById(anchor)
      if(sec){
        sec.scrollIntoView({behavior:'smooth', block:'start'})
        let idx = els.docTocLinks.findIndex(a=> a.getAttribute('href') === '#' + anchor)
        if(idx >= 0){
          els.docTocLinks.forEach(a=> a.classList.remove('active'))
          els.docTocLinks[idx].classList.add('active')
        }
      }
    })
  }
}
function updateWorkspaceBanner(){
  if(state.page === 'workspace'){
    if(!state.tunnelUrl){
      els.workspaceBanner.querySelector('span').textContent = 'Belum ada backend terhubung. Generate jalan dalam mode demo.'
      els.workspaceBanner.classList.add('show')
      return
    }
    if(state.lastPingOk === false){
      els.workspaceBanner.querySelector('span').textContent = 'Server tidak merespons. Cek terminal tempat tunnela.py berjalan.'
      els.workspaceBanner.classList.add('show')
      return
    }
  }
  els.workspaceBanner.classList.remove('show')
}
function showToast(title, desc, type){
  type = type || 'success'
  let icons = {success:'check', error:'triangle-alert', warning:'triangle-alert', info:'info'}
  let icon = icons[type] || 'info'
  let el = document.createElement('div')
  el.className = 'toast ' + type
  el.innerHTML = `<i data-lucide="${icon}"></i><div class="toast-msg"><div class="toast-title">${title}</div>${desc?`<div class="toast-desc">${desc}</div>`:''}</div><button class="toast-close" aria-label="Tutup"><i data-lucide="x"></i></button>`
  els.toastContainer.appendChild(el)
  if(window.lucide) window.lucide.createIcons()
  let closed = false
  let close = ()=>{
    if(closed) return
    closed = true
    el.classList.add('out')
    setTimeout(()=> el.remove(), 200)
  }
  el.querySelector('.toast-close').addEventListener('click', close)
  setTimeout(close, 3400)
}
function validateTunnel(url){
  if(!url) return 'Link masih kosong'
  try{
    let u = new URL(url)
    if(u.protocol !== 'https:') return 'Harus diawali https://'
    return ''
  }catch{
    return 'Format link tidak valid'
  }
}
function setConnectState(type, msg){
  els.connectStatus.style.display = 'flex'
  els.connectStatus.className = 'status-panel ' + (type || '')
  let iconMap = {checking:'loader-2', success:'check', error:'triangle-alert'}
  let icon = iconMap[type] || 'info'
  els.connectStatus.innerHTML = `<i data-lucide="${icon}"${type==='checking'?' class="spin"':''}></i><span>${msg}</span>`
  if(window.lucide) window.lucide.createIcons()
}
async function testConnection(){
  let url = els.tunnelInput.value.trim().replace(/\/$/,'')
  let err = validateTunnel(url)
  els.connectSuccess.style.display = 'none'
  if(err){
    els.tunnelError.textContent = err
    els.tunnelError.classList.add('show')
    els.connectTroubleshoot.classList.remove('show')
    setConnectState('error', err)
    showToast('Validasi gagal', err, 'error')
    return
  }
  els.tunnelError.classList.remove('show')
  els.connectTroubleshoot.classList.remove('show')
  setConnectState('checking', 'Menghubungi server...')
  setStatus('checking')
  els.connectBtn.disabled = true
  let ok = await pingHealth(url)
  await new Promise(r=> setTimeout(r, 500))
  if(ok){
    state.tunnelUrl = url
    localStorage.setItem(LS_TUNNEL, url)
    state.lastPingOk = true
    setConnectState('success', 'Terhubung. Server merespons.')
    els.connectSuccess.style.display = 'block'
    setStatus('connected')
    updateWorkspaceBanner()
    showToast('Connected', 'Backend siap dipakai', 'success')
  }else{
    els.connectTroubleshoot.classList.add('show')
    setStatus('disconnected')
    setConnectState('error', 'Server tidak merespons. Cek terminal dan coba lagi.')
    showToast('Gagal terhubung', '/health tidak merespons dari link itu', 'error')
  }
  els.connectBtn.disabled = false
}
function forgetTunnel(){
  state.tunnelUrl = ''
  localStorage.removeItem(LS_TUNNEL)
  els.tunnelInput.value = ''
  els.connectStatus.style.display = 'none'
  els.connectTroubleshoot.classList.remove('show')
  els.connectSuccess.style.display = 'none'
  els.tunnelError.classList.remove('show')
  state.lastPingOk = null
  setStatus('disconnected')
  updateWorkspaceBanner()
  showToast('Link dilupakan', 'URL dihapus dari browser', 'warning')
}
function updateCharCount(){
  els.charCount.textContent = els.promptInput.value.length + ' karakter'
  saveParams()
}
function onRangeInput(){
  els.stepsVal.textContent = els.stepsRange.value
  els.cfgVal.textContent = els.cfgRange.value
  saveParams()
}
function randomSeed(){
  els.seedInput.value = Math.floor(Math.random()*2147483647)
  saveParams()
}
function renderWorkspace(){
  updateCharCount()
  onRangeInput()
  if(state.workspaceResults.length === 0){
    els.workspaceEmpty.classList.add('show')
    els.workspaceGrid.style.display = 'none'
    els.canvasMeta.textContent = 'Belum ada generate'
  }else{
    els.workspaceEmpty.classList.remove('show')
    els.workspaceGrid.style.display = 'grid'
    let last = state.workspaceResults[0]
    els.canvasMeta.textContent = `${state.workspaceResults.length} gambar terakhir`
    els.workspaceGrid.innerHTML = state.workspaceResults.map(item=> cardHTML(item, true)).join('')
    bindCardEvents(els.workspaceGrid)
    if(window.lucide) window.lucide.createIcons()
  }
}
function cardHTML(item){
  let src = imgSource(item)
  return `<div class="image-card">
    <div class="image-thumb" data-action="preview">
      <img src="${src}" alt="" loading="lazy">
      <div class="image-overlay">
        <button class="overlay-btn" data-action="download"><i data-lucide="download"></i> Download</button>
        <button class="overlay-btn" data-action="copy"><i data-lucide="copy"></i> Copy</button>
      </div>
    </div>
    <div class="image-meta">
      <div class="image-prompt">${escapeHTML(item.prompt)}</div>
      <div class="image-sub">
        <span>${item.width}x${item.height}</span>
        <span>seed ${item.seed_used != null ? item.seed_used : item.seed}</span>
      </div>
    </div>
  </div>`
}
function escapeHTML(s){
  return String(s).replace(/[&<>"']/g, c=> ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))
}
function bindCardEvents(container){
  container.querySelectorAll('.overlay-btn').forEach(btn=>{
    btn.addEventListener('click', e=>{
      e.stopPropagation()
      let card = btn.closest('.image-card')
      let item = findItem(card)
      if(!item) return
      let action = btn.dataset.action
      if(action==='download') downloadImage(item)
      if(action==='copy') copyPrompt(item)
    })
  })
  container.querySelectorAll('.image-thumb').forEach(thumb=>{
    thumb.addEventListener('click', ()=>{
      let card = thumb.closest('.image-card')
      let item = findItem(card)
      if(item) openLightbox(item)
    })
  })
}
function findItem(card){
  let promptEl = card.querySelector('.image-prompt')
  if(!promptEl) return null
  let prompt = promptEl.textContent
  return state.workspaceResults.find(x=> x.prompt === prompt) || state.history.find(x=> x.prompt === prompt)
}
function downloadImage(item){
  let a = document.createElement('a')
  a.href = item.imageUrl || item.thumb
  a.download = 'tunnela-' + (item.id || Date.now()) + '.png'
  a.target = '_blank'
  document.body.appendChild(a)
  a.click()
  a.remove()
  showToast('Download dimulai','','success')
}
async function copyPrompt(item){
  let text = item.prompt
  try{
    await navigator.clipboard.writeText(text)
    showToast('Prompt disalin','','success')
  }catch{
    let ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    ta.remove()
    showToast('Prompt disalin','','success')
  }
}
function usePrompt(item){
  els.promptInput.value = item.prompt || ''
  els.negativeInput.value = item.negative_prompt || item.negative || ''
  els.stepsRange.value = item.num_inference_steps || item.steps || 20
  els.cfgRange.value = item.guidance_scale || item.cfg || 7
  els.samplerSelect.value = item.sampler || 'auto'
  els.seedInput.value = item.seed_used != null ? item.seed_used : (item.seed != null ? item.seed : -1)
  els.widthSelect.value = String(item.width || 768)
  els.heightSelect.value = String(item.height || 768)
  els.batchSelect.value = String(item.batch_size || item.batch || 1)
  saveParams()
  updateCharCount()
  onRangeInput()
  navigate('workspace')
  showToast('Parameter dimuat','','success')
}
function makeThumb(src){
  return new Promise(resolve=>{
    let img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = ()=>{
      try{
        let size = 240
        let scale = Math.min(size / img.naturalWidth, size / img.naturalHeight, 1)
        let w = Math.max(1, Math.round(img.naturalWidth * scale))
        let h = Math.max(1, Math.round(img.naturalHeight * scale))
        let cv = document.createElement('canvas')
        cv.width = w; cv.height = h
        cv.getContext('2d').drawImage(img, 0, 0, w, h)
        resolve(cv.toDataURL('image/jpeg', 0.72))
      }catch(e){
        resolve(typeof src === 'string' && !src.startsWith('data:') ? src : '')
      }
    }
    img.onerror = ()=> resolve('')
    img.src = src
  })
}
async function persistHistory(newItems){
  if(newItems && newItems.length){
    for(let it of newItems){
      if(it.thumb) continue
      it.thumb = await makeThumb(imgSource(it))
    }
  }
  try{
    localStorage.setItem(LS_HISTORY, JSON.stringify(state.history.slice(0,120)))
  }catch(e){
    while(state.history.length > 4){
      state.history.length = Math.floor(state.history.length / 2)
      try{
        localStorage.setItem(LS_HISTORY, JSON.stringify(state.history))
        break
      }catch(e2){}
    }
  }
  renderHistory()
}
function renderHistory(){
  let term = (els.historySearch.value || '').toLowerCase().trim()
  let filter = els.historyFilter.value
  let now = new Date()
  let filtered = state.history.filter(item=>{
    let hay = ((item.prompt||'') + ' ' + String(item.date)).toLowerCase()
    if(term && !hay.includes(term)) return false
    if(filter==='today'){
      return new Date(item.date).toDateString() === now.toDateString()
    }
    if(filter==='week'){
      return now - new Date(item.date) < 7*24*60*60*1000
    }
    return true
  })
  els.historyCount.textContent = filtered.length + ' item tersimpan lokal'
  if(filtered.length===0){
    els.historyEmpty.classList.add('show')
    els.historyGrid.style.display = 'none'
    if(state.history.length===0){
      els.historyEmpty.querySelector('h3').textContent = 'Belum ada riwayat'
      els.historyEmpty.querySelector('p').textContent = 'Hasil generate tersimpan otomatis beserta prompt dan parameternya.'
    }else{
      els.historyEmpty.querySelector('h3').textContent = 'Tidak cocok'
      els.historyEmpty.querySelector('p').textContent = 'Ubah kata kunci atau filter waktu.'
    }
  }else{
    els.historyEmpty.classList.remove('show')
    els.historyGrid.style.display = 'grid'
    els.historyGrid.innerHTML = filtered.map(item=> cardHTML(item)).join('')
    bindCardEvents(els.historyGrid)
    els.historyGrid.querySelectorAll('.image-card').forEach((card, i)=>{
      card.addEventListener('click', e=>{
        if(e.target.closest('button')) return
        openHistoryDetail(filtered[i])
      })
    })
    if(window.lucide) window.lucide.createIcons()
  }
}
function openHistoryDetail(item){
  state.historyDetail = item
  let dateStr = new Date(item.date).toLocaleString('id-ID', {day:'2-digit', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit'})
  let steps = item.num_inference_steps || item.steps
  let cfg = item.guidance_scale || item.cfg
  els.historyModalBody.innerHTML = `
    <img src="${imgSource(item)}" alt="" style="width:100%;max-height:46vh;object-fit:cover;border-radius:10px;border:1px solid var(--border);background:var(--bg-elevated)">
    <div style="margin-top:12px;font-size:13px;line-height:1.5;color:var(--text-primary);font-weight:500">${escapeHTML(item.prompt)}</div>
    ${(item.negative_prompt||item.negative)?`<div style="margin-top:6px;font-size:12.5px;color:var(--text-secondary)"><span style="color:var(--text-muted)">Negative:</span> ${escapeHTML(item.negative_prompt||item.negative)}</div>`:''}
    <div class="detail-grid">
      <div class="detail-item"><div class="detail-label">Tanggal</div><div class="detail-value">${dateStr}</div></div>
      <div class="detail-item"><div class="detail-label">Model</div><div class="detail-value mono">${escapeHTML(String(item.model || '-'))}</div></div>
      <div class="detail-item"><div class="detail-label">Steps / CFG</div><div class="detail-value mono">${steps} / ${cfg}</div></div>
      <div class="detail-item"><div class="detail-label">Resolusi</div><div class="detail-value mono">${item.width} x ${item.height}</div></div>
    </div>
    <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">
      <button class="btn btn-secondary btn-sm" id="detailDownload"><i data-lucide="download"></i> Download</button>
      <button class="btn btn-secondary btn-sm" id="detailCopy"><i data-lucide="copy"></i> Copy prompt</button>
    </div>
  `
  openModal('historyModal')
  requestAnimationFrame(()=>{
    let dDl = $('#detailDownload')
    let dCp = $('#detailCopy')
    if(dDl) dDl.addEventListener('click', ()=> downloadImage(item))
    if(dCp) dCp.addEventListener('click', ()=> copyPrompt(item))
    if(window.lucide) window.lucide.createIcons()
  })
}
function openLightbox(item){
  state.lightboxData = item
  els.lightboxImg.src = imgSource(item)
  els.lightboxPrompt.textContent = item.prompt || ''
  openModal('lightboxModal')
}
function closeModal(id){
  let m = document.getElementById(id)
  if(m){ m.classList.remove('show'); m.setAttribute('aria-hidden','true') }
}
function openModal(id){
  let m = document.getElementById(id)
  if(m){ m.classList.add('show'); m.setAttribute('aria-hidden','false'); if(window.lucide) window.lucide.createIcons() }
}
function confirmAction(title, desc, actionText, cb){
  els.confirmTitle.textContent = title
  els.confirmDesc.textContent = desc
  els.confirmAction.textContent = actionText
  state.confirmCallback = cb
  openModal('confirmModal')
}
function showSkeletons(n){
  let cells = []
  for(let i=0;i<n;i++){
    cells.push(`<div class="image-card"><div class="image-thumb"><div class="skeleton" style="position:absolute;inset:8px;border-radius:10px"></div></div><div class="image-meta" style="padding:6px 2px 2px"><div class="sk-line skeleton"></div><div class="sk-line short skeleton"></div></div></div>`)
  }
  els.skeletonGrid.innerHTML = cells.join('')
  els.skeletonGrid.style.display = 'grid'
}
function hideSkeletons(){
  els.skeletonGrid.style.display = 'none'
  els.skeletonGrid.innerHTML = ''
}
function setGenerating(on){
  state.generating = on
  els.generateBtn.disabled = on
  els.generateBtn.innerHTML = on
    ? `<span class="spin" style="width:15px;height:15px;display:inline-block;border:2px solid rgba(255,255,255,0.35);border-top-color:#fff;border-radius:50%"></span> Generating...`
    : `<i data-lucide="play"></i> Generate <kbd>Ctrl Enter</kbd>`
  if(window.lucide) window.lucide.createIcons()
}
async function apiGenerate(payload){
  let base = state.tunnelUrl.replace(/\/$/,'')
  let res = await fetch(base + '/api/txt2img', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  })
  let data = null
  try{ data = await res.json() }catch(e){}
  if(!res.ok){
    throw new Error((data && data.error) || `HTTP ${res.status}`)
  }
  return data
}
async function generateRemote(payload){
  let res
  try{
    res = await apiGenerate({
      prompt: payload.prompt,
      negative_prompt: payload.negative || '',
      num_inference_steps: payload.stepsNum,
      guidance_scale: payload.cfgNum,
      width: payload.widthNum,
      height: payload.heightNum,
      batch_size: payload.batchNum,
      seed: payload.seedBase,
      sampler: els.samplerSelect.value
    })
  }catch(e){
    hideSkeletons()
    els.progressTrack.classList.remove('show')
    setGenerating(false)
    showToast('Generate gagal', String(e.message || e), 'error')
    return
  }
  finishGeneration(res.images.map(im=>{
    let uri = im.data_uri || im.image || im.data || ''
    if(uri && !String(uri).startsWith('data:')) uri = 'data:image/png;base64,' + uri
    return {
      id: Date.now() + '-' + Math.floor(Math.random()*1e5),
      prompt: payload.prompt,
      negative_prompt: payload.negative,
      num_inference_steps: payload.stepsNum,
      guidance_scale: payload.cfgNum,
      sampler: els.samplerSelect.value,
      width: res.width || payload.widthNum,
      height: res.height || payload.heightNum,
      seed_used: im.seed != null ? im.seed : res.seed_used,
      model: res.model || '',
      date: new Date().toISOString(),
      imageUrl: uri
    }
  }), res.took_s, false)
}
async function generateDemo(payload){
  await new Promise(r=> setTimeout(r, 2200 + Math.random()*900))
  let batch = payload.batchNum
  let baseSeed = payload.seedBase >= 0 ? payload.seedBase : Math.floor(Math.random()*999999)
  let items = []
  for(let i=0;i<batch;i++){
    let s = baseSeed + i
    items.push({
      id: Date.now() + '-' + i + '-' + Math.floor(Math.random()*1e5),
      prompt: payload.prompt,
      negative_prompt: payload.negative,
      num_inference_steps: payload.stepsNum,
      guidance_scale: payload.cfgNum,
      sampler: els.samplerSelect.value,
      width: payload.widthNum,
      height: payload.heightNum,
      seed_used: s,
      model: 'demo-placeholder',
      date: new Date().toISOString(),
      imageUrl: `https://picsum.photos/seed/${s}/600/600`
    })
  }
  finishGeneration(items, null, true)
}
function finishGeneration(items, tookSec, isDemo){
  hideSkeletons()
  if(tween){ clearInterval(tween); tween = null }
  els.progressFill.style.width = '100%'
  state.workspaceResults = [...items, ...state.workspaceResults].slice(0, 48)
  state.history = [...items.map(x=> ({...x})), ...state.history]
  if(state.history.length > 120) state.history = state.history.slice(0, 120)
  persistHistory(items)
  renderWorkspace()
  setTimeout(()=>{ els.progressTrack.classList.remove('show'); els.progressFill.style.width = '0%' }, 260)
  setGenerating(false)
  let tagline = isDemo
    ? `${items.length} placeholder demo dibuat`
    : `${items.length} gambar selesai${tookSec != null ? ` dalam ${tookSec}s` : ''}`
  showToast(isDemo ? 'Demo selesai' : 'Selesai', tagline, 'success')
  if(els.seedInput.value !== '-1'){
    els.seedInput.value = parseInt(els.seedInput.value,10) + items.length
    saveParams()
  }
}
async function doGenerate(){
  if(state.generating) return
  let prompt = els.promptInput.value.trim()
  if(!prompt){
    showToast('Prompt kosong','Tulis deskripsi dulu','error')
    els.promptInput.focus()
    return
  }
  saveParams()
  setGenerating(true)
  els.progressTrack.classList.add('show')
  els.progressFill.style.width = '8%'
  tween = setInterval(()=>{
    let cur = parseFloat(els.progressFill.style.width) || 8
    if(cur < 90) els.progressFill.style.width = Math.min(90, cur + Math.random()*9) + '%'
  }, 260)
  showSkeletons(Math.min(parseInt(els.batchSelect.value,10) || 1, 4))
  els.workspaceEmpty.classList.remove('show')
  let payload = {
    prompt,
    negative: els.negativeInput.value.trim(),
    stepsNum: parseInt(els.stepsRange.value,10),
    cfgNum: parseFloat(els.cfgRange.value),
    widthNum: parseInt(els.widthSelect.value,10),
    heightNum: parseInt(els.heightSelect.value,10),
    batchNum: parseInt(els.batchSelect.value,10) || 1,
    seedBase: els.seedInput.value === '' || els.seedInput.value === '-1' ? -1 : parseInt(els.seedInput.value,10)
  }
  if(state.tunnelUrl && state.lastPingOk !== false){
    await generateRemote(payload)
  }else{
    if(state.tunnelUrl) showToast('Mode demo','Server tidak merespons saat ini','warning')
    await generateDemo(payload)
  }
}
let tween = null
function exportHistory(){
  if(state.history.length===0){
    showToast('Belum ada data','History masih kosong','warning')
    return
  }
  let slim = state.history.map(({imageUrl, thumb, ...rest})=> rest)
  let blob = new Blob([JSON.stringify(slim, null, 2)], {type:'application/json'})
  let url = URL.createObjectURL(blob)
  let a = document.createElement('a')
  a.href = url
  a.download = 'tunnela-history-' + new Date().toISOString().slice(0,10) + '.json'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
  showToast('Export selesai','Metadata tanpa gambar','success')
}
function clearHistory(){
  if(state.history.length===0){
    showToast('Sudah kosong','','warning')
    return
  }
  confirmAction('Bersihkan history','Semua riwayat hilang permanen.', 'Hapus semua', ()=>{
    state.history = []
    state.workspaceResults = []
    localStorage.removeItem(LS_HISTORY)
    renderHistory()
    renderWorkspace()
    showToast('History dibersihkan','','success')
  })
}
function initEvents(){
  $$('[data-nav]').forEach(b=>{
    b.addEventListener('click', ()=> navigate(b.dataset.nav, b.dataset.anchor))
  })
  els.themeToggle.addEventListener('click', ()=>{
    state.theme = state.theme === 'dark' ? 'light' : 'dark'
    applyTheme()
  })
  els.tunnelInput.addEventListener('input', ()=>{
    els.tunnelError.classList.remove('show')
    els.connectStatus.style.display = 'none'
    els.connectTroubleshoot.classList.remove('show')
    els.connectSuccess.style.display = 'none'
  })
  els.connectBtn.addEventListener('click', testConnection)
  els.forgetBtn.addEventListener('click', forgetTunnel)
  els.tunnelInput.addEventListener('keydown', e=>{
    if(e.key==='Enter') testConnection()
  })
  els.promptInput.addEventListener('input', updateCharCount)
  els.negativeInput.addEventListener('input', saveParams)
  els.stepsRange.addEventListener('input', onRangeInput)
  els.cfgRange.addEventListener('input', onRangeInput)
  els.samplerSelect.addEventListener('change', saveParams)
  els.widthSelect.addEventListener('change', saveParams)
  els.heightSelect.addEventListener('change', saveParams)
  els.batchSelect.addEventListener('change', saveParams)
  els.seedInput.addEventListener('input', saveParams)
  els.randomSeedBtn.addEventListener('click', randomSeed)
  els.clearPromptBtn.addEventListener('click', ()=>{
    els.promptInput.value = ''
    updateCharCount()
    els.promptInput.focus()
  })
  els.randomPromptBtn.addEventListener('click', ()=>{
    els.promptInput.value = samplePrompts[Math.floor(Math.random()*samplePrompts.length)]
    updateCharCount()
  })
  let colHead = els.paramCollapsible.querySelector('.collapsible-head')
  colHead.addEventListener('click', ()=>{
    els.paramCollapsible.classList.toggle('open')
    colHead.setAttribute('aria-expanded', els.paramCollapsible.classList.contains('open'))
  })
  els.generateBtn.addEventListener('click', doGenerate)
  els.clearResultsBtn.addEventListener('click', ()=>{
    if(state.workspaceResults.length===0){
      showToast('Sudah kosong','','warning')
      return
    }
    confirmAction('Bersihkan kanvas','Hasil di kanvas dihapus. History tetap aman.', 'Bersihkan', ()=>{
      state.workspaceResults = []
      renderWorkspace()
      showToast('Kanvas bersih','','success')
    })
  })
  els.historySearch.addEventListener('input', renderHistory)
  els.historyFilter.addEventListener('change', renderHistory)
  els.exportBtn.addEventListener('click', exportHistory)
  els.clearHistoryBtn.addEventListener('click', clearHistory)
  els.lightboxDownload.addEventListener('click', ()=>{ if(state.lightboxData) downloadImage(state.lightboxData) })
  els.lightboxCopy.addEventListener('click', ()=>{ if(state.lightboxData) copyPrompt(state.lightboxData) })
  els.lightboxUse.addEventListener('click', ()=>{
    if(state.lightboxData){
      closeModal('lightboxModal')
      usePrompt(state.lightboxData)
    }
  })
  els.historyReuseBtn.addEventListener('click', ()=>{
    if(state.historyDetail){
      closeModal('historyModal')
      usePrompt(state.historyDetail)
    }
  })
  els.confirmAction.addEventListener('click', ()=>{
    if(state.confirmCallback) state.confirmCallback()
    closeModal('confirmModal')
    state.confirmCallback = null
  })
  $$('[data-close]').forEach(el=>{
    el.addEventListener('click', ()=> closeModal(el.dataset.close))
  })
  $$('.accordion-trigger').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      btn.closest('.accordion-item').classList.toggle('open')
      if(window.lucide) window.lucide.createIcons()
    })
  })
  $$('[data-copy]').forEach(btn=>{
    btn.addEventListener('click', async ()=>{
      let text = btn.dataset.copy || ''
      try{
        await navigator.clipboard.writeText(text)
        showToast('Disalin ke clipboard','','success')
      }catch{
        let ta=document.createElement('textarea')
        ta.value=text
        document.body.appendChild(ta)
        ta.select()
        document.execCommand('copy')
        ta.remove()
        showToast('Disalin ke clipboard','','success')
      }
    })
  })
  document.addEventListener('keydown', e=>{
    if((e.ctrlKey || e.metaKey) && e.key==='Enter'){
      if(state.page==='workspace') doGenerate()
    }
    if(e.key==='Escape'){
      closeModal('lightboxModal')
      closeModal('historyModal')
      closeModal('confirmModal')
    }
  })
  els.docTocLinks = $$('.doc-toc a')
  els.docTocLinks.forEach(a=>{
    a.addEventListener('click', e=>{
      e.preventDefault()
      let id = a.getAttribute('href').slice(1)
      let sec = document.getElementById(id)
      if(sec) sec.scrollIntoView({behavior:'smooth', block:'start'})
      els.docTocLinks.forEach(x=> x.classList.remove('active'))
      a.classList.add('active')
    })
  })
}
function init(){
  loadState()
  applyTheme()
  if(state.tunnelUrl) els.tunnelInput.value = state.tunnelUrl
  refreshConnection()
  renderWorkspace()
  renderHistory()
  updateWorkspaceBanner()
  initEvents()
  if(window.lucide) window.lucide.createIcons()
  let hash = location.hash.replace('#','')
  if(hash && pageMeta[hash]) navigate(hash)
  setInterval(refreshConnection, 30000)
}
document.addEventListener('DOMContentLoaded', init)
