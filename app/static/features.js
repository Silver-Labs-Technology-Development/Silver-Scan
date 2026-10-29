// Interactive feature catalog. All modules are authored as source-controlled
// HTML with explicit implementation status; filters never invent values.
const search=document.getElementById('feature-search')
const filter=document.getElementById('feature-filter')
const count=document.getElementById('feature-result-count')
const empty=document.getElementById('features-empty')
const cards=[...document.querySelectorAll('[data-feature-card]')]
const groups=[...document.querySelectorAll('.feature-group')]
function update(){
  const text=search.value.trim().toLocaleLowerCase()
  const state=filter.value
  let visible=0
  for(const card of cards){
    const matches=card.dataset.query.includes(text)&&(state==='all'||card.dataset.status===state)
    card.hidden=!matches
    if(matches)visible++
  }
  for(const group of groups){
    group.hidden=![...group.querySelectorAll('[data-feature-card]')].some(c=>!c.hidden)
  }
  count.textContent=visible+' of '+cards.length+' capabilities'
  empty.hidden=visible!==0
}
search.addEventListener('input',update)
filter.addEventListener('change',update)
update()
