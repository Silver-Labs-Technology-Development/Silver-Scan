# SilverScan — Cloudflare Pages Public Viewing Alpha

**Release status:** Ready for Cloudflare Pages Git connection after CI passes and
the owner selects the correct account/project. A committed Git branch is **not**
evidence that Cloudflare has published the site.

## Intended deployment

- Repo: `Silver-Labs-Technology-Development/Silver-Scan`.
- Production branch: `main` (the canonical website source; development stays in separate worktrees and PRs).
- Cloudflare Pages project: `silver-scan` or the existing project owned by Silver Labs.
- Root directory: repository root.
- Framework: None / static site.
- Build command: none (leave empty; source HTML/CSS/JS are ready to publish).
- Build output directory: `app/static`.
- Repo Wrangler file: `wrangler.toml`, with
  `pages_build_output_dir = "./app/static"`.
- Pages advanced mode: `app/static/_worker.js` uses `env.ASSETS.fetch(request)`
  to serve static files and implements a **restricted**, read-only public API.

See the [official Pages Git integration guide](https://developers.cloudflare.com/pages/get-started/git-integration/).
**Do not create a duplicate Cloudflare project** if an appropriate existing
SilverScan project is already connected. First inspect its production branch.

### One-time Cloudflare dashboard steps

1. In Cloudflare Dashboard → Workers & Pages, open the SilverScan Pages project.
   If none exists, create a Pages project with **Connect to Git**, authorize
   access to the `Silver-Scan` repository, and choose `main` as the
   production branch. Do not select the mining pool project.
2. Verify the build output directory is `app/static`. Use the repo root and
   no build command. The site has no Python server dependency for public alpha.
3. Confirm production deployment and visit the actual URL shown by Cloudflare.
   **Never guess the Pages subdomain.** Check that `/api/alpha/health` returns
   `{"status":"alpha",...}`. This tests the Pages Function, not merely HTML.
4. In Pages → Metrics, enable **Cloudflare Web Analytics**. It measures
   aggregate page views, referrers and performance without user identifiers.
   It does *not* automatically measure each button click or portfolio content.
5. Review Pages → Settings → Variables and Secrets. Add provider keys
   **only if properly licensed for this public use**. Avoid storing secrets in
   GitHub source files or sharing them in chat. See provider permissions below.
6. Configure Cloudflare WAF/rate limiting for public `/api/*` endpoints and
   review real provider consumption/errors before publishing wider asset feeds.
   Keep main/public releases review-gated, not every draft-PR push.
7. Visit homepage, coin pages, crypto news, mining, explorer, light/dark mode,
   mobile navigation and the alpha disclaimer from an external network; check
   browser console and Pages Function logs for denied or malformed requests.

### Current public-alpha capabilities

| Capability | Public deployment |
|---|---|
| Static pages, charts layout, coin watch browser stars, navigation | Served by Pages even with your laptop powered off |
| Alpha health, source statuses, staging pool registry | Read-only Pages Function |
| Alternative.me Fear & Greed observations | Public source adapter, when upstream responds |
| CoinGecko markets, market-cap pages, quotes, provider-ID search and chart data | **Disabled until** provider rights and Cloudflare secret are set |
| Coinbase, CoinMarketCap, LiveCoinWatch provider data | Separate local development adapters; public backend integration not yet approved |
| Crypto News RSS images/headlines | UI prepared; public feed adapter not yet enabled |
| MiningPoolStats wholesale pool feed | **Not included** without an authorized dataset and appropriate license |
| BTCS Core, Solana/EVM RPC search and indexers | Local only until dedicated rate-limited read-only backend is hosted |
| Portfolio account registration/password storage | **Not public**; local prototype only |
| Trading, deposits, token creation, payout, wallet key/signing, financial writes | **Never available** in this viewing alpha |

Data that cannot be fetched should show an unavailable state. A source card
is not an indexed asset count. Do not claim 22,000+ individually verified coins,
live pool payouts, active exchange trading or working explorer RPC without
an independently audited connection.

### Optional CoinGecko public market integration

Only configure the following in **Cloudflare environment variables and
secrets**, after verifying the terms for your intended commercial/public use:

- Secret `COINGECKO_API_KEY` — valid key for the approved provider plan.
- Variable `CG_COMMERCIAL_USE_APPROVED=yes` — set only after reviewing
  commercial/public display and redistributable rights.
- Variable `COINGECKO_KEY_TIER=pro` — only for a key entitled to use
  `pro-api.coingecko.com`; omit or set `demo` for non-Pro endpoint testing
  when the provider's applicable license permits that use.

The API key stays within Cloudflare Pages Function environment bindings and
is sent as a request header, never to client JavaScript. Endpoints filter
provider IDs and limit page sizes. Upstream requests use fixed HTTPS origins.

### Monitoring and release checklist

- Cloudflare Web Analytics: page views, referrers and performance monitoring;
  no custom personal-data tracking or identification.
- Cloudflare Pages Functions metrics/logs: error rates and API activity (subject
  to Cloudflare plan and data-retention settings).
- Avoid logging URL queries containing any private information. The Explorer
  expects only public on-chain identifiers.
- Disable public `/api/account/*`, `/api/universal/search` and all writes
  until separately authenticated, authorized and security-reviewed.
- Keep `X-Robots-Tag: noindex` during alpha; switch search indexing deliberately
  after auditing information accuracy and commercial licensing.
- Deploy stable commits to `main`, not an unreviewed working branch.
  Every subsequent push to a Git-connected production branch deploys automatically
  via Cloudflare Pages; the user's computer is not part of runtime hosting.
- Keep `main` and the local repositories unmodified by release previews.
- Roll back with Cloudflare Pages deployments if an alpha change breaks service.

### How to verify a hosted release

Check the URL displayed on the Cloudflare project’s Deployments page, then:

```sh
# Replace the placeholder with the actual Cloudflare-shown URL.
curl -fsS https://YOUR-SILVERSCAN-DOMAIN/api/alpha/health
curl -I https://YOUR-SILVERSCAN-DOMAIN/
```

The first result should include `status: alpha`, and the second should show
an HTTPS response with appropriate security headers. A repository push,
successful GitHub CI or a local `127.0.0.1` preview does **not** prove that
Cloudflare is live.

### Remaining production-grade work

Provider licensing, verifiable market-data coverage, Cloudflare usage limits,
browser screenshot testing, error monitoring, independent security review,
permanent indexed chain datasets, authorized MiningPoolStats integration and
privacy-focused click analytics are separate release gates.
