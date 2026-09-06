# The page

The browser interface of the live product, served by `src.product.web_server`.
Six screens, one document:

| path | screen |
| --- | --- |
| `/` | Home: what is new (arrivals, requests, invitations, new group posts), the people found so far, and your thoughts, groups and conversations at a glance; the introduction for a first-time visitor |
| `/thoughts` | My thoughts: every thought in one of three states; share, edit (name, field, ideas, links), share again, stop sharing, delete |
| `/people` | People: who resonates with you, across all your thoughts or one of them; a profile radar (how close, on seven axes), a radar over your own ideas (which parts of your thought each person answers), a world map (where) and a matrix (which thought); each person opens a drawer with the correspondence diagram and the ask-for-introduction composer |
| `/talk`, `/talk/<intro>` | Conversations: requests to answer, and the relay chat with each connected person |
| `/groups`, `/groups/<id>` | Groups: people around one idea; discussion, parts of the work, shared understanding, members |
| `/connect` | Connect a chat: the one address a Claude, ChatGPT, Grok or Cursor client needs |

Signed out, only Home and Connect exist; every other address opens Home.

## Files

| file | role |
| --- | --- |
| `index.html` | the frame: masthead, navigation, `#view`, footer |
| `main.mjs` | the router and every screen; pure functions of the store and a little screen-local state |
| `maps.mjs` | the drawings: radar (people overlaid on the engine's seven axes, or on your own ideas), world map, correspondence diagram (which of their ideas answers which of yours, which links are kept), heat matrix |
| `store.mjs` | the one state: `/api/product/overview` in one read, discovery and group details on demand, one slow poll while the tab is visible, one refresh after any write |
| `strings.mjs` | every sentence the page says, English only, one key per sentence |
| `session.mjs` | cookie session and CSRF bootstrap, shared by the page and the browser tools |
| `theme.mjs` | colour scheme before first paint |
| `app.css`, `tokens.css` | the stylesheet and the type/radius scale; `legal.css` styles the privacy, terms and support pages |
| `webmcp_live.mjs`, `collab.mjs`, `workspaces.mjs` | the browser WebMCP tools (`document.modelContext.registerTool`), for an agent living in the browser; they register tools and render only a status pill on the Connect screen |

Nothing in the browser matches, ranks or rescores. Every number on screen is a
number the engine returned, and every order is the engine's order.

## Why one store

The page used to be a dozen modules, each fetching on its own and telling the
others through DOM events. Sections appeared one by one as each fetch landed,
the same record was read two or three times per load, and four of the first
requests failed with 401 before the session existed. Now there is one read,
and a poll that finds nothing new renders nothing.

Typing survives a refresh: a render is deferred while a text field on the
screen has focus.

## Checks

```bash
node --check demo/ui/main.mjs demo/ui/store.mjs demo/ui/strings.mjs
python3 -m pytest -q tests/test_product_http.py tests/test_web_server_webmcp.py \
    tests/test_web_topics.py tests/test_one_scale.py tests/test_every_verdict_has_words.py
```

To see it with people in it:

```bash
python3 -m src.product.web_server --db :memory: --host 127.0.0.1 --port 8830 \
    --origin http://127.0.0.1:8830 &
python3 ops/populate_local.py http://127.0.0.1:8830 /tmp/people.json
open http://127.0.0.1:8830/
```
