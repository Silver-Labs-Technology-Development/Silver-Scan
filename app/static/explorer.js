/* Silver Scan BTCS L1 explorer.
 * All RPC/provider strings flow through textContent. No HTML templates,
 * inline handlers, or untrusted HTML are inserted into the document.
 */
const view = document.getElementById('view')
const networkSelect = document.getElementById('net')
const searchForm = document.getElementById('explorer-search')
const controls = document.getElementById('explorer-controls')
const searchField = document.getElementById('q')

function make(tag, text, cls) {
  const e = document.createElement(tag)
  if (text !== undefined && text !== null) e.textContent = String(text)
  if (cls) e.className = cls
  return e
}
function panel(title, content = [], extraClass = 'card') {
  const card = make('section', undefined, extraClass)
  card.append(make('h2', title))
  for (const element of content) card.append(element)
  return card
}
function msg(message, variant = '') {
  return make('p', message, variant ? 'notice ' + variant : 'notice')
}
function button(label, callback) {
  const b = make('button', label)
  b.type = 'button'
  b.addEventListener('click', callback)
  return b
}
function actions(...buttons) {
  const row = make('div', undefined, 'card-actions')
  for (const b of buttons) row.append(b)
  return row
}
function stat(label, value) {
  const wrapper = make('div', undefined, 'stat')
  wrapper.append(make('span', label, 'label'), make('strong', value ?? 'Unavailable', 'v'))
  return wrapper
}
function grid(...cells) {
  const g = make('div', undefined, 'grid')
  for (const cell of cells) g.append(cell)
  return g
}
function table(headers, rows, onSelect = null) {
  const t = make('table')
  const head = make('thead')
  const hrow = make('tr')
  for (const name of headers) hrow.append(make('th', name))
  head.append(hrow)
  t.append(head)
  const body = make('tbody')
  for (const values of rows) {
    const tr = make('tr')
    values.forEach((value, index) => {
      const td = make('td')
      if (index === 0 && onSelect) td.append(button(String(value ?? ''), () => onSelect(value)))
      else td.textContent = String(value ?? '—')
      tr.append(td)
    })
    body.append(tr)
  }
  t.append(body)
  return t
}
function fmt(n) {
  if (n === null || n === undefined || n === '') return 'Unavailable'
  return typeof n === 'number' && Number.isFinite(n) ? n.toLocaleString('en-US') : String(n)
}
function time(ts) {
  return typeof ts === 'number' ? new Date(ts * 1000).toLocaleString() : 'Unavailable'
}
function show(...elements) {
  view.replaceChildren(...elements)
}
function currentNetwork() {
  return networkSelect.value
}
function chainQuery() {
  return '?network=' + encodeURIComponent(currentNetwork())
}
async function api(url) {
  const response = await fetch(url, { headers: {'Accept': 'application/json'} })
  let result
  try { result = await response.json() } catch { throw new Error('Explorer backend returned an unreadable response') }
  if (!response.ok) throw new Error(result?.error || 'Explorer backend unavailable (HTTP ' + response.status + ')')
  return result
}
function error(error) {
  show(msg(error.message || 'Explorer data unavailable', 'error'), actions(button('Retry overview', overview)))
}
function jsonPanel(name, data) {
  const block = make('pre', JSON.stringify(data, null, 2))
  return panel(name, [block])
}

function renderBlock(b) {
  if (!b || typeof b !== 'object') return error(new Error('Block data unavailable'))
  const content = [
    grid(stat('Block height', fmt(b.height)), stat('Transactions', fmt(b.txCount)), stat('Timestamp', time(b.time)), stat('Network', currentNetwork())),
    make('p', 'Hash: ' + fmt(b.hash), 'research-note'),
    make('p', 'Previous hash: ' + fmt(b.previousblockhash), 'research-note'),
    panel('Transactions (up to first 20)', [
      b.txids?.length ? table(['Transaction ID'], b.txids.map(txid => [txid]), openTx) : msg('No transaction IDs returned for this block.'),
      make('p','Only the first 20 transaction IDs are returned by this development explorer.','research-note')
    ]),
    actions(button('Back to overview', overview))
  ]
  show(panel('Bitcoin Silver block ' + fmt(b.height), content))
}
async function openBlock(ident) {
  show(msg('Loading block…'))
  try { renderBlock(await api('/api/block/' + encodeURIComponent(ident) + chainQuery())) }
  catch (exc) { error(exc) }
}

function renderTx(tx) {
  if (!tx || typeof tx !== 'object') return error(new Error('Transaction data unavailable'))
  show(panel('Transaction details', [
    grid(stat('Confirmations', fmt(tx.confirmations)), stat('Size (bytes)', fmt(tx.size)), stat('Inputs', fmt(tx.vin?.length)), stat('Outputs', fmt(tx.vout?.length))),
    make('p', 'Transaction ID: ' + fmt(tx.txid), 'research-note'),
    jsonPanel('Transaction data', tx),
    actions(button('Back to overview', overview))
  ]))
}
async function openTx(id) {
  show(msg('Loading transaction…'))
  try { renderTx(await api('/api/tx/' + encodeURIComponent(id) + chainQuery())) }
  catch (exc) { error(exc) }
}

function renderAddress(data) {
  if (!data || typeof data !== 'object') return error(new Error('Address index unavailable'))
  const items = (data.transactions || []).map(item => [item.txid, item.height ?? item.block_height ?? '—'])
  const total = typeof data.txCount === 'number' ? data.txCount : 0
  const controls = actions()
  if (data.offset > 0) controls.append(button('Previous', () => openAddress(data.address, Math.max(data.offset - data.limit, 0))))
  if (data.offset + items.length < total) controls.append(button('Next', () => openAddress(data.address, data.offset + data.limit)))
  show(panel('Address activity', [
    msg('Partial indexed history only. An index below the node tip or a node reorganization can change balances. Do not treat this as a complete spendable balance.', 'warning'),
    make('p', 'Address: ' + data.address, 'research-note'),
    grid(stat('Indexed unspent BTCS', data.balance), stat('Indexed transactions', fmt(total)), stat('Indexed block tip', fmt(data.indexedTip)), stat('History offset', fmt(data.offset || 0))),
    panel('Indexed transactions', [
      items.length ? table(['Transaction ID','Height'],items,openTx) : msg('No indexed transactions yet; run the bounded indexer sync locally.'),
      controls
    ]),
    actions(button('Back to overview',overview))
  ]))
}
async function openAddress(address, offset = 0) {
  show(msg('Loading address from local index…'))
  try {
    const data = await api('/api/address/' + encodeURIComponent(address) + chainQuery() + '&limit=50&offset=' + offset)
    renderAddress(data)
  } catch (exc) { error(exc) }
}

async function explorerSearch(event) {
  event.preventDefault()
  const q = searchField.value.trim()
  if (!q) return
  show(msg('Searching the selected network…'))
  try {
    const result = await api('/api/search?q=' + encodeURIComponent(q) + '&network=' + encodeURIComponent(currentNetwork()))
    if (result.type === 'block') renderBlock(result.result)
    else if (result.type === 'tx') renderTx(result.result)
    else if (result.type === 'address') renderAddress(result.result)
    else throw new Error('Unexpected lookup response')
  } catch (exc) { error(exc) }
}

async function overview() {
  const current = networkSelect.options[networkSelect.selectedIndex]
  if (current?.dataset.family !== 'utxo') {
    show(panel('Experimental EVM demo', [
      msg('Fixture only. This view is not a BTCS L2 node, block indexer, or deployed EVM network. Switch to a BTCS L1 network for live node data.','warning')
    ]))
    return
  }
  show(msg('Checking Bitcoin Silver Core and index freshness…'))
  const suffix = chainQuery()
  const results = await Promise.allSettled([
    api('/api/health' + suffix),
    api('/api/blocks/recent' + suffix + '&limit=10'),
    api('/api/index/status' + suffix)
  ])
  const [health, blocks, index] = results
  if (health.status === 'rejected') {
    error(health.reason)
    return
  }
  const h = health.value
  const idx = index.status === 'fulfilled' ? index.value : null
  const items = blocks.status === 'fulfilled' ? blocks.value : []
  const cards = [
    panel('Network overview', [
      grid(
        stat('Network', fmt(h.chain)),
        stat('Node height', fmt(h.blocks)),
        stat('Indexed block height', idx ? fmt(idx.tip) : 'Unavailable'),
        stat('Verification progress', typeof h.verificationProgress === 'number' ? (100 * h.verificationProgress).toFixed(2) + '%' : 'Unavailable')
      ),
      idx && !idx.caught_up ? msg('The local index is behind the node by ' + fmt(idx.behind_blocks) + ' blocks. Run python -m app.indexer --max-blocks 100 locally.','warning') : msg(idx?.caught_up ? 'Index tip equals the node tip at the time checked; this is not independent consensus verification.' : 'Indexer status unavailable.'),
      make('p', 'Source: locally configured Bitcoin Silver Core RPC; balances and activity are indexed views, not finality guarantees.', 'research-note')
    ]),
    panel('Recent blocks', [
      items.length ? table(['Height','Hash','Transactions','Time'], items.map(item => [
        item.height, item.hash, item.txCount, time(item.time)
      ]), openBlock) : msg(blocks.status === 'rejected' ? 'Recent blocks unavailable: ' + blocks.reason.message : 'No recent blocks returned.'),
      actions(button('Refresh node data', overview))
    ])
  ]
  show(...cards)
}

async function init() {
  searchForm.addEventListener('submit', explorerSearch)
  networkSelect.addEventListener('change', overview)
  try {
    const networks = await api('/api/networks')
    networkSelect.replaceChildren()
    for (const network of networks) {
      const option = make('option', network.name)
      option.value = network.id
      option.dataset.family = network.family
      networkSelect.append(option)
    }
    if (!networks.length) throw new Error('The backend returned no supported networks')
    await overview()
  } catch (exc) { error(exc) }
}
init()
