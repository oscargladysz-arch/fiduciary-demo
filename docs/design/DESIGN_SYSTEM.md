# Tark design system

Cloud session, round 3 (R3-P1-5 and R3-P1-6). This document and the
`#/design` route are the approval surface for the design checkpoint
(decision 8.2). The rule set it answers to is the pinned copy of Vercel's
Web Interface Guidelines, `docs/design/web-interface-guidelines_2026-09-07.md`.
Source of truth for every value: `web/src/design/tokens.css`. A gate fails
the build when a color, font size, spacing, radius, shadow, border width or
duration literal appears anywhere else in the built CSS or JS.

## 1. Tokens

### Color

One brand accent, the plum, kept from the current site and re-tuned so
every text use passes 4.5:1 and every non-text use passes 3:1 in both
themes (every pair below was computed with the WCAG 2 formula and is in
the checkpoint table, section 6).

| Token | Light | Dark | Use |
|---|---|---|---|
| `--ink-800` (`--text`) | `#262130` | `#ece8f1` | primary text, 14.8:1 on paper |
| `--ink-600` (`--text-2`) | `#564f61` | `#b9b2c3` | secondary text, 7.4:1 |
| `--ink-500` (`--text-3`) | `#6b6476` | `#9b94a6` | captions and tertiary text, 5.3:1 (the current caption color failed at 4.05:1) |
| `--ink-400` | `#8a8394` | `#8a8394` | non-text only (axes, dividers), 3.7:1 |
| `--ink-300` to `--ink-50` | lines and fills | inverted | hairlines, soft fills |
| `--paper` | `#faf8f5` | `#16121c` | the page |
| `--panel` | `#ffffff` | `#1f1a27` | cards, tables, drawers |
| `--accent-700` (`--accent`, `--link`) | `#593380` | `#c5addf` | text and primary actions, 9.5:1 |
| `--accent-500` (`--accent-nontext`) | `#8961b6` | `#a685cc` | borders and icons, 4.7:1 |
| `--focus` | `#2f5fd0` | `#7ea2ff` | the focus ring, a blue so it stays visible on plum, 5.7:1 |
| `--alarm` | `#9d2f26` | `#f08c83` | escalations and errors, 6.9:1 |

Semantic pairs, each a foreground on its background, tested at the 12 px
chip size (4.5:1 required, every pair passes, lowest 4.87:1 light and
5.81:1 dark):

| Status or verdict | Light fg on bg | Dark fg on bg |
|---|---|---|
| structured (T1) | `#1f4e5f` on `#e2eef2` | `#a9d3e2` on `#12303a` |
| extracted, unverified (T2) | `#256e46` on `#e5f2e9` | `#a6dcb8` on `#123a25` |
| verified (T3) | `#ffffff` on `#256e46` | `#0f2a1a` on `#8fd3a6` |
| computed | `#14636d` on `#e0eef0` | `#9fd8de` on `#0f3339` |
| partial | `#8a5a08` on `#f8efdd` | `#f0c977` on `#3d2a05` |
| not applicable | `#6b6476`, dashed border, no fill | `#9b94a6` |
| adviser input | `#593380` on `#efe9f7` | `#d7c3ec` on `#3a2554` |
| aligned | `#256e46` on `#e5f2e9` | `#a6dcb8` on `#123a25` |
| conditional | `#8a5a08` on `#f8efdd` | `#f0c977` on `#3d2a05` |
| conditional, weak | `#8a4a04` on `#fbeadb` | `#f3b985` on `#3f2208` |
| misaligned | `#9d2f26` on `#f9e9e7` | `#f5a39c` on `#451612` |
| illustrative | `#452763` on `#f7f4fb`, dotted border | `#d7c3ec` on `#221632` |
| pending | `#6b6476` on `#efedf1` | `#b9b2c3` on `#2a2433` |

Color never carries information alone: every chip's text is its label,
every banner names its verdict, every chart has a legend and a table.

Alternative accent proposed for the checkpoint: an ink blue
(`#27456f` text, `#4a6a94` non-text, light) that reads as a ledger rather
than a brand. Oscar picks one. Both are one token change.

