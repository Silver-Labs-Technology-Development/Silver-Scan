# SilverScan: Cloudflare-first full-stack hosting

The official SilverScan source is the GitHub `main` branch of
`Silver-Labs-Technology-Development/Silver-Scan`. The live Cloudflare
Workers service is named `silver-scan`. Its deploy configuration is
`wrangler.toml` at repository root, which bundles both the Worker
(`app/static/_worker.js`) and the entire `app/static` website.

The public-facing service is not hosted by the developer's PC.

## Deployment and automatic updates

In the existing Worker service's **Settings → Builds**, connect the
`Silver-Scan` GitHub repository, choose `main` as the production branch,
use the repository root and `npx wrangler deploy` as the deployment command.
No build is needed for the original HTML/CSS/JS. Cloudflare Workers Builds
can automatically deploy each approved push to `main`; use a separate
development branch or worktree for unreviewed changes. A GitHub Actions
pass is not evidence of a successful Cloudflare production deployment:
inspect the Cloudflare deployment and actual public URL.

- Homepage: `/` or `/index.html`.
- Full market terminal: `/markets.html`.
- Coin Watch: `/coin-watch.html`.
- Exchange Directory: `/exchanges.html`.
- Mining: `/mining.html`.
- Crypto News: `/news.html`.
- Universal Explorer: `/universal-explorer.html`.
- Insights, comparison and feature catalog have their own pages.

Current read-only Cloudflare Worker routes include CoinLore ranked markets,
global observations, CoinLore asset lookup, Alternative.me sentiment,
CoinMarketCap keyless **exchange identities** and optional
entitlement-gated CoinGecko market/exchange data. The external venue list
does **not** imply a safety rating or a licensed source of transaction volumes.

## What can run on Cloudflare without leaving a PC on?

| Component | Suggested host | Readiness |
|---|---|---|
| Website and responsive visual pages | Cloudflare Worker Static Assets | Repository implementation present |
| Fixed-host market and exchange APIs | Cloudflare Worker request handlers + cache | CoinLore/CMC implemented; other provider adapters conditional |
| Source schedules, freshness and rate-limited ingestion | Cloudflare Cron Triggers and Workers | Not configured as jobs |
| Cached approved pool/network statistics | Cloudflare R2 or D1, bounded read APIs | Dataset schema supported locally; no approved public MiningPoolStats dataset connected |
| User accounts and manually entered portfolios | Cloudflare D1 plus production authentication/session service | **Not configured for public accounts**. Local Python prototype must not be exposed |
| Privacy-respecting traffic statistics | Cloudflare Web Analytics and Worker metrics | Configure in the Cloudflare account; no custom tracking turned on by Git changes |
| EVM and Solana chain observations | Worker calling fixed, rate-limited and authorized RPC/indexer APIs | Development adapters exist; public unrestricted proxy disabled |
| BTCS full node and continuous canonical chain indexer | Persistent managed node / disk-backed VPS / trusted external RPC | **Not hosted on Cloudflare Workers** |
| Index storage, network rescans and deep reorg processing | Persistent node / DB service | Requires independent deployment, backups and monitoring |

Cloudflare D1 is managed SQLite data storage for Worker applications.
R2 provides object storage. These require one-time creation and binding
using the authenticated Cloudflare account. Do not invent a database ID
or commit keys in GitHub. A properly tested authentication service is
required before enabling public user-account writes.

Cloudflare Containers support Linux processes but do not provide a
guaranteed always-on node with permanently persistent local disk. They
are not the preferred backing store for a full BTCS Core node.

## Connecting upstreams safely

- **Market data**: follow each provider's API usage and public-display
  terms. Keep source identity separate; do not sum overlapping asset totals.
- **Exchange data**: CMC keyless exchange *mapping* offers venue identities
  and tracked status, not independent exchange safety/volume metrics.
  CoinGecko metrics remain separately attributed and may require a key.
- **MiningPoolStats**: request lawful/approved dataset access before
  importing and redistributing multi-chain mining-pool rankings.
  Missing pool fee, luck, hashrate or payout data must remain missing,
  not synthetic.
- **Blockchain RPC**: issue read-only calls to fixed allowed hosts
  through server-side bindings; check expected chain IDs, rate limits,
  response sizes, confirmations and finality/reorg state.
- **Private credentials**: use Cloudflare Secrets, never browser JS,
  GitHub files or query strings.
- **Reliability**: provide source timestamps, caching and stale labels;
  fail closed for financial writes, wallet signing, trading and payouts.

## Verify the actual release

Open the Worker URL shown under Cloudflare Workers **Domains & Routes**.
Verify that `/api/alpha/health` returns `status: "alpha"`, that
`/markets.html` displays the market terminal, and that the homepage
does not present fabricated market numbers. Check
`/api/exchanges/cmc?page=1&limit=25` for attributed venue identities.

Confirm 3xx/4xx/5xx rates and upstream quotas in the Cloudflare console.
If the GitHub build passes but Cloudflare still serves old HTML, inspect
the Worker production branch and build deployment SHA. Never infer a
live deployment from GitHub alone.
