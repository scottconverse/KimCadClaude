# 02 - UI/UX Deep-Dive

## Scope

Rendered UI-v2 surfaces: landing, design workspace, Inspector tabs, My Designs, Settings, desktop and mobile.

## What's Working

- The UI-v2 flow is materially better than the stacked-card baseline: the verdict remains visible, tabs preserve context, and mobile has a direct path to export.
- Copy is generally honest about local vs cloud, simulated vs real printing, and "building" track record.
- The final Playwright pass found no horizontal overflow on desktop or mobile.

## Findings

### UX-001 - Minor - Accessibility/Responsive - Link-style controls missed the mobile touch-target floor

**Evidence:** First mobile pass showed several link-style or title-style controls under the expected touch height, while the main `.kc-btn` and design actions already had a 44px rule.

**Why this matters:** These controls appear in Settings and My Designs, where users may be on a small touch screen at a workbench.

**Fix path:** Fixed. The existing mobile touch-target rule now includes `.kc-link-btn`, `.kc-btn-sm`, `.kc-unit-btn`, `.kc-photo-affordance`, `.kc-design-name`, and `.kc-help-btn`.

## Could Not Assess

The pass used Chromium/Edge automation only; Firefox/WebKit were not exercised.