### Type

Inter for everything. Fraunces only for the wordmark and the landing H1
(proposal A) or nowhere (proposal B, Inter 32 semibold), Oscar picks at the
checkpoint. Six steps plus the landing H1, each with its line height:

| Token | Size / line | Use |
|---|---|---|
| `--fs-12` | 12 / 16 | captions, chips, eyebrows, axis labels. The floor. A gate fails any smaller text. |
| `--fs-13` | 13 / 18 | table cells, buttons, dense lists |
| `--fs-14` | 14 / 20 | body |
| `--fs-16` | 16 / 24 | landing body, drawer titles |
| `--fs-20` | 20 / 28 | section titles, stat values |
| `--fs-24` | 24 / 32 | page titles |
| `--fs-32` | 32 / 40 | the landing H1 only |

`font-variant-numeric: tabular-nums` on every numeric column, stat and
axis. `text-wrap: balance` on headings. Eyebrows only at 12 px uppercase
with 0.06em tracking. Weights 400, 500, 600.

### Space, radius, elevation, motion

Space: 4, 8, 12, 16, 24, 32, 48, 64 (`--s-1` to `--s-8`). Radius: 4 and 8
(`--r-1`, `--r-2`) and a pill. Borders: 1 and 2 px. Shadows: three
(`--shadow-1` to `--shadow-3`). Motion: 120 ms and 200 ms, one easing
(`cubic-bezier(0.2, 0, 0, 1)`), only `transform` and `opacity` animate,
and `prefers-reduced-motion: reduce` sets both durations to 0.

### Themes

A full dark token set under `prefers-color-scheme: dark` (unless
`data-theme="light"` is set) and under `[data-theme="dark"]`, so the
system preference applies and an explicit choice wins. `color-scheme` on
the root, two `theme-color` metas, the native select styled with its own
arrow per theme. The choice is stored per browser and applied before the
first paint by a two-line inline script.

## 2. Components

Every component renders on `#/design` in every state (rest, hover,
focus-visible, active, disabled, loading) and in both themes. Keyboard and
ARIA behavior, by component:

