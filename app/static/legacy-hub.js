// Preserve old bookmarked Coin Universe links after the product page split.
const hash=location.hash;
const destination=hash==='#news'?'./news.html':
  (hash==='#mining'||hash==='#pool-sources')?'./mining.html':
  './coin-watch.html';
const suffix=destination.endsWith('coin-watch.html')?location.search:'';
location.replace(destination+suffix);
