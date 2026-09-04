# Resonance Competition Video — Draft Shot List

> **Target runtime: 2:35–2:50. Hard maximum: 2:59.**
>
> STATUS: staging draft. Every shot marked `[RELEASE CHECK]` must be replaced/verified against the frozen hosted product. Do not fake unavailable features. Real WebMCP invocation must be visibly demonstrated.

> **Judging-guidance ordering:** the working hosted product must be visible in the first 10–15 seconds, the recording starts **already signed in** on the live URL, and a **real** `document.modelContext` WebMCP invocation is shown on screen (DevTools WebMCP panel or the page's tool-status indicator visibly updating). Hard max 2:59.

## 0:00–0:15 — Working product + live WebMCP invocation (the hook)

**Visual:** open on the **live** hosted page (`https://resonance-production-cfe3.up.railway.app`), already signed in, product UI fully rendered (map + match cards, not a loading state). Immediately trigger a real browser WebMCP call — `resonance_discover` from the agent surface — and show the tool firing (WebMCP status indicator / DevTools WebMCP panel) and the map/cards updating in the same shot.

**Narration:**

> This is Resonance, running live. My agent is calling it through native WebMCP — right here in the browser — and the page updates with people whose ideas share the *structure* of mine, not just the words.

On-screen line: **Context tells you where an idea lives. Structure tells you how it works.**

`[RELEASE CHECK: this opening MUST be the real hosted product and a real WebMCP invocation — no mock, no localhost, no manual DOM edit.]`

> **Two paths, honestly separated (maintainer story correction):**
> **(A) Browser WebMCP** — competition-eligibility path, visible in-page agent tool invocation. On current `main` the browser `resonance_prepare_thought` builds from the **labelled flagship page thought**, NOT the viewer's ChatGPT conversation — the video must not imply otherwise.
> **(B) Remote MCP from a real LLM chat** — the actual cross-chat product: an external LLM client passes the *real selected conversation context* to `resonance_prepare_thought(context=…)` over remote MCP, which privately extracts Thought DNA and discovers against another independently ingested chat.
> Show **(B)** as a live segment ONLY if the R15 revision (PR #128) is accepted and deployed and independently tested before freeze. Until then, label the remote-chat capability **"pending / submitted"** on screen and in narration — do not present it as live.

## 0:15–0:38 — Private thought → explicit share

**Visual:** user-selected idea; browser agent invokes `resonance_prepare_thought`; page visibly shows PRIVATE/PREPARED. Open share preview with Thought DNA nodes/relations and consented display/location fields.

**Narration:**

> I can ask my agent to prepare this idea for Resonance. Preparation is private. Before anything becomes discoverable, I see exactly what will be shared and approve it.

**Visual:** invoke `resonance_share_prepared_thought`; consent indicator changes visibly.

`[RELEASE CHECK: real browser WebMCP tool invocation, not mocked/manual DOM]`

## 0:38–1:15 — Structural discovery

**Visual:** invoke `resonance_discover`. Map/spatial field animates. Highlight first 2–4 backend-order matches.

**Narration:**

> Now the agent calls Resonance through WebMCP. The matching engine does not use location or profile metadata to rank people. It compares the structure of the Thought DNA and returns evidence for the relationship.

Open one cross-domain card and structural comparison.

> This person may be working in a different domain, but the same causal pattern appears in both ideas. Resonance shows the mapping, not just a similarity score.

`[RELEASE CHECK: match IDs/order/scores/evidence equal authoritative live product result]`

## 1:15–1:30 — Negative / contradiction

**Visual:** dedicated contradiction/hard-rejection card or same-words/wrong-structure case.

**Narration:**

> And surface similarity is not enough. Same words with the wrong structure can score low, while a causal inversion is surfaced separately as a contradiction — never disguised as a resonance.

## 1:30–1:52 — Geography without using it for ranking

**Visual:** map / coarse distance. Optional rich visual returned on agent surface if cleanly recordable.

**Narration:**

> With permission, Resonance can also show coarse geography — useful for understanding whether someone is nearby or far away. Location is presentation only. It never changes the structural match.

`[RELEASE CHECK: coarse consented location only; small-bucket privacy rule active]`

## 1:52–2:20 — From discovery to people working together

**Visual:** request intro to one match. Target user view accepts. Open shared idea workspace. Show 3 members if the final release makes the 3-person flow clean enough; otherwise show accepted 2-person flow and mention multi-person only if actually available from live app.

**Narration:**

> Finding a person is only useful if both people want to connect. I can request an introduction, but Resonance reveals no private contact information. The other person explicitly accepts. Then we can create a shared idea room where people — and their authorized agents — continue the work with notes, tasks, messages, and artifacts.

**Visual:** add one note/task via agent; visible workspace update.

`[RELEASE CHECK: intro acceptance, workspace membership authorization, durable state, idempotent write]`

## 2:20–2:38 — What WebMCP changes

**Visual:** compact overlay or split showing browser page + discovered WebMCP tool names.

**Narration:**

> WebMCP is what turns the website into an agent-native product. Instead of an agent guessing where to click, the page exposes explicit tools with schemas, consent boundaries, and visible state changes — while the human stays in the loop.

## 2:38–2:50 — Close

**Visual:** resonance map pulls back; no fake population numbers.

**Narration:**

> This pilot starts small. The larger question is: has anyone, anywhere, reasoned like this before? Resonance is our attempt to make that searchable — and collaborative.

Logo/title: **Resonance — Shazam for human thought.**

## Recording rules

- [ ] final exported video is < 3:00; target <= 2:50;
- [ ] public YouTube visibility tested logged-out;
- [ ] English narration intelligible;
- [ ] no copyrighted music unless properly licensed;
- [ ] no secrets, tokens, private contact details, real private chats, exact locations, or unauthorized user data visible;
- [ ] browser WebMCP action is unmistakably real;
- [ ] use live hosted product for core flow; replay may appear only if clearly labeled and genuinely captured from accepted output;
- [ ] warm engine/server before recording if cold start is slow;
- [ ] avoid debug consoles unless needed briefly as evidence;
- [ ] future/network-scale language clearly says future/pilot, not current scale.

## Mandatory pre-record smoke

Record only after the exact release candidate passes:

`register/login -> prepare -> preview -> share -> WebMCP discover -> map/cards -> evidence -> intro request -> target accept -> workspace write -> restart/persistence smoke -> revoke/fail-closed smoke`

If any required release feature is unavailable, revise the script to the strongest truthful flow rather than simulating it.
