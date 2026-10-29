/* Shared SilverScan light/dark appearance for independent HTML pages. */
(function(){
  const KEY='silver-scan-theme-v1';
  let mode='dark';
  try{mode=localStorage.getItem(KEY)==='light'?'light':'dark';}catch{}
  function set(value){
    const theme=value==='light'?'light':'dark';
    document.documentElement.dataset.theme=theme;
    const control=document.getElementById('theme-toggle');
    if(control){
      control.textContent=theme==='dark'?'☀':'◐';
      control.setAttribute('aria-label','Switch to '+(theme==='dark'?'light':'dark')+' appearance');
      control.setAttribute('aria-pressed',String(theme==='light'));
    }
    try{localStorage.setItem(KEY,theme);}catch{}
  }
  set(mode);
  document.addEventListener('DOMContentLoaded',()=>{
    set(mode);
    document.getElementById('theme-toggle')?.addEventListener('click',()=>{
      mode=document.documentElement.dataset.theme==='dark'?'light':'dark';
      set(mode);
    });
  });
})();
