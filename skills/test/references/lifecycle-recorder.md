# Recording how a surface changes

Use this when a check is about what the visitor sees happen, not the state the page ends in: a
dialog that opens, a banner that dismisses, a list that fills, a spinner, anything that mounts or
unmounts while the page loads. A final screenshot cannot see a dialog that flashed for 9ms or a
component that mounted twice.

## The recorder

Install it with `addInitScript` before navigation. A recorder attached after `goto` starts too
late: the first render is already over.

```js
await context.addInitScript(() => {
  window.__timeline = [];
  let previous = '';
  const sample = () => ({
    ms: Math.round(performance.now()),
    dialog: !!document.querySelector('[role="dialog"]'),
    loader: !!document.querySelector('[aria-busy="true"], [class*="spin"]'),
    banner: !!document.querySelector('[role="alert"]'),
  });
  const record = () => {
    const state = sample();
    const key = Object.values(state).slice(1).join('|');
    if (key !== previous) {
      window.__timeline.push(state);
      previous = key;
    }
  };
  const start = () => {
    record();
    new MutationObserver(record).observe(document.documentElement, {
      childList: true,
      subtree: true,
      attributes: true,
    });
  };
  if (document.documentElement) start();
  else document.addEventListener('readystatechange', start, { once: true });
});
```

Change the fields in `sample()` to the states the check is about; keep `ms` first, because the
change key skips it. Read the result with:

```js
const timeline = await page.evaluate(() => window.__timeline);
```

With Playwright MCP, run the same `addInitScript` through the code-execution tool before the
first navigation, then read `window.__timeline` with `browser_evaluate`.

**Do not poll instead.** An interval hides every window shorter than itself: a 300ms poll reports
nothing on a dialog that vanished for 9ms. The MutationObserver fires on every DOM change, so the
timeline sees every transition.

## What to assert

Assert on the shape of the timeline, not on one row:

- Nothing shown to the visitor disappears and returns within one page view.
- Nothing mounts twice in one page view.
- Nothing is on screen for less time than a person can read it.
- Loading states end: the last row has no loader.

```js
const flips = (field) => timeline.filter((row, i) => i > 0 && row[field] !== timeline[i - 1][field]).length;
expect(flips('dialog')).toBeLessThanOrEqual(1);   // appears once, does not blink
const shown = timeline.findIndex((r) => r.banner);
const hidden = timeline.findIndex((r, i) => i > shown && !r.banner);
if (shown >= 0 && hidden >= 0) {
  expect(timeline[hidden].ms - timeline[shown].ms).toBeGreaterThan(1500);
}
```

## Widen the window instead of racing it

A defect that lives in a 9ms gap is a race, and a check that must win a race is flaky. Hold the
loading state open so the same defect becomes reliable to observe:

```js
await page.route(/\/api\/items\//, async (route) => {
  await new Promise((resolve) => setTimeout(resolve, 2000));
  await route.continue();
});
```

Delay the request the surface waits on, not every request, or you only slow the whole page down.

## What it cannot see

**It does not survive a navigation.** The recorder lives in the page: every navigation clears
`window.__timeline` and resets `performance.now()`. A page that reloads in a loop looks, from
inside, like a series of ordinary first loads. Count navigations from the Playwright side:

```js
let navigations = 0;
page.on('framenavigated', (frame) => {
  if (frame === page.mainFrame()) navigations += 1;
});
// ...drive the flow...
expect(navigations).toBe(1);
```

**It records only the fields you gave it.** Whatever `sample()` does not read is not in the
timeline, so a clean timeline means "none of the states I chose misbehaved", never "the page is
fine". Name the states covered when reporting the check.

**It sees the DOM, not paint.** An element present but hidden by CSS counts as present. If
visibility matters, sample `getComputedStyle(el).visibility` or `el.checkVisibility()` instead.

## Prove the check can fail

Run it once where the defect is known to be present: the base build, or the branch with the fix
reverted. A timeline check that passes everywhere, including on the build that has the bug, is
measuring the wrong thing. Record that failing run beside the passing one in the report.
