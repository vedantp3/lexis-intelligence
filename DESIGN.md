---
name: Lexis Intelligence
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#45464d'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#76777d'
  outline-variant: '#c6c6cd'
  surface-tint: '#565e74'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#131b2e'
  on-primary-container: '#7c839b'
  inverse-primary: '#bec6e0'
  secondary: '#735c00'
  on-secondary: '#ffffff'
  secondary-container: '#fed65b'
  on-secondary-container: '#745c00'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#00174b'
  on-tertiary-container: '#497cff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae2fd'
  primary-fixed-dim: '#bec6e0'
  on-primary-fixed: '#131b2e'
  on-primary-fixed-variant: '#3f465c'
  secondary-fixed: '#ffe088'
  secondary-fixed-dim: '#e9c349'
  on-secondary-fixed: '#241a00'
  on-secondary-fixed-variant: '#574500'
  tertiary-fixed: '#dbe1ff'
  tertiary-fixed-dim: '#b4c5ff'
  on-tertiary-fixed: '#00174b'
  on-tertiary-fixed-variant: '#003ea8'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
typography:
  display-lg:
    fontFamily: Source Serif 4
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Source Serif 4
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Source Serif 4
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
  headline-sm:
    fontFamily: Source Serif 4
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  title-lg:
    fontFamily: Hanken Grotesk
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Hanken Grotesk
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Hanken Grotesk
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: Hanken Grotesk
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 8px
  container-max: 1280px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 48px
---

## Brand & Style

The design system is engineered for **Constitution AI**, a platform where legal precision meets computational intelligence. The brand personality is **authoritative, meticulous, and visionary**. It aims to evoke the feeling of an elite digital law firm—one that is rooted in the weight of tradition but powered by the speed of the future.

The design style is **Modern Professionalism with a touch of Minimalist Luxury**. It prioritizes extreme clarity, utilizing heavy whitespace to ensure that complex legal information remains digestible. The aesthetic balances high-contrast typography with subtle, tactile interface elements to create an environment that feels both grounded and innovative.

## Colors

The palette is anchored by **Deep Navy (#0F172A)**, representing the stability and authority of constitutional law. This is contrasted against a **Refined Gold (#D4AF37)**, used sparingly for primary actions and high-value highlights to denote premium quality.

**Deep Blue (#2563EB)** serves as a functional accent for interactive elements like links and active states, bridging the gap between "Legal" and "Tech." The background remains primarily **Pure White (#FFFFFF)** or **Slate Gray (#F8FAFC)** to maintain an "academic" clarity, ensuring the user's focus is never diverted from the content.

## Typography

This design system employs a tiered typographic strategy to distinguish between "The Law" and "The Interface." 

**Source Serif 4** is used for headlines and titles. Its classic proportions and sturdy serifs evoke the feeling of printed legal documents and historical authority. **Hanken Grotesk** is used for all body text and UI labels. It provides a sharp, contemporary contrast that ensures high legibility in data-dense AI environments.

For long-form reading, such as legal briefs or AI-generated summaries, use `body-lg` with a slightly increased line height to reduce eye strain. All labels should utilize a subtle letter-spacing increase to maintain clarity at smaller scales.

## Layout & Spacing

The layout follows a **Fixed-Fluid Hybrid Grid**. Content is housed within a 12-column grid system with a maximum width of 1280px to maintain readability on ultra-wide monitors. 

Spacing follows a strict 8px linear scale. For legal documents, use generous padding (e.g., 40px - 64px) to create a "document-centric" feel within the browser. On mobile, margins compress to 16px, and complex data tables should transition into card-based layouts or horizontal-scroll components to preserve data integrity.

## Elevation & Depth

Hierarchy is established through **Tonal Layering and Soft Ambient Shadows**. Rather than heavy drop shadows, this design system uses "Surface Offsets."

1.  **Level 0 (Base):** Pure White (#FFFFFF) for the main canvas.
2.  **Level 1 (Cards/Sidebar):** Slate Gray (#F8FAFC) background with a 1px border in #E2E8F0.
3.  **Level 2 (Active/Floating):** White background with a highly diffused, low-opacity Deep Navy shadow (Blur: 20px, Y: 10px, Opacity: 4%).

This approach creates a sense of "stacked paper," reinforcing the legal metaphor without looking dated or bulky.

## Shapes

The design system utilizes **Rounded (0.5rem)** corners as the default for most components. This specific radius is soft enough to feel modern and accessible, yet sharp enough to maintain a professional, serious tone. 

Interactive elements like buttons use the default `rounded`, while larger containers like modal dialogs or "Analysis Cards" should use `rounded-lg` (1rem) to create a clear visual distinction from the rest of the UI.

## Components

### Buttons
Primary buttons use the Deep Navy (#0F172A) background with White text. The "Premium" button variant uses a Refined Gold (#D4AF37) border or subtle background to highlight AI-powered features. All buttons feature a 0.2s ease-in-out hover transition that slightly deepens the background color.

### Input Fields
Inputs are defined by a 1px Slate border and 12px horizontal padding. Focus states should use a 2px Deep Blue (#2563EB) ring. For legal search bars, use a larger font size (18px) to emphasize the primary action of the platform.

### Cards & Surfaces
Cards should be used to group AI insights or document metadata. Use a White surface with a thin #E2E8F0 border. Headers within cards should use the `label-md` typographic style for a structured, metadata-heavy look.

### Document Viewer
A specialized component for displaying legal text. It should feature a "margin" area for AI-generated annotations and line numbers. The background should be slightly off-white to distinguish the "official document" from the "platform interface."

### Chips/Tags
Used for "Citation Labels" or "Confidence Scores." These should use a light tint of the primary color (e.g., Deep Navy at 5% opacity) with the text in the full Deep Navy color.