# Driving the interface in a real browser

Mandatory for any change a person can see, and for a backend change whenever an existing screen
already shows its effect (an enabled button, a status label, a displayed limit). Green unit tests
do not replace it: they build their own fixtures and agree with themselves.

## Three tools, not interchangeable

Check which tools this session actually has before planning the pass. Search the tool list for
each prefix; do not assume one exists because it did last time.

| Tool | Use it for | Limits |
|---|---|---|
| **Playwright MCP** (`mcp__plugin_playwright_playwright__*`, or any `browser_*` Playwright tools) | Viewport measurements (phone width), repeatable live steps, network and console reads | Own browser process, so `browser_resize` is real. No user session unless a storage state is loaded |
| **Cursor in a real browser**: Claude in Chrome (`mcp__claude-in-chrome__*`) or the desktop app's browser pane (`mcp__Claude_Browser__*`) | The user's own signed-in session; the exploratory pass "like a person, with the cursor"; the odd case you think of mid-run | Resizing a real window is unreliable: tools report success while `window.innerWidth` never moves |
| **Playwright test files** in the project's e2e folder | The repeatable regression check this run leaves behind | Written after the live pass, never instead of it |

**Both MCP tools are driven live, step by step.** Call navigate, click, snapshot and evaluate
yourself and read each result. Writing a spec file first and treating a green test run as the
interface pass is not a live pass. A run that did only the live pass or only the spec is half a
run: say which half you did.

In Claude in Chrome, the `computer` tool clicks at coordinates taken from the latest screenshot.
Take a fresh screenshot after anything that moves the layout before clicking by coordinate.

**Never open the browser's own chrome**: DevTools, the device toolbar, OS dialogs, file pickers,
print dialogs. No tool reaches them reliably and a stuck dialog blocks the extension. Get the same
result another way: `browser_resize` for viewport, `evaluate`/`javascript_tool` for what DevTools
would show, network-request tools for the network panel.

## Before you open anything

**Serve the branch on the port the identity provider redirects to.** Read the redirect and callback
URLs from the dev env file (site URL, post-login redirect, post-logout redirect). On any other port
sign-in never completes: the provider sends the browser back to the configured port, which serves
nothing or somebody else's build, and the page sits at the login screen with no error. The usual
symptom in the dev server log is a login route answering a redirect and no callback afterwards.

If that port is taken by the user's own process, say what is running there and ask before stopping
it. Give them the command that brings it back and put it in the report's environment section.

Point the branch's env file at the backend you just built, not at whatever was already running.

## Signing in

**Never type a password, a one-time code or any other credential.** When a page needs a session:

- In a real browser: open the page, let the sign-in screen appear, and ask the user to sign in
  in that browser. Then continue.
- For Playwright: ask the user to put test credentials in the dev env file the e2e suite reads.
  Name the exact variable and the exact file. Never ask for secrets in chat, never print values;
  check presence with `[ -n "$VAR" ]` (see `environments.md`).

Do not script the identity provider. Accounts differ (email code, SSO, passkey) and a script
written for one waits forever on another. When you need a stored session, wait on the session
cookie, not on a redirect. Cookies ignore the port: a session set on one localhost port is sent to
every other, which explains redirects that look wrong.

## Driving it

**Wait for hydration before every click.** Many pages render a spinner or a static shell while they
resolve the session. A click in that window hits nothing, the next screenshot looks unchanged, and
it reads exactly like a broken control. Screenshot, confirm the control is there, then click.

**Map the surface before touching it.** Before the first click, list every control on every screen
the change touches (buttons, links, menu items, fields, the ones that appear only in a state you
must reach). Read the component source for the list; do not infer it from a screenshot. Without the
map you cannot notice a missing control. Put the map in the report.

**Scroll. The viewport is not the page.** Banners, second save steps and validation messages live
below the fold. Before concluding a control is absent or an action did nothing:

```js
// If unseen > 0, you have not seen the whole page.
({ windowHeight: window.innerHeight,
   pageHeight: document.documentElement.scrollHeight,
   unseen: document.documentElement.scrollHeight - window.innerHeight })
```

Scroll to the bottom and look, or read the full accessibility tree, which does not stop at the fold.

**Two-step saves are the norm.** A dialog that closes is not a write. Confirm the write reached the
server: a version or timestamp that moved, a history entry, a fresh read after reload.

**Exercise the write path, not the render.** A page that loads proves routing and layout. Saving is
where environment-specific defects live: an identifier shape tests never produced, a header a proxy
drops, a validation rule only the real store violates. Change something, save it, read it back from
the server or the store.

**Read all three failure surfaces and quote them:**

| Surface | Gives you |
|---|---|
| The toast or inline error on the page | What the user is told, often only "could not save" |
| The dev server log | Method, path, status: `PATCH /api/items/42 400` |
| The service log, and the store itself | The reason, and the actual value that was rejected |

A report that carries only the first did not diagnose anything.

## Test like a QA engineer, not like a demo

The happy path proves the screenshot in the ticket. Spend most of the pass around it, and report
which cases you ran:

| Case | What to do |
|---|---|
| Same button twice | Double-click every submit; click again while the first request is in flight |
| Click before ready | Click during load, before hydration, before a list fills. The control must be absent or inert |
| Back and forward | Back after a submit, then forward. A stale page must not create a second entity |
| Reload mid-flow | Refresh at each wizard step. Does the draft survive, does the step know where it is? |
| Empty and maximum | Submit empty; fill each field to its limit and one past it |
| Whitespace and paste | Only spaces, a trailing newline from paste, an emoji, a right-to-left string |
| Abandon | Start, navigate away, come back. State is gone or complete, never half-applied |
| Two tabs | Same entity edited in two tabs. The second write must conflict, not silently win |
| Keyboard only | Tab to the control, press Enter. A div posing as a button fails here |
| Slow and broken network | Throttle; fail one request. The screen must say what happened, not spin forever |

Judge every case that fires against the base build too: an old defect is a finding, but not this
change's finding.

## Mobile is part of every interface check

Check every touched surface at **390x844** and at the desktop width. Do the resize in Playwright
MCP, then verify instead of trusting the tool's success message:

```js
// browser_resize({ width: 390, height: 844 }), reload, then:
window.innerWidth  // must read 390
```

Reload after resizing: load-time device checks do not re-run on resize. A plain resize is not full
device emulation (no touch, no mobile user agent), which is enough for the checks below. If the
mobile pass ran without the user's session, say so.

Three things fail on a phone and nowhere else. Measure them:

- **No sideways scroll.** `document.documentElement.scrollWidth` equals `window.innerWidth`. Wide
  tables and code blocks scroll inside their own container, not the page.
- **A lone element on its line is centred.** Equal gaps left and right.
- **Nothing the visitor needs is covered** by sticky bars, bottom navigation or cookie banners.

```js
const W = window.innerWidth, H = window.innerHeight;
const els = [...document.querySelectorAll('a, button, input, select, textarea, [role=button]')];
const offCentre = els.map((e) => ({ e, r: e.getBoundingClientRect() }))
  .filter(({ r }) => r.width > 0 && r.width < W - 40)
  .filter(({ r }) => Math.abs(r.left - (W - r.right)) > 12)
  .map(({ e, r }) => ({ text: (e.innerText || e.name || '').slice(0, 30),
                        left: Math.round(r.left), right: Math.round(W - r.right) }));
const covered = els.map((e) => ({ e, r: e.getBoundingClientRect() }))
  .filter(({ r }) => r.width > 0 && r.top >= 0 && r.bottom <= H)
  .filter(({ e, r }) => {
    const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    return top && !e.contains(top) && !top.contains(e);
  })
  .map(({ e }) => (e.innerText || e.name || e.tagName).slice(0, 30));
({ pageScrollsSideways: document.documentElement.scrollWidth > W, offCentre, covered });
```

`offCentre` lists candidates, not verdicts: inline elements sharing a line are expected to be off
centre. `covered` only checks elements in the current viewport; scroll and run it again.
Report the widths you measured at. A report naming one width has tested one width.

## Media and caching

An image whose URL resolves to nothing renders nothing, and nothing does not throw. Measure every
image the surface should show, not just the one in the screenshot:

```js
[...document.querySelectorAll('img')].map((img) => ({
  src: img.currentSrc || img.src,
  loaded: img.complete && img.naturalWidth > 0,
}));
```

Cross-check the network log: a 4xx or 5xx on any asset is a fail whatever the DOM says. Known
failure modes:

- **Unconfigured remote image host.** Image optimisers refuse sources outside their allow list;
  the result may be a full-page error overlay, not a broken tile.
- **Valid URL, missing file.** The record carries a well-formed storage URL and the object was
  never uploaded or seeded. The request answers 404.
- **Signed URL expiry.** A signed URL carries its own expiry; a cached copy past it starts failing
  though the file never changed. Fetch a fresh signed URL from the API rather than reusing one.

**Caching hides both the defect and the fix.** A browser that cached a 404 keeps showing it broken
after the fix; one that cached a success keeps showing it fine after the file is gone. Reload with
the cache disabled or in a fresh context before concluding either way.

**"It still looks the same" names a layer, not a verdict.** Walk the layers in order: the file on
the branch, the file the origin serves, the optimiser's output, the CDN or edge, the browser. Say
which one holds the stale copy. Edge response headers (`x-cache`, `age`, `cache-control`) say
whether it was a hit. No browser refresh fixes a stale edge.

- **Fetch the variant the browser fetches.** Responses with `Vary: Accept` keep separate entries
  for `*/*` and `image/avif,image/webp,...`; high-density screens take the 2x `srcset` entry.
  Send a browser `Accept` header and check every width actually requested.
- **Same URL means the cache cannot miss.** Replacing a file in place without changing the URL
  (or the width bucket an optimiser keys on) leaves every cache serving old bytes until `max-age`
  runs out. Change the URL, or expect `max-age` to decide who sees the fix.

## Evidence to keep

Screenshot every step that changes state: the surface before, the control used, the result, and
the server-side read afterwards. A PASS on an interface check without a screenshot is an assertion,
not evidence. For transient states (something that flickers or mounts twice) use the recorder in
`lifecycle-recorder.md`.
