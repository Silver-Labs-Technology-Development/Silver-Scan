/* Silver Scan research terminal. Provider data is external and attributed.
 * Render every provider-supplied string through textContent, never innerHTML.
 * Coin Watch is local browser storage: no cloud account or alerts.
 */
const explorer = document.getElementById('view')
const research = document.getElementById('research-view')
const tabs = [...document.querySelectorAll('[data-tab]')]
const WATCH_KEY = 'silver-scan-coin-watch-v1'
const prices = new Intl.NumberFormat('en-US', {style:'currency',currency:'USD',maximumFractionDigits:8})
let marketRows = []

function el(tag, text, className) {
  const node = document.createElement(tag)
  if (text !== undefined && text !== null) node.textContent = String(text)
  if (className) node.className = className
  return node
}
function rowCells(row, cells) {
  const tr = el('tr')
  for (const value of cells) tr.append(el('td', value == null ? 'Unavailable' : value))
  row.append(tr)
  return tr
}
function notice(text) { research.replaceChildren(el('p', text, 'research-note')) }
function formatted(value) {
  return typeof value === 'number' && Number.isFinite(value) ? prices.format(value) : 'Unavailable'
}
function number(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString('en-US') : 'Unavailable'
}
function pct(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(2) + '%' : 'Unavailable'
}
function sourceInfo(source, fetched, stale) {
  const container = el('p', '', 'research-note')
  container.append(el('span', 'Source: ' + source + ' · '))
  container.append(el('span', fetched ? 'Fetched: ' + new Date(fetched * 1000).toLocaleString() : 'Timestamp unavailable'))
  container.append(el('strong', stale ? ' · STALE / provider unavailable' : ' · Reference data, not Silver Labs trades'))
  return container
}
async function getJson(path) {
  const r = await fetch(path, {headers:{'Accept':'application/json'}})
  if (!r.ok) throw new Error('Source unavailable (HTTP ' + r.status + '). Try again later.')
  return r.json()
}
function watchIds() {
  try {
    const items = JSON.parse(localStorage.getItem(WATCH_KEY) || '[]')
    return Array.isArray(items) ? items.filter(x => typeof x === 'string').slice(0,100) : []
  } catch { return [] }
}
function setWatch(ids) {
  try { localStorage.setItem(WATCH_KEY, JSON.stringify(ids.slice(0,100))) }
  catch { notice('Browser storage is unavailable. Coin Watch cannot save changes here.') }
}
function switchTab(tab) {
  tabs.forEach(button => {
    const active = button.dataset.tab === tab
    button.setAttribute('aria-pressed', String(active))
    button.classList.toggle('selected', active)
  })
  explorer.hidden = tab !== 'explorer'
  document.getElementById('explorer-controls').hidden = tab !== 'explorer'
  research.hidden = tab === 'explorer'
  if (tab === 'markets') loadMarkets()
  if (tab === 'watch') loadWatch()
  if (tab === 'dex') showDexSearch()
}

function marketTable(data, filterWatch=false) {
  const heading = el('div', '', 'research-head')
  heading.append(el('h2', filterWatch ? 'Coin Watch' : 'Markets'))
  heading.append(sourceInfo(data.source, data.fetched_at, data.stale))
  const description = el('p', 'Coin Watch stays in this browser. Price, volume, ranks and supply are external research data, not native SilvEx activity.', 'research-note')
  const table = el('table')
  const head = el('tr')
  for (const h of ['Asset', 'Rank', 'Price USD', '24h', '24h volume', 'Watch']) head.append(el('th',h))
  table.append(head)
  const ids = watchIds()
  const coins = filterWatch ? data.assets.filter(c => ids.includes(c.id)) : data.assets
  for (const c of coins) {
    const tr = rowCells(table, [
      (c.name || 'Unknown') + ' (' + (c.symbol || '-') + ')',
      c.rank,
      formatted(c.price_usd),
      pct(c.change_24h_pct),
      formatted(c.volume_24h_usd),
      ''
    ])
    const btn = el('button', ids.includes(c.id) ? 'Remove' : 'Watch', 'research-action')
    btn.type = 'button'
    btn.setAttribute('aria-label', (ids.includes(c.id) ? 'Remove ' : 'Watch ') + (c.name || c.id))
    btn.addEventListener('click', () => {
      const current = watchIds()
      setWatch(current.includes(c.id) ? current.filter(x => x !== c.id) : [...current,c.id])
      marketTable(data, filterWatch)
    })
    tr.lastElementChild.append(btn)
  }
  research.replaceChildren(heading,description)
  if (!coins.length) research.append(el('p', filterWatch ? 'No watched assets found in the current top-market snapshot. Saved IDs remain on this device.' : 'No market assets were returned.', 'research-note'))
  else research.append(table)
  research.append(el('p', data.note || '', 'research-note'))
}
async function loadMarkets() {
  notice('Loading market data from CoinGecko…')
  try {
    const data = await getJson('/api/markets?limit=100')
    marketRows = data.assets
    marketTable(data)
  } catch (error) { notice(error.message + ' Markets need the Silver Scan Python backend; a static preview cannot fetch /api.') }
}
async function loadWatch() {
  notice('Loading saved market references…')
  try {
    const data = await getJson('/api/markets?limit=100')
    marketRows = data.assets
    marketTable(data,true)
  } catch (error) { notice(error.message + ' No prices are fabricated when provider data is missing.') }
}
function showDexSearch() {
  const header = el('h2','DEX Scan')
  const desc = el('p','Search externally observed token/pair activity by token name, address, or pair. Match by network and contract, not ticker alone. Research only; not a SilvEx swap.', 'research-note')
  const form = el('form','', 'research-form')
  const input = el('input')
  input.placeholder = 'Token name, contract or pair'
  input.name = 'q'
  input.required = true
  input.maxLength = 80
  input.minLength = 2
  input.setAttribute('aria-label','DEX pair search')
  const button = el('button','Search DEX pairs')
  button.type = 'submit'
  form.append(input,button)
  const result = el('div')
  form.addEventListener('submit', async event => {
    event.preventDefault()
    result.replaceChildren(el('p','Checking DEX Screener…','research-note'))
    try {
      const data = await getJson('/api/dex/search?q=' + encodeURIComponent(input.value.trim()))
      const table = el('table')
      const tr = el('tr')
      for (const name of ['Network', 'Pair / contract', 'DEX', 'USD price', 'Liquidity', '24h volume','Source']) tr.append(el('th',name))
      table.append(tr)
      for (const pair of data.pairs) {
        const tr = rowCells(table,[
          pair.chain_id,
          (pair.base_token?.symbol || '?') + '/' + (pair.quote_token?.symbol || '?') + ' · ' + pair.pair_address,
          pair.dex_id,
          pair.price_usd,
          formatted(pair.liquidity_usd),
          formatted(pair.volume_24h_usd),
          ''
        ])
        if (pair.source_url) {
          const a = el('a','View pair')
          a.href = pair.source_url
          a.target = '_blank'
          a.rel = 'noopener noreferrer'
          tr.lastElementChild.append(a)
        }
      }
      result.replaceChildren(sourceInfo(data.source,data.fetched_at,data.stale),el('p',data.note,'research-note'))
      if (data.pairs.length) result.append(table)
      else result.append(el('p','No pairs found for this query.','research-note'))
    } catch(error) { result.replaceChildren(el('p',error.message + ' No synthetic pair data will be shown.','research-note')) }
  })
  research.replaceChildren(header,desc,form,result)
}

tabs.forEach(button => button.addEventListener('click', () => switchTab(button.dataset.tab)))
switchTab('explorer')
