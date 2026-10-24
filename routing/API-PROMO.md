# API promotional routing — guarded API-only jobs

Public setup requires explicit [local inputs](../docs/LOCAL-SETUP.md).
Named API choices below are supported technical examples, not installed selections.

Fresh text-only independent reviews use `api-fable` →
`anthropic-promo/claude-fable-5-1#high`. Explicit API-only jobs use `api-opus` →
`anthropic-promo/claude-opus-5-5`. `api-haiku-proof` is proof-only and accepts exactly
“Reply OK only.” No subscription fallback, bulk routing, tools, goals, continuation,
warm-up or helper-owned inference loop. Caller text is limited to32768 UTF-8 bytes.

Native residual risk requires explicit owner acceptance with an existing Console spending
backstop and exclusive key. This kit does not configure that backstop. The
approval/reference and verified baseline belong only in private runtime authority.
Direct manual provider use bypasses Runway accounting and is NOT budget protected.

## Accounting and limitations

Separate SQLite `promo.sqlite3`: operator-configured promo grant and 90%
spent+held+new-reservation stop; BEGIN IMMEDIATE admission, integer micro-USD,
unique attempts and receipts. No default grant is asserted.
Practical per-job estimates: Fable$17 (≤32,768/HIGH), Opus$6, Haiku proof$1. These are conservative
estimates, NOT hard total native liabilities. Fable estimate allows roughly128k
cache-creation-price input plus8192 output+reasoning per attempt across four attempts
(Fable $11.8784, Opus $4.75136 at128000 input tokens/attempt);
Opus similarly conservative. Caller input is tiny, but runtime assembly is larger.
Deny tools, explicit title, and request `max_tokens`8192 (Haiku32) reduce
amplification, not a claim to prove title/retry/warming/auxiliary traffic absent.
Console backstop covers the principal-accepted residual risk; local accounting is
NOT a provider balance and cannot see invisible/outside usage.

Actual runtime receipts separate `output` from `reasoning`. Both are REQUIRED
nonnegative integers (no booleans); bill their sum at the output rate. Input excludes
cache; cache read/write use separate rates. This is a local price estimate, not an
invoice. A synthetic Fable example with input4/output0/reasoning2048/cachewrite10445/
cacheread0 estimates311340microUSD (including102400 reasoning). Do not replay
settlements or corrections from examples; retain original receipts and provenance.

The fresh single-turn review agent deliberately omits `steps`. Native SessionRunner
behavior with `steps:1` appends an assistant maximum-steps
instruction on the FIRST request, rejected by this Anthropic model as unsupported
prefill. Raising steps is not a second-request workaround. Natural text-only completion
is expected; no tools, goals, autonomous continuation or automatic resend is allowed.
This does not establish a hard whole-native-request bound; the Console-backed
residual-risk acceptance and local reserves/90% stop remain required.

Prepare atomically writes job digest/reservation. Bind validates exact native
session metadata, model/variant, agent, location and empty history. Prompt state is
durably claimed BEFORE the only send. Unknown creation/send results never trigger
automatic resend or reservation release. Collect is caller-session-scoped, checks
idle/inbox/permissions/forms and all message pages (bounded20pages), validates the
one user's metadata/text digest, then records actual native assistant token receipts
and settles their priced usage idempotently. Errors/retries/missing usage/tool or
compaction traffic keep the full hold. Multiple clean assistant receipts are summed.
Incomplete native auxiliary usage remains a disclosed estimate limitation, not
silently assumed zero. Bound estimate exceedance freezes further admission.

Unknown holds survive rollover. The configured UTC renewal day is a local accounting
convention, NOT a provider timestamp. Every new cycle requires renewed private
authority/baseline confirmation; no automatic grant is fabricated.
CREDIT promo shows grant/spent/held/remaining/expiry and BURN within
3days. BURN/prefer cannot override cap or purpose. Paid loaded credits are never
counted. Existing percent quotas/routes/ledger are untouched.

## Public evidence

Normally retrieved with webfetch on2026-10-23:
- https://opencode.ai/v2/docs/config — `{file:~/.chief-of-staff/secrets/anthropic-api.key}`.
- https://opencode.ai/v2/docs/providers — canonical/package/settings, variants list,
  body overrides, timeout retries. Ordinary `@opencode/ai/providers/anthropic`, no
  custom transport/provider/hooks/daemon/SDK patch. Existing bridge/defaults remain.
