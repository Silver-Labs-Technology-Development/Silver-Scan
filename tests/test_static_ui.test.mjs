import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const page = readFileSync('app/static/index.html', 'utf8')
const css = readFileSync('app/static/styles.css', 'utf8')
const explorer = readFileSync('app/static/explorer.js', 'utf8')
const research = readFileSync('app/static/research.js', 'utf8')

test('Silver Scan includes four real research/explorer views', () => {
  for (const tab of ['explorer','markets','watch','dex','mining']) {
    assert.match(page, new RegExp('data-tab="' + tab + '"'))
  }
  for (const id of ['explorer-search','view','research-view','net']) {
    assert.match(page, new RegExp('id="' + id + '"'))
  }
  assert.match(page, /Silver Labs/i)
  assert.match(page, /not SilvEx trades/i)
})

test('research modules are external; untrusted block fields never become HTML templates', () => {
  assert.doesNotMatch(page, /<script>\s*[\s\S]*?<\/script>/)
  assert.match(page, /src="\.\/explorer\.js"/)
  assert.match(page, /src="\.\/research\.js"/)
  assert.match(research, /import \{sparkline,timeSeries,dominanceRing,sentimentGauge\}/)
  assert.match(explorer, /textContent/)
  assert.doesNotMatch(explorer, /innerHTML\s*=/)
  assert.doesNotMatch(explorer, /insertAdjacentHTML/)
  assert.doesNotMatch(research, /innerHTML\s*=/)
})

test('responsive and accessible visual foundation', () => {
  assert.match(page, /<html lang="en">/)
  assert.match(page, /name="viewport"/)
  assert.match(page, /class="skip-link"/)
  assert.match(page, /aria-label="Silver Scan sections"/)
  assert.match(page, /aria-live="polite"/)
  assert.match(css, /@media\(max-width:700px\)/)
  assert.match(css, /@media\(prefers-reduced-motion:reduce\)/)
  assert.match(css, /:focus-visible/)
  assert.match(css, /#research-view\[hidden\]/)
})

test('query controls use encoded parameters and no authorization or signing flow', () => {
  assert.match(explorer, /encodeURIComponent/)
  assert.match(research, /encodeURIComponent/)
  assert.match(research, /Fear & Greed/)
  assert.match(research, /Market Dominance/)
  assert.match(research, /historical/i)
  assert.doesNotMatch(explorer, /mining\.submit|sendrawtransaction|signTransaction/)
})