| Component | Keyboard | ARIA and semantics |
|---|---|---|
| AppShell | a skip link is the first Tab stop and moves focus to `main` | `main` is focusable (`tabindex=-1`), one `nav` labeled Main, the content column has a 1,200 px maximum |
| Sidebar | every item is an `<a href>`, so Cmd-click and middle-click open a tab | `aria-current="page"` on the active route, four groups with eyebrow labels |
| MobileNavSheet | Esc closes, Tab is trapped, focus returns to the menu button | `role=dialog`, `aria-modal`, `aria-labelledby`, `overscroll-behavior: contain`, a route change closes it |
| PageHeader | none | the H1 of the route, an eyebrow, a one-sentence subtitle, actions. The H1 is within the first 200 px on mobile |
| ContextChip | a native select | a `<label for>` on every select, shown only on the panels the plan or product drives |
| Button | Enter and Space | `type=button` by default, the icon variant requires an accessible name (it throws without one), `aria-busy` while loading, loading text ends with the ellipsis character |
| Link | Enter, modifier clicks open a tab | a real `<a href>` for every navigation, `rel=noopener` and the external glyph on outbound links |
| Chip | none (not interactive) | the text is the label, 12 px minimum, one of 17 kinds, never color alone |
| Card, CardLink | a linked card is one `<a>` | `section` by default |
| Stat | none | label, value with tabular figures, unit, source line |
| VerdictBanner | none | `role=status`, the defined label, its one-line definition inline, a legend link |
| Table | header sort buttons (Enter, Space), the scroll region is focusable | `<caption>`, `scope=col`, `aria-sort` on sortable headers, sticky header and first column, virtualized above 50 rows, a column picker of checkboxes, cards under 720 px with `data-label` headers, an empty state row |
| Drawer | Esc closes, Tab is trapped, focus lands on the close button and returns to the opener | `role=dialog`, `aria-modal`, `aria-labelledby` |
| Dialog | as Drawer | as Drawer, click on the scrim closes |
| Palette | ⌘ K or Ctrl K opens, arrows move, Home and End jump, Enter runs, Esc closes and returns focus | `role=combobox` input over a `role=listbox`, `aria-activedescendant`, a polite live region with the count |
| Tabs | arrows move between tabs, Home and End jump, the panel is focusable | `role=tablist` with a label, `aria-selected`, `aria-controls`, roving tabindex |
| Disclosure | Enter and Space on the summary | a native `<details>`, the chevron is `aria-hidden`, a visible hover and focus state |
| Field | none | `<label for>`, hint and error joined by `aria-describedby`, the error has `role=alert`, `aria-invalid` on the control |
| Input, NumberInput, DateInput, Select, Textarea | native | `inputmode=numeric` or `decimal` on number inputs, `autocomplete` where the field has one |
| Checkbox, Radio | native, the whole label is the hit target | 24 px minimum hit target |
| Slider | arrows, Home, End, Page keys | a visible value in an `<output>`, `aria-valuetext`, fires on input, a polite live region for the recompute it drives |
| PasswordInput | a Show toggle with `aria-pressed` | `autocomplete=current-password` |
| FileDownload | Enter on the link, Enter on Copy | a real `<a download>` whose href is a blob of the bytes on screen, the size shown, a copy button with a toast |
| Toast | none (a toast with an action has a button) | `aria-live=polite`, `role=status`, four seconds, eight with an action such as Undo |
| EmptyState | none | `role=status`, a title and one sentence that says what to do first |
| Skeleton | none | `role=status`, a polite live label ending with the ellipsis character |
| ProgressList | none | an `<ol>` with `aria-current=step`, each step's state read to screen readers, a polite live region for the active step |
| Tooltip and Term | Enter or Space toggles, Esc closes and returns focus, tap toggles | `role=tooltip`, `aria-expanded`, `aria-controls`, `aria-describedby` while open. The glossary lives here, nothing is hover only |
| Icon | none | `aria-hidden` unless it is the only content of a button, one inline set of 27 glyphs |
| Charts | data points and bars are focusable with a name, a Table toggle on every chart | `figure` with `aria-labelledby` and `aria-describedby`, text at token sizes in CSS pixels, scales computed per container width, a legend |
| CiteButton and the citation drawer | Enter opens, Esc closes and returns focus to the button that opened it | the button's accessible name says which row and which fund it opens, so fifty on one page are fifty distinct names. The drawer carries the document, the section, the verbatim sentence, who read it, whether anyone has signed it, and a link to every filing the accession resolves to, all from the manifest through the record chunk |
| PremiumPanel | the chart and its table alternative | the exhibit for a fund whose shares trade at a price of their own, inside that fund's record under the factors it speaks to. Every figure is the fund's own filed table or the held market-price series, and the series is labeled a market price wherever it appears |

## 3. Copy rules

