# SilverScan: Existing Cloudflare Workers `silver-scan` Service

The user provided the Cloudflare **Workers production service** `silver-scan`.
This is NOT Cloudflare Pages. Use this guide to deploy the public viewing
alpha into the existing Worker rather than creating a new site.

## Repository release source

- GitHub repository: `Silver-Labs-Technology-Development/Silver-Scan`.
- Production release branch: `public-alpha`.
- Existing Cloudflare Worker name: `silver-scan`.
- Production entrypoint: `app/static/_worker.js` (public read-only API).
- Static assets directory: `app/static` (HTML, CSS, JS, images).
- Wrangler config: **`wrangler.worker.toml`**, not `wrangler.toml`.
- Cloudflare's Worker assets binding is `ASSETS`.
- Worker runs before assets for `/api/*`; all other requests are served
  directly as Cloudflare static assets, with `_headers` applied.
- `app/static/.assetsignore` keeps `_worker.js` from being publicly downloadable.
- Legacy `wrangler.toml` remains available for separate Pages workflows.
  Do **not** run bare `wrangler deploy` until you've checked which config it
  selects.

## Existing Worker: Git-based Builds (recommended)

1. Open the provided Cloudflare Worker **silver-scan** → **Settings → Build**.
   Review whether it already has GitHub connected. Do not create another
   Worker or overwrite existing domain/route settings.
2. Connect the existing Worker to
   `Silver-Labs-Technology-Development/Silver-Scan` if not already connected.
3. Under **Branch control** set the **production branch** to `public-alpha`.
   Only a release commit to this branch should trigger a production update.
   Development PR changes stay on separate branches.
4. Set project/root directory to the **repository root** (if shown).
5. Build command: **none**, since this site is plain HTML/CSS/JS.
6. Deploy command: `npx wrangler deploy --config wrangler.worker.toml`.
   This identifies the existing `silver-scan` service and serves static
   assets + a restricted API in one Worker.
7. Save and trigger an approved deployment from Cloudflare's dashboard, then
   open the actual production URL shown there. Do not assume a workers.dev
   address based on the service name.

See Cloudflare's official docs:
- https://developers.cloudflare.com/workers/ci-cd/builds/configuration/
- https://developers.cloudflare.com/workers/ci-cd/builds/build-branches/
- https://developers.cloudflare.com/workers/static-assets/binding/
- https://developers.cloudflare.com/workers/static-assets/headers/

### If the existing Worker already hosts a different app

Do not blindly deploy on top of it. First review its current version, route
and bindings in the Cloudflare dashboard. A Wrangler deployment of a Worker
with the same `name` updates that Worker. Preserve/record existing Cloudflare
deployment information and keep a rollback option.

## Public release safeguards

The public Worker is intentionally **not** equivalent to the local Python
backend. It only serves allowlisted, safe read-only endpoints:

- `/api/alpha/health` — health/alpha capability details.
- `/api/sources/status` — provider permissions and connections, no fake count.
- `/api/market/sentiment` — public attributed sentiment if source available.
- `/api/mining/coins` — honest staged coin metadata, not public mining.
- CoinGecko market/quotes/chart endpoints only after
  **`CG_COMMERCIAL_USE_APPROVED=yes`** and a valid server-side
  `COINGECKO_API_KEY` Cloudflare secret are configured. This does NOT
  substitute for actually securing usage rights and respecting quotas.

Everything else fails closed with an unavailable response, especially:
- Public account registration, passwords or synchronized portfolios.
- Trading, wallets, payments, deposits or mining payouts.
- Arbitrary Ethereum/Solana/BTCS RPC access or public node admin calls.
- Unlicensed MiningPoolStats bulk data redistribution.

Visitors can browse the visible interface without owning a wallet or
providing financial details. Browser-local starred coins remain browser-only.

## One-time validation

Copy the public URL from the Worker's **Triggers/Domains** or production
deployment detail and check:

```sh
# Replace the example placeholder with the exact URL Cloudflare displays.
curl -fsS https://ACTUAL-URL/api/alpha/health
curl -I https://ACTUAL-URL/
curl -i https://ACTUAL-URL/api/account/session
```

Expected:
- Health returns `status: "alpha"` and backend details.
- Homepage returns HTTPS with the public alpha banner and security headers.
- Account endpoint returns HTTP 403 (not account details).

Then check both themes, desktop/mobile, market-source errors, Coin Watch,
News, Mining and universal explorer pages.

## Analytics

Enable Cloudflare Web Analytics on the Worker custom domain/site when
available. Monitor anonymous aggregate page visits, traffic sources, latency,
error counts and Pages/Workers request metrics. Fine-grained click analytics
require a deliberate privacy-preserving event design, user disclosure
and testing; **analytics are not enabled just because `_headers` permits
Cloudflare's analytics beacon**.

## Source key review before unlocking prices

Set keys in **Workers Settings → Variables and Secrets**, not in GitHub
commits, public JavaScript, CI logs or this guide. The market frontend will
show an unavailable state until data rights/key configuration is complete.
Do not present connector placeholders as operating providers.

## Developer workflow

Keep work and experimental changes on the development PR branch.
Publish only reviewed and tested versions on `public-alpha`. Cloudflare
Workers Builds can then deploy each production-branch push automatically,
with stable HTTPS hosting independent of the developer's computer.

GitHub tests alone do NOT confirm production is live. Verify the actual
Cloudflare deployment URL and health endpoint separately.