- https://platform.claude.com/docs/en/about-claude/pricing — global standard
  USD/MTok input/output/1h-cache-write/hit: Fable10/50/20/.25; Opus4/20/8/.20;
  Haiku conservative >100k tier .50/2.50/1/.05 (<=100k .10/.50/.20/.01).
  Cache writes use1h maximum when TTL unavailable. Fast/residency/server tools/batch
  unsupported; no claim these estimates equal a live Console balance.

Retained native2.1.3 OpenAPI inspected for `Config.AgentEncoded.steps`,
provider/model settings, `Model.Ref`, session create/prompt, paginated messages,
`Session.Message.Assistant.tokens`/`TokenUsage.Info`. Native stateless generate
returns text only and is NOT used for usage proof. Frozen mock report is untouched.

## Parent-released installation (do NOT run before review)

Use this candidate's Python entrypoint for the proof; the existing live plugin/launcher
need not be repointed or rebuilt. Canonical integration/publication belongs to parent.
The installer only adds provider+agent, top-level `api_routes`/`promo` metadata and
new separate counter. Existing defaults/providers/bridge/policies/unknown fields and
JSONC comments/formatting are byte-preserved by scoped insertion. Collisions abort.
No existing config/auth/key contents are printed or copied to a backup. Private
rollback receipt stores only inserted fields, positions, hashes and original modes.
Explicit file target avoids global config discovery. No secret substitution happens
in installer code; only the native runtime reads the key later.

First configure the three local files described in Local setup above. Parent then
creates a private0600 JSON approval file (outside source) with:
`console_backstop:true`, `exclusive_key:true`, `baseline_micro_usd:0`,
`reference:<owner approval reference>`, `verified_cycle:<confirmed current accounting cycle ID>`.
The current cycle ID is an accounting label, not a provider renewal instant.

From the kit root (choose the actual existing JSON or JSONC config;
do not create a second sibling):

```sh
python3 scripts/install-api-promo.py --config "$HOME/.config/opencode/opencode.jsonc" --runway-home "$HOME/.chief-of-staff/runway" --approval-file "$HOME/.chief-of-staff/runway/promo-approval.json"
```

Dry-run is default. It emits only scoped entry names, not existing config values.
After review, repeat the same command with `--apply`. It serializes installers,
checks preimage/mode, journals before writes and uses fsync+atomic file replacement.
Interrupted multi-file installation is recoverable via the scoped receipt; not
claimed to be a cross-file filesystem transaction. No service/account changes.

Rollback (postimage/mode must still match; otherwise no config writes):

```sh
python3 scripts/install-api-promo.py --runway-home "$HOME/.chief-of-staff/runway" --rollback --apply
```

Rollback revokes local authority and restores only inserted bytes; preserves counter,
holds, receipts and journal. It never destroys unknown money liability. An install
cannot be blindly repeated over an existing counter/receipt. Parent reconciles it.

## Existing-install amendment (parent review/apply only)

Legacy `steps:1` can fail HTTP400 (unsupported assistant prefill), without a
token receipt. Do not manufacture zero usage or reuse a failed session as proof.
Corrected tiny reruns and normal useful API request counts within the authorized
local 90% stop require the operator's authority, not a universal approval. Unknown usage still
retains its hold unless explicitly reconciled with owner authority and provenance;
that reconciliation is not a native token receipt.
No blind automatic retries: each send remains explicitly prepared/claimed once.

For the already installed provider/agent, **do not reinstall or roll back**. From
this candidate, choose the exact original config path:

```sh
python3 scripts/install-api-promo.py --amend --config "$HOME/.config/opencode/opencode.jsonc" --runway-home "$HOME/.chief-of-staff/runway"
```

Default is read-only dry-run. Parent reviews then repeats with `--apply`. No approval
file is needed or read. This exact amendment reconstructs original bytes in memory
from `promo-install.json`, verifies both installed postimages/modes and the exact
owned legacy2048 snippet (with or without steps:1), then resplices the reviewed
8192 snippet without steps. Haiku32 and every other provider/agent field must match;
no general update or foreign value copying is allowed. Only config
and insertion receipt change; original preimage hash/mode and routes receipt remain.
No routes rewrite, database access, hold settlement, authority change or service action.

