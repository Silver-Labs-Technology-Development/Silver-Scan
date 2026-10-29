import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const theme = readFileSync('app/static/theme.css','utf8')

function luminance(color){
  const hex=color.replace('#','')
  assert.match(hex,/^[0-9a-fA-F]{6}$/)
  const rgb=[0,2,4].map(i=>parseInt(hex.slice(i,i+2),16)/255)
    .map(c=>c<=.04045?c/12.92:((c+.055)/1.055)**2.4)
  return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722
}
function contrast(foreground,background){
  const a=luminance(foreground),b=luminance(background)
  return (Math.max(a,b)+.05)/(Math.min(a,b)+.05)
}
function variable(section,key){
  const match=section.match(new RegExp(key+':(#[0-9a-fA-F]{6})'))
  assert.ok(match,'Missing '+key)
  return match[1]
}
const dark=theme.split('html[data-theme=dark]')[1].split('html[data-theme=light]')[0]
const light=theme.split('html[data-theme=light]')[1].split('body{')[0]

test('light and dark mode primary and secondary text meet WCAG AA contrast',()=>{
  for(const [name,block] of [['dark',dark],['light',light]]){
    const panel=variable(block,'--panel')
    const text=variable(block,'--text')
    const secondary=variable(block,'--muted')
    const bg=variable(block,'--bg')
    const accent=variable(block,'--brand')
    for(const [role,fg,bgColor] of [
      ['primary/panel',text,panel],['secondary/panel',secondary,panel],
      ['primary/page',text,bg],['accent/panel',accent,panel]
    ]){
      const ratio=contrast(fg,bgColor)
      assert.ok(ratio>=4.5,name+' '+role+': '+ratio.toFixed(2)+':1 < 4.5:1')
    }
  }
})

test('call-to-action and selected critical status colors meet contrast',()=>{
  for(const [name,fg,bg] of [
    ['button text','#102a43','#a6e0ff'],
    ['dark good','#8ee9c9','#1b344b'],
    ['dark warning','#ffb0b5','#1b344b'],
    ['hero text','#f3faff','#153552'],
    ['light news link','#153149','#ffffff']
  ]){
    assert.ok(contrast(fg,bg)>=4.5,name+' fails WCAG AA readability')
  }
})

test('important content panels are opaque and theme states are explicit',()=>{
  assert.match(theme,/html\[data-theme=dark\]/)
  assert.match(theme,/html\[data-theme=light\]/)
  assert.match(theme,/\.hub-main-panel/)
  assert.match(theme,/opacity:1/)
  assert.match(theme,/:focus-visible/)
})
