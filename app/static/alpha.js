/* Public SilverScan alpha disclosure. Local Python previews are unaffected.
   Public accounts are disabled until a secure hosting/auth review is complete.
   No visitor IDs, fingerprints, tracking cookies or personal data collected. */
(() => {
  const local = ["localhost","127.0.0.1","::1"].includes(location.hostname);
  if (local) return;
  document.addEventListener("DOMContentLoaded",() => {
    const bar=document.createElement("div");
    bar.className="public-alpha-banner";
    bar.setAttribute("role","status");
    const tag=document.createElement("strong");
    tag.textContent="PUBLIC ALPHA";
    const text=document.createElement("span");
    text.textContent="SilverScan is under active development. Market quotes are third-party observations; some services aren't connected yet. No trading, deposits, or wallet access.";
    bar.append(tag,text);
    const skip=document.querySelector(".skip-link");
    if(skip?.parentNode)skip.parentNode.insertBefore(bar,skip.nextSibling);
    else document.body.prepend(bar);
    const auth=document.getElementById("portfolio");
    if(auth){
      auth.querySelector("#account-auth")?.setAttribute("hidden","");
      auth.querySelector("#account-portfolio")?.setAttribute("hidden","");
      const banner=document.getElementById("account-message");
      if(banner){
        banner.textContent="Public accounts and synced portfolios are not enabled on this alpha. Coin Watch's browser-local stars work, and the manual account prototype is available only in the local development server.";
        banner.className="hub-note alpha-account-disabled";
      }
      const section=auth.querySelector(".hub-head h2");
      if(section)section.textContent="Portfolio accounts — coming in a future alpha";
    }
    const title=document.title;
    if(!title.includes("Alpha"))document.title=title.replace("— SilverScan","— SilverScan Alpha");
  });
})();