- Title Case for headings and button labels, sentence case for body copy.
- Numerals for counts. Second person where the user is addressed. Active voice.
- No shouting: the illustrative marker is a chip, verdicts are words.
- No em dashes and no semicolons.
- Every internal identifier reaches the DOM through the copy layer
  (`web/src/copy/copy.ts`): registry keys, cohort keys, strategy and lane
  keys, rubric criteria, enum values, statuses, verdicts, wrapper classes,
  job states and census field names. The allowlist gate
  (`src/test_surfaces.py`, rules in `tark_display.PROSE_RULES`) fails any
  snake_case token, repository path or file name, ticket reference, the
  words engine, artifact, typed, the writer, the build, this build and the
  site, and slider outside the name of the figure it sets ("slider
  assumption") and the control's own label ("allocation slider"), in reader
  prose: every bundle string a view prints, every rendered view and every
  document paragraph. A field set in code style for provenance is exempt
  from these rules and never from the forbidden-string list: in the bundle
  the evidence ledger's source and verbatim quote and the closed-vocabulary
  fact values the views map to words, on a page an element with the
  `provenance` or `cmd` class, a `pre` or `code` element and a slider
  control's own row, in a document the "Source as written" and "Accession
  and EDGAR URL" columns. "Owned" is not in the list: its only uses are
  English ("wholly owned"). Internal keys inside the record's own cell text
  (a product key, a field name, a dataset column) reach every surface and
  document through `tark_display.display_copy`, which prints their words.
- "Verified" and "human-verified" appear only beside the count of signed
  cells. A pending state says "pending".

## 4. Formatting rules

`web/src/format/format.ts` is the only formatter. `Intl.NumberFormat` and
`Intl.DateTimeFormat` with the viewer's locale. Percent, currency, compact
money, ratios to a stated precision, dates as "June 9, 2026" or ISO where a
filing date is quoted. Non-breaking spaces inside "n = 5", "2% < 1 year",
"⌘ K" and between a number and its unit. Curly quotes and apostrophes, the
ellipsis character, `translate="no"` on tickers, fund names and cell ids.
The formatting gate greps the built JS for `toFixed(`, `toLocaleString(`
without options, straight quotes in strings rendered to users, and three
dots.

## 5. Gates

`src/test_web.py` (R3-P1-11), run by the hook and by CI against the built
output: the token gate, the copy allowlist gate, the formatting gate, the
guideline audit on every route at 1440 and 390 px in both themes, axe-core
with zero serious or critical findings, the performance budget, and the
preview-subpath check.

The guideline audit asserts the pinned rule set in
`docs/design/web-interface-guidelines_2026-09-07.md` in full. Per route, at
both widths, in both themes:

- Accessibility: every interactive element focusable with a visible ring,
  every form control labeled, every icon-only button named, every icon
  hidden or named, every image with alternative text, strict heading order
  with exactly one H1, a skip link that works, no text under 12 px, every
  text pair at 4.5:1 (3:1 at 24 px and up), no information carried by a
  `title` alone, a live region on every page.
- Interaction: tap targets at 24 px and 44 px for a primary action on
  mobile, the double-tap delay removed on every control, nothing that is
  not a control looking clickable, at most one element claiming the focus
  and none on a narrow viewport, an overlay that contains its own scroll.
- Forms: an autocomplete on every field, an inputmode on every numeric
  field, a placeholder that ends with an ellipsis and shows the pattern, no
  spellcheck on a code or an address.
- Layout: no horizontal scroll of the page body, the H1 within the first
  200 px on mobile, a table inside its own scroll container with a sticky
  header and a caption, a list over sixty rows virtualized rather than put
  in the document whole, an image with its dimensions.
- Typography, read from the rendered text rather than from a string
  literal, because an apostrophe ends a string literal and the check could
  never see it: no straight apostrophe, no straight quotation mark, no
  three-dot ellipsis, no em dash. A verbatim quote from a filing is exempt,
  because it is the document's own text and is never edited.
- Theming: the root declares its colour scheme, the browser chrome gets the
  theme colour, a native select paints its own background and colour, and
  zoom is never disabled.
- Navigation: Back returns to the previous route with its scroll position,
  a filter or sort change keeps focus and scroll, the palette and the
  drawer take and return focus, the theme choice survives a reload, and
  reduced motion collapses every duration.

Once over the built output: every font face declares its swap, the layout
applies the safe-area insets, the tap highlight is set on purpose, every
control has a hover state, the focus ring is drawn on `:focus-visible`,
paste is never blocked, and the page fetches nothing from another host.

## 6. Checkpoint record

Approved by Oscar on 2026-09-08, as built, and recorded as decision 8.21.
- Accent: the re-tuned plum. The ink-blue alternative was not taken.
- Display face: Fraunces for the wordmark and the landing H1, Inter
  everywhere else. The Inter-only proposal was not taken.
- Focus ring: the blue, kept distinct from the accent.
- Reviewed on: the eight images in `docs/screenshots/design_checkpoint/`,
  both themes at 1440 and 390 px, each width also with the focus ring on.
  The preview at `previews/5/#/design` was gone by then, because a preview
  folder is removed when its pull request closes.
Every property an image cannot show is asserted by the web gate on every
route, which is where it belongs. A later change to a token is a commit
against decision 8.21.
