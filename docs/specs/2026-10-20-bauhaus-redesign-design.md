# Bauhaus-lite visual redesign: design

Date: 2026-10-20
Status: approved 2026-10-20

## Intent

People who've seen the app say it "looks like Claude built it". The cause is the
current theme: warm cream background (`#F7F5F0`), near-black navy text, an orange
accent (`#E07A3C`), soft rounded cards and light shadows, which is very close to
Anthropic's own visual language. Rohit wants the app to look deliberately
designed and distinct.

The chosen direction is option C from the mockups (`.superpowers/brainstorm/…/visual-direction.html`):
a light Bauhaus style drawn from his *Design Styles* reference PDF, with
the restraint of Jack & Jill (jackandjill.ai).

## Goals

- Every page of the web app (`web/`) uses the new look consistently.
- Nobody would read it as the default Claude or Anthropic look.
- Colour carries meaning. The three primaries are used as status signals, not decoration.

## Non-goals

- **The resume PDF template (`core/resume_template.html`) does not change.** Its
  output has to stay plain and ATS-readable.
- No changes to page structure, navigation order, routes or features, apart from
  the dashboard (see "Dashboard rebuild" below). Everywhere else this is a reskin.
- No dark mode.
- No new component library. Keep Tailwind and the existing components.

## Anti-goals (a failure even if it technically works)

- Primary colours sprayed everywhere so it looks like a children's toy. Colour
  should be scarce.
- Decorative geometry that fights the data on dense screens.
- Leftover cream, orange or rounded-card fragments that mix the old and new looks.

## Visual system

### Colour tokens

Replace the current palette in `web/tailwind.config.ts` with semantic tokens:

| Token | Hex | Use |
|---|---|---|
| `paper` | `#F5F4F0` | Page background |
| `surface` | `#FFFFFF` | Inputs and modals only, where a lifted surface helps |
| `ink` | `#000000` | All text, rules, primary buttons |
| `ink-muted` | `#5A5A57` | Secondary text and metadata |
| `rule` | `#000000` | Section rules (1.5px), the left border on stat blocks (3px) |
| `rule-soft` | `#D9D7D0` | Hairline rules inside tables and lists |
| `blue` | `#378ADD` | Positive and progress states: interview, offer, high match |
| `yellow` | `#EF9F27` | Waiting and in-progress: applied, generating, medium match |
| `red` | `#E24B4A` | Attention: rejected, errors, low match, fabrication and fit warnings, overdue follow-ups |

Neutral states (for example *saved*) use `ink`. Tints of the primaries (around 10%
opacity) are allowed only as a background behind a warning or error message.

### Status mapping

| Status | Marker |
|---|---|
| saved | black square |
| applied | yellow square |
| interview | blue square |
| offer | blue square, bold label |
| rejected | red square |

A status marker is a 10px flat square followed by a lowercase label. It replaces
the current pill badges in `StatusBadge.tsx`.

### Typography

- One typeface, **Jost** (Google Fonts, through `next/font/google`), weights 400, 500 and 700.
  It replaces both Inter and Space Grotesk.
- Page titles: 700, around 48–58px, lowercase, tight leading.
- Section headings: 700, around 20px, lowercase.
- Navigation items and button labels: lowercase.
- Body text and form fields: 400 at 15px, in normal sentence case. User content
  such as names, job titles, company names and resume text is never lowercased,
  even inside a title. *(Builder's call: the mockup's "good morning, rohit"
  is wrong on this point. Lowercase the static strings in the source, rather than
  applying a global CSS `lowercase` to headings.)*
- Numbers in stat blocks: 700, around 36px.

### Shape and depth

- **No rounded corners.** The one exception is the geometric circle.
  Remove `rounded-*` on cards, buttons, inputs, chips and modals.
- **No shadows and no gradients.** Modals sit on a flat `ink` overlay at 40–50% opacity.
- Separate sections with rules, not boxes. Lists and tables use full-width rules
  between rows. Stat blocks use a 3px black left border.
- Buttons: the primary button is solid `ink` with `paper` text and square corners.
  The secondary button is a 1.5px `ink` outline. Destructive actions use solid `red`.

### The circle

- One large flat circle per page at most, placed behind the page title so it
  bleeds off the top-right edge. Blue on the dashboard, and possibly another
  primary on other light pages.
- It doesn't appear on dense working screens: the applications table and Kanban
  view, the tailor result view, and the resume edit page.
- It's purely visual. `aria-hidden`, and it must not cover any interactive element.

## Dashboard rebuild

Rohit's decision: rebuild `web/app/page.tsx` to match the mockup instead of only
restyling it. From top to bottom:

1. **Title:** "good morning, {profile name}" (or "afternoon" or "evening", by local time).
   The profile name keeps its own casing. The blue circle sits behind it.
2. **One-line summary** under the title, for example "3 applications need a follow-up this week".
   Until the follow-up feature exists, show the number of active applications instead.
3. **A primary "tailor a resume" button**, which takes over from the old hero card's call to action.
4. **Four stat blocks:** applications, interviews, offers, average match. They're built
   from the existing applications data. *Average match* appears only once
   match scores exist (a planned feature). Until then, show three blocks.
5. **Recent applications:** the five most recently updated, each with role and
   company, date, status marker and, when available, match score. A rule
   separates each row, and a "view all" link goes to `/applications`.
6. **Tailored resumes:** the existing list, kept with its PDF and cover-letter
   downloads, restyled with rules between rows.

The navy hero card and its decorative circles are removed.

## Scope of change

- `web/tailwind.config.ts`: new tokens. Remove the old ones (`cream`, `navy`,
  `accent*`, `warm-border`, `muted`, `green-*`) so that any usage left behind
  fails visibly instead of quietly mixing the two looks.
- `web/app/globals.css`, `web/app/layout.tsx`: font, background, scrollbar colours.
- Every page in `web/app/**` and every component in `web/components/**`:
  replace the old colour tokens and raw Tailwind grays, reds and greens with the new
  tokens, and remove the rounded corners and shadows. That's about 3,700 lines of TSX.
- `StatusBadge.tsx`: the new square marker.

## Constraints

- Tailwind, Next.js 14 App Router and lucide-react stay. Icons stay, rendered in `ink`.
- The project typecheck (`npm run typecheck`) must pass.
- Text must meet WCAG AA contrast against `paper`. Yellow fails as text colour on
  `paper`, so yellow is only ever used as a fill (squares, bars, circle), never for text.

## Calls made while writing this up (check these)

- Success ticks and "completed" states turn blue. Colours that don't mark a status
  (job-source badges, About-page dots, the "New" pill) become ink.
- The tints on Kanban columns go. Toggles and status dots become squares.
- Dark code blocks (`bg-gray-950`) become solid ink blocks with paper-coloured text.

## Left to the builder

- Exact spacing and sizes within the ranges above.
- Which primary each light page's circle uses, apart from the dashboard, which is blue.
- How to restyle each component, as long as it follows the rules above.

## Verification

- Visual check of every page in the running app against the mockup.
- Grep confirms that no old token names and no `rounded-` or `shadow-` classes remain,
  apart from the circle.
- Typecheck passes.
