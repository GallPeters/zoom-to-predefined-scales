# Zoom to Predefined Scales

A QGIS 4.0+ plugin that adds a **toggle button** to the Plugins toolbar to
lock the map canvas so that every zoom operation snaps to one of the
project's own **predefined scales** (*Project → Properties → View Settings
→ Project predefined scales*).

- 🔓 **Unlocked** — QGIS zooms exactly as it always does.
- 🔒 **Locked** — the canvas can only ever land on a scale from the
  project's predefined-scale list, however you zoom (wheel, zoom in/out
  tool, rubber-band zoom, keyboard, or a script). Zooming in always steps
  to the next smaller scale denominator; zooming out to the next larger
  one; the map centre is preserved.

The plugin never stores its own scale list and never writes to the
project — it only *reads* `QgsProject.viewSettings()` and, while locked,
adjusts the canvas.

## Repository layout

```
zoom_to_predefined_scale/          (repo root)
    README.md
    .gitignore
    src/                           everything that gets installed/packaged
        __init__.py                classFactory() entry point
        metadata.txt
        zoom_to_predefined_scale.py    toolbar/menu UI, plugin lifecycle
        settings_dialog.py             Plugins -> ... -> Settings... ("Run Tests")
        scale_lock_controller.py       lock state machine + signal wiring (the core)
        project_scales.py              reads QgsProject's predefined scales
        scale_utils.py                 pure scale-selection algorithm (no QGIS import)
        icon_unlocked.png
        icon.png                       plugin's official icon (also the "locked" state icon)
    tests/                         developer/QA test suite (not packaged separately -
                                    see "Packaging a release" below)
        __init__.py                 locates src/ and registers it as _ztps_plugin
        run_all.py                  discovers and runs every test_*.py
        _project_guard.py           snapshot/restore the live project around a run
        fakes.py                    FakeCanvas/FakeIface test doubles
        test_scale_utils.py
        test_project_scales.py
        test_scale_lock_controller.py
        test_plugin_lifecycle.py
        test_settings_dialog.py
    releases/                      zipped releases uploaded to the QGIS plugin portal
```

`src/`'s own files use ordinary intra-package relative imports (`from
.scale_lock_controller import ...`, etc.) — they don't know or care that
they currently live under `src/`. That's what makes the packaging step
below a plain flatten-and-zip with no source rewriting needed.

## Packaging a release

The QGIS plugin portal expects a zip whose root contains **one folder**,
named after the plugin, holding the plugin's files directly (no nested
`src/`). To build one:

1. Create a folder named exactly `zoom_to_predefined_scale` (call it `X`
   anywhere, e.g. next to this repo).
2. Copy everything from `src/` directly into `X/` (flattened — `X/__init__.py`,
   `X/metadata.txt`, `X/zoom_to_predefined_scale.py`, `X/icon.png`, `X/icon_unlocked.png`, ...).
3. Copy `tests/` into `X/tests/` (optional, but recommended — it's what
   makes the Settings dialog's "Run Tests" button available to whoever
   installs this build; see below).
4. Zip `X` (so the zip's root contains the single `zoom_to_predefined_scale/`
   folder) and drop it into `releases/`, e.g. `releases/zoom_to_predefined_scale-1.0.zip`.
5. Upload that zip to the QGIS plugin portal / `Install from ZIP`.

Nothing in `src/` or `tests/` needs to change for this — the import setup
described below was specifically designed to work unmodified in both the
git-checkout layout (`tests/` a sibling of `src/`) and this flattened
release layout (`tests/` nested inside the single top-level folder).

## Installation (development)

Symlink or copy `src/`'s contents (not the `src/` folder itself) into your
QGIS profile's plugins directory, under a folder named
`zoom_to_predefined_scale`:

- Windows: `%APPDATA%\QGIS\QGIS3\profiles\<profile>\python\plugins\zoom_to_predefined_scale\`
  (QGIS keeps this path under the `QGIS3` folder name across the QGIS 4
  series; check *Settings → User Profiles → Open Active Profile Folder* if
  unsure).
- Linux: `~/.local/share/QGIS/QGIS3/profiles/<profile>/python/plugins/zoom_to_predefined_scale/`
- macOS: `~/Library/Application Support/QGIS/QGIS3/profiles/<profile>/python/plugins/zoom_to_predefined_scale/`

For an end user, installing a packaged release zip via **Plugins → Manage
and Install Plugins → Install from ZIP** is simpler and does the same
thing.

Restart QGIS (or use the *Plugin Reloader* plugin during development), then
enable **Zoom to Predefined Scales** in the Plugin Manager.

## Usage

1. Configure predefined scales for your project: **Project → Properties →
   View Settings → Project predefined scales** — check *"Use predefined
   scales"* and add one or more scales.
2. Click the lock/magnifying-glass button on the **Plugins toolbar** (also
   available under **Plugins → Zoom to Predefined Scales**).
3. While locked, zoom normally. Every zoom action resolves to the nearest
   appropriate predefined scale in the direction you zoomed.
4. Click the button again to return to normal, unrestricted zooming.

### Button states

| State | Icon | Checked | Tooltip |
|---|---|---|---|
| Unlocked | open padlock | no | "Lock map canvas to project predefined scales" |
| Locked | closed padlock | yes | "Unlock map canvas from predefined scales" |
| Unavailable (scales disabled or empty) | open padlock | no | Explains why, and points at the project setting |

If you click the button while no usable predefined scales are configured,
the button stays unlocked and a message-bar warning explains why —
nothing pops up uninvited during normal use.

### Settings dialog

**Plugins → Zoom to Predefined Scales → Settings...** opens a small dialog.
For now it holds a single control: a **"Run Tests"** button (shown only
when a `tests/` folder can actually be found next to the running install —
a development checkout, or a release packaged together with its tests; a
normal end-user install without `tests/` simply doesn't show it). Clicking
it runs the plugin's own test suite and opens a separate **Test Results**
window — a coloured pass/fail summary plus the full log, with a single
**Close** button. The main QGIS window stays responsive throughout the run,
and your currently open project's predefined-scale settings are restored
afterwards no matter what the tests did.

## How the zoom interception / snap mechanism works

This is the core design decision, so it's worth spelling out precisely.

**What we deliberately did *not* do:**
- No polling timer, no busy loop.
- No event filter on the canvas viewport intercepting raw mouse/keyboard
  events. Reimplementing wheel/rubber-band/keyboard zoom math for every
  input mechanism would be fragile and would fight QGIS's own navigation
  code.
- No forcing of the scale on every render/repaint.

**What we did instead: react to `QgsMapCanvas.scaleChanged`.**

QGIS already exposes exactly the signal we need:
`QgsMapCanvas.scaleChanged(scale: float)`, emitted once whenever the
canvas's scale settles on a new value — regardless of *which* interaction
caused it (mouse wheel, the zoom-in/out toolbar tools, rubber-band zoom,
keyboard shortcuts, or a script calling `zoomIn()`/`zoomToExtent()`/etc.).
That uniformity is exactly why this is the right integration point: we
don't need to special-case each zoom mechanism.

The flow, while locked (`ScaleLockController` in
[src/scale_lock_controller.py](src/scale_lock_controller.py)):

1. The user zooms, by any means. QGIS performs its **normal** zoom
   handling completely unmodified — including its own focal-point logic
   (e.g. re-centring the view under the mouse cursor for wheel zoom, or on
   the drawn rectangle for a rubber-band zoom).
2. That normal zoom lands the canvas on some scale that generally is
   *not* one of the predefined scales. `scaleChanged` fires with that
   value.
3. Our handler compares this new scale against the last predefined scale
   the lock had settled on, to infer the zoom **direction** (a smaller
   denominator means the user zoomed in; a larger one, out) — see
   [src/scale_utils.py](src/scale_utils.py)'s `next_scale()`.
4. It computes the correct predefined scale for that direction (the
   largest predefined scale smaller than the reference when zooming in,
   the smallest one larger when zooming out; clamped at the ends of the
   list) and immediately calls `canvas.zoomScale(target, True)` —
   the same call that backs QGIS's own scale box in the status bar.
5. `zoomScale()` re-centres on the canvas's *current* centre. Since QGIS's
   own zoom (step 1) already moved that centre to the user's focal point,
   re-scaling around it preserves that focal point — we're not
   reimplementing cursor-centred zoom, we're reusing the one QGIS just
   did and pivoting the correction on top of it.

Because step 4 happens synchronously inside the `scaleChanged` handler —
before QGIS's canvas has dispatched an actual repaint for the
intermediate, off-scale extent — the correction generally supersedes it
before anything is painted, so what the user sees is one clean jump
straight to the predefined scale rather than a visible intermediate flash.

**Recursion guard.** `canvas.zoomScale()` itself emits `scaleChanged`
again (synchronously). Reacting to that would recurse forever. A single
boolean, `_applying_correction`, is set before our own `zoomScale()` call
and cleared right after (`try`/`finally`, so it always clears even on
error); the handler's very first line checks it and returns immediately
if set. This is verified directly by
`test_recursion_guard_prevents_reacting_to_its_own_correction` in
[tests/test_scale_lock_controller.py](tests/test_scale_lock_controller.py).

**Why not intercept the wheel event instead?** An event-filter approach
would let us compute the target scale *before* any native zoom happens,
avoiding even the theoretical intermediate frame — but it means
reimplementing focal-point math per input mechanism (wheel vs. rubber-band
vs. keyboard all compute their target extent differently) and fighting
QGIS's own handling instead of cooperating with it. The signal-based
approach is native, simpler, and — because of the synchronous-correction
timing above — has no visible downside in practice.

**QGIS's own (unrelated) "Lock Scale" feature.** `QgsMapCanvas` also has
`setScaleLocked()`/`scaleLocked()` — the padlock next to the scale box in
the status bar, which freezes the scale so that further "zooming" only
changes magnification. That's a different feature entirely and has
nothing to do with predefined scales. We call `zoomScale(scale,
ignoreScaleLock=True)` specifically so our own correction can never be
silently absorbed by that unrelated toggle if the user happens to have it
turned on.

## Case-by-case behaviour

| Situation | Behaviour |
|---|---|
| Predefined scales enabled, list non-empty | Locking available; zoom snaps to the list. |
| Predefined scales disabled in the project | Button shows **Unavailable**; clicking it warns via the message bar instead of enforcing anything. |
| Predefined scales enabled, list empty | Same as above — nothing to lock to. |
| Project settings changed while running | `QgsProjectViewSettings.mapScalesChanged` is re-connected on every project change and triggers an immediate re-read; availability/button state update live, no restart needed. |
| A new project is opened / the current one is closed | The plugin listens to `QgsProject.readProject`/`cleared` and re-evaluates from scratch; an active lock is released if the new project has no usable scales. |
| Scale list edited while locked | If the scale currently locked to is still in the (possibly reordered/edited) list, nothing moves. If it was removed, the canvas re-snaps to the nearest remaining scale. |
| Plugin unloaded | `teardown()` disconnects every signal the controller ever connected (canvas, project, view settings) before the toolbar/menu action is removed — no dangling handlers. |

## Limitations

- Corrections happen *after* QGIS's native zoom step completes, not
  before it: on an extremely slow canvas/heavy layer, a corrected frame
  could in principle still get painted before the correction lands. In
  practice this is not observable in normal use.
- If QGIS ever animates a zoom transition over several `scaleChanged`
  emissions (as opposed to firing it once for wheel/tool/keyboard zoom,
  which is what current QGIS versions do), each intermediate emission
  would trigger its own correction, which could look busier than a single
  clean jump. Not observed in testing against QGIS 4.2.
- The lock only affects *this* map canvas instance
  (`iface.mapCanvas()`); it does not attempt to affect other canvases
  (e.g. a Map view / 2D map decoration, print layout preview canvases).
- The plugin does not add, remove, or reorder the project's predefined
  scales — that is entirely managed in Project Properties, by design.
- The "Run Tests" button only appears when a `tests/` folder is found next
  to the install (see "Packaging a release" above); a normal end-user
  install without it simply doesn't show it.

## Compatibility

- QGIS **4.0+** only. Not tested against, and not intended for, QGIS 3.x
  (uses PyQt6/Qt6 APIs — e.g. `QAction`/`QIcon` live in `PyQt6.QtGui`,
  not `QtWidgets` as they did under PyQt5).
- Developed and verified against QGIS **4.2.1** with its bundled PyQt6.

## Development / testing

Tests are plain `unittest.TestCase`s, discovered and run via
[tests/run_all.py](tests/run_all.py). `tests/__init__.py` locates `src/`
(preferring it as a sibling of `tests/`, then falling back to `tests/`'s
own parent directory — so the exact same test files run unmodified against
either the git-checkout layout or a flattened release) and registers it
under the fixed synthetic package name `_ztps_plugin`; every test module
imports the plugin through that name (`from _ztps_plugin import
scale_utils`, etc.) rather than assuming any particular folder name.

From a shell, using QGIS's own bundled Python interpreter, run from the
repository root:

```bash
python3 -m tests.run_all
```

From the QGIS Python Console:

```python
import sys
sys.path.insert(0, r"<path to this repository>")
from tests import run_all
run_all.main()
```

Or use the plugin's own **Settings → Run Tests** button (see above) — the
same thing, from inside a running QGIS session, with a results window
instead of console output.

`qgis.testing.start_app()` is bootstrapped once, in `tests/__init__.py`,
only if no `QgsApplication` already exists — so the same test files work
both as a standalone process and from inside an already-running QGIS
session's Python console. Set `QT_QPA_PLATFORM=offscreen` to run without a
display (e.g. in CI or over SSH).

All of the above was run and passes against a real **QGIS 4.2.1** install
with its bundled PyQt6 while building this plugin — 61 tests, covering the
scale-selection algorithm, project-scale reading, the lock/unlock state
machine and recursion guard, the real toolbar/menu UI lifecycle, and the
Settings dialog's "Run Tests" button — and again after flattening `src/` +
`tests/` into a simulated release folder, to confirm the imports really do
follow the release structure rather than the repo structure.

For manual verification inside QGIS itself: open a project, enable
predefined scales with at least two entries, click the toolbar button,
and confirm scroll-wheel zooming steps discretely through the list in
both directions while panning/identify/selection tools keep working
normally; then edit the predefined-scale list live and confirm the button
updates without a restart.
