# Spec: Profile Page Design

## Overview
This step upgrades the basic Step 04 profile layout into a polished, production-grade design using the "Refined Financial Ledger" aesthetic direction. The static hardcoded data from Step 04 remains unchanged — this step is purely a visual redesign. Key changes: a two-column lower grid (transactions left, category breakdown sidebar right), an avatar with a faint ring halo, stat cards with animated accent left-borders, breakdown bars that animate in on page load via CSS keyframes, and a subtle radial-gradient wash in the hero corner. The goal is to lock in a premium visual design before wiring up live data in Step 06.

## Depends on
- Step 04: Profile page (template and route must already exist)

## Routes
No new routes.

## Database changes
No database changes.

## Templates
- **Modify:** `templates/profile.html` — full redesign of the page structure and class names:
  - Hero: add `.profile-eyebrow` label, `.avatar-wrap` + `.avatar-ring` halo, `.profile-meta` combining email + member-since
  - Stats: keep 3-card row; add `.stat-card--primary` on Total Spent, add `.stat-value--word` variant for text values
  - Lower layout: replace two stacked `.profile-section` cards with `.profile-columns` two-column grid
  - Breakdown: add `--delay` CSS variable to each `.breakdown-bar` for staggered animation; show `breakdown-figures` (amount + pct) side by side

## Files to change
- `templates/profile.html` — restructure HTML with new class names (see design output above)
- `static/css/style.css` — replace existing profile CSS block with redesigned version

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never string-format SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values in `profile.html`
- All templates extend `base.html`
- No inline styles in HTML except CSS custom properties (`--bar-w`, `--delay`) on breakdown bars
- Category badges, dots, and bars must use CSS class, never inline colour
- Breakdown bars must start at `width: 0` and animate to `var(--bar-w)` via `@keyframes bar-fill`
- Two-column `.profile-columns` grid collapses to single column at ≤ 900px
- Stats row collapses to single column at ≤ 600px
- `font-variant-numeric: tabular-nums` on all monetary and numeric values

## Definition of done
- [ ] Visiting `/profile` while logged in returns HTTP 200
- [ ] Hero section shows avatar circle with faint ring, eyebrow label, name, and combined email/member-since line
- [ ] Stats row shows three cards; "Total Spent" card has green left border (`.stat-card--primary`)
- [ ] At ≥ 901px viewport, transactions and category breakdown appear side by side in two columns
- [ ] At ≤ 900px viewport, the two sections stack vertically
- [ ] Breakdown bars animate from 0 to their target width on page load with staggered delay
- [ ] Each breakdown row shows both the category amount and percentage on the same line
- [ ] Transaction rows highlight on hover
- [ ] No hex colour values appear in `profile.html`
- [ ] Page is visually consistent with the existing Spendly design system (same fonts, same colour tokens)
