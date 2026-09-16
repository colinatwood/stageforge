# Astra checkpoint 62 validation — Chromium accessibility-tree reference qualification

Checkpoint 62 adds a real-browser semantic accessibility gate on top of checkpoint 54's rendered/responsive workflow. It does **not** claim actual screen-reader, switch-control or voice-control qualification.

## Accessibility-tree contract

At the 1440×900 reference viewport the qualification helper opens a Chromium DevTools Protocol session and retrieves the full accessibility tree after the production HTML/CSS/JavaScript and real-handler-backed API workflow have rendered. The gate requires:

- a `main` landmark;
- a focusable `Skip to stage controls` link;
- a named/focusable `Play or pause` launcher button and a named Stop button;
- a focusable BPM spinbutton with minimum 30 and maximum 300;
- a focusable Key combobox;
- named buttons for Alex, Sam, Maya and Jordan;
- at least three polite live-status regions;
- no exposed interactive control without an accessible name;
- no ignored accessibility-tree node that remains focusable.

The tree analyzer is a pure helper with regression tests so semantic failures can be caught without launching Chromium on every unit-test path.

## Reference result

The real Chromium run passes all four checkpoint-54 viewports and the new AX-tree gate:

- accessibility tree exposed nodes: **781**;
- interactive nodes: **86**;
- polite live regions: **4**;
- unnamed interactive controls: **0**;
- ignored focusable nodes: **0**;
- `accessibilityTreeReferenceQualified: true`;
- `assistiveTechnologyQualified: false`;
- `directBrowserLoopbackNetworkingQualified: false`.

The report is emitted separately from the source archive so qualification systems can retain the exact run evidence.

## Full gate

- Accessibility-tree unit regressions pass **2/2**.
- Release Python suite passes **618 tests**.
- RT native CTest passes **2/2**; native source is unchanged.
- Automation-performance passes.
- All **126 schemas plus OpenAPI** parse.
- All **7 frontend JavaScript files** pass Node syntax checking.

## Remaining

`UX-035` remains open for an actual assistive-technology exercise using at least one supported screen-reader stack and keyboard-only operator workflow, with switch/voice-control scope decided separately. The deployed browser-to-LAN/TLS/IdP path remains part of `SEC-040`.