Private0600 `promo-amend.json` contains only old/new insertion receipts (owned inserted
bytes, offsets and hashes, never unrelated config values). It precedes replacements.
If interrupted, run the same dry-run to inspect resumability, then parent may repeat
`--apply` to finish forward only when exact old/new postimages and modes still match.
Otherwise stop for parent review; no blind rollback. Ordinary rollback refuses while
this journal exists. It is removed after the updated install receipt is durable; the
updated receipt still supports original insertion-only rollback if later authorized.

## Scoped native plugin Python deployment (parent only)

The installed `dist/runway/cli.py` and `dist/WORKFLOW.md` predate unrelated source
host-dispatch work. Do NOT copy whole source CLI/workflow or rebuild/reload index.js.
`scripts/install-api-promo-plugin.py` pins exact installed SHA256/mode0644 preimages,
inserts only API CLI branches/error sanitation, adds promo.py/promo_native.py and
appends only the API workflow section. No ledger/quota/default/config/JS changes.
Its private receipt contains hashes/modes only. Source changes after deployment
refuse rollback; retain this commit to recover. Interrupted apply/rollback accepts
only exact old/new images; third-party edits refuse before writes.

```sh
python3 scripts/install-api-promo-plugin.py --dist /path/to/chief-of-staff/dist
# Parent reviews exact API delta, then same command --apply.
# Rollback preview: same command --rollback; parent may add --apply.
```

After parent installation, one ordinary Runway status readback should show CREDIT.
That readback is not inference or a plugin reload. Chief-runway already uses canonical
source; this helper addresses only the native tool's Python dist seam.

## Tiny real Haiku proof under parent standing authority

Do not run during source building. No key/models/auth probe. Use supported native
CLI auth; helper never reads registration/password/env credentials. Requests use
the existing host. No helper waits for inference; `/prompt` is native async. After
an uncertain create/prompt, STOP sending and retain hold, never repeat the command.

1. From the candidate, prepare (no inference) with the approved directory:

```sh
python3 runway_main.py <<'JSON'
{"action":"promo-prepare","task":{"attempt":"promo-haiku-proof-example","route":"api-haiku-proof","purpose":"proof","directory":"/path/to/project","text":"Reply OK only."}}
JSON
```

2. `native_create` contains the exact native body; create once:

```sh
opencode api post /api/session --data '{"title":"API promo review","agent":"api-promo-review","model":{"providerID":"anthropic-promo","id":"claude-haiku-5-5"},"location":{"directory":"/path/to/project"},"metadata":{"promo_attempt":"promo-haiku-proof-example"}}'
```

3. Bind returned native ID (replace `ses_RETURNED`):

```sh
python3 runway_main.py <<'JSON'
{"action":"promo-bind","attempt":"promo-haiku-proof-example","session":"ses_RETURNED"}
JSON
```

4. Claim the single prompt durably, then execute the returned native prompt ONCE:

```sh
python3 runway_main.py <<'JSON'
{"action":"promo-claim-send","attempt":"promo-haiku-proof-example","text":"Reply OK only."}
JSON
opencode api post /api/session/ses_RETURNED/prompt --data '{"text":"Reply OK only.","metadata":{"promo_attempt":"promo-haiku-proof-example"}}'
```

5. After native session becomes idle, collect actual assistant token receipts:

```sh
python3 runway_main.py <<'JSON'
{"action":"promo-settle","attempt":"promo-haiku-proof-example"}
JSON
python3 runway_main.py <<'JSON'
{"action":"promo-status","format":"json"}
JSON
```

Settlement is safe to repeat; dispatch/prompt is NOT. Pending/unknown keeps holds.
Record native assistant IDs/tokens and local observed/accounted micro-USD before/after.
No stateless generate or automatic client retries. Further useful requests remain
lead-owned within authorized limits, each with a fresh attempt and reservation. Alternative
`promo-dispatch` performs create/bind/single async prompt; `promo-send` sends an
already-bound prompt. Both use normal `opencode api`, no new transport or wait loop.
The25s plugin timer may interrupt a slow helper; persisted states/holds survive and
collection is safe, never blindly resend. Explicit native commands above avoid that
timer for the parent proof. Real Fable Tower review follows only after accepted proof.
# Current Fable bound and cancellation

See [Fable headroom](FABLE-HEADROOM.md) for the final $17 reserve,
operator-owned ≤32,768/HIGH prerequisite and atomic unsent cancellation.
Historical rollout instructions below do not automatically migrate local inputs.
