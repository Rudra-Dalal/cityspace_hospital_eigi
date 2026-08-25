# Medihub / CityCare Frontend Design System

## 1. Design Philosophy
Medihub's design system is founded on the intersection of three rigorous references:
1. **Apple HIG**: Calibrated hierarchy, restraint, physical springs, optical typography, clear cause-and-effect feedback, accessibility.
2. **Kokonut UI**: Contemporary SaaS components, refined card surfaces, modern button states, micro-interactions.
3. **shadcn/ui**: Rock-solid accessible component architecture on Radix primitives.

---

## 2. Typography: Helvetica Neue Stack

Typography is strictly sans-serif with optical letter-spacing rules:
- **Font Stack**: `"Helvetica Neue", -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Arial, sans-serif`
- **Hero / Display Headlines**: Helvetica Neue Bold (`font-weight: 700`), `letter-spacing: -0.028em`, `line-height: 1.15`
- **Page Titles**: Helvetica Neue Bold / Semibold (`font-weight: 600–700`), `letter-spacing: -0.024em`
- **Section & Card Headings**: Helvetica Neue Semibold / Medium (`font-weight: 600`), `letter-spacing: -0.018em`
- **Body & Longform**: Helvetica Neue Regular (`font-weight: 400`), `letter-spacing: -0.011em`, `line-height: 1.5`
- **Labels, Buttons & Navigation**: Helvetica Neue Medium (`font-weight: 500`), optical alignment, tap-feedback.
- **Numbers & Time Slots**: Tabular lining figures with precise font weights for rapid scanning.

---

## 3. Color Token System (OKLCH Color Space)

| Token Name | Light Mode (OKLCH) | Dark Mode (OKLCH) | Purpose |
| :--- | :--- | :--- | :--- |
| `background` | `oklch(0.985 0.003 220)` | `oklch(0.14 0.018 235)` | Canvas background |
| `surface` | `oklch(0.965 0.006 220)` | `oklch(0.18 0.022 235)` | Section backgrounds |
| `card` / `surface-elevated` | `oklch(1 0 0)` | `oklch(0.19 0.022 235)` | Elevated interactive cards |
| `foreground` | `oklch(0.17 0.02 230)` | `oklch(0.97 0.004 220)` | High-contrast body & title text |
| `primary` | `oklch(0.50 0.135 222)` | `oklch(0.66 0.13 220)` | Clinical cyan / sapphire accent |
| `primary-soft` | `oklch(0.935 0.028 222)` | `oklch(0.24 0.04 222)` | Soft badge & highlight fills |
| `border` | `oklch(0.90 0.006 220)` | `oklch(0.26 0.018 235)` | Crisp panel & input borders |
| `muted-foreground` | `oklch(0.46 0.018 230)` | `oklch(0.68 0.015 225)` | Subtitle & metadata text |
| `success` | `oklch(0.58 0.14 152)` | `oklch(0.68 0.13 152)` | Verified status & confirmed visits |
| `warning` | `oklch(0.72 0.14 75)` | `oklch(0.76 0.13 75)` | Pending approval & scheduled slots |
| `destructive` | `oklch(0.58 0.19 25)` | `oklch(0.64 0.17 25)` | Cancellation & error alerts |

---

## 4. Elevation, Radii & Motion

- **Border Radius**:
  - Small / Chips: `var(--radius-sm)` (10px)
  - Standard Buttons & Inputs: `var(--radius-lg)` (14px)
  - Cards & Panels: `var(--radius-2xl)` (22px)
  - Full Pills: `9999px`
- **Shadows**:
  - `shadow-subtle`: Subtle border reinforcement
  - `shadow-soft`: Elevated card resting state
  - `shadow-lift`: Interactive hover state
- **Motion Utilities**:
  - `.hover-lift`: Smooth 220ms bezier spring transition
  - `.tap-feedback`: Instant 120ms pointer-down scale reduction (`scale(0.97)`)
  - `.fade-rise`: Content entrance transition
  - `@media (prefers-reduced-motion: reduce)`: Full fallback to zero vestibular motion.
