# Product Requirements Document (PRD)
## Client Acquisition Landing Page for Imperium Acquisition

---

## Overview

**Project Name:** Imperium Acquisition Landing Page  
**Purpose:** A high-converting landing page for a client acquisition consulting business targeting agency owners, coaches, and consultants.  
**Target Audience:** Agency owners, business coaches, and consultants looking for predictable client acquisition systems.

---

## Design Direction

### Aesthetic Vision
- **Tone:** Professional, trustworthy, premium consulting feel
- **Color Palette:**
  - Primary: Deep forest green (`#1a3d2e` or similar dark green)
  - Secondary: Cream/off-white (`#f5f3ef` or similar warm white)
  - Accent: Gold/yellow for small UI elements (seen in corner icon)
  - Text: White on dark backgrounds, dark charcoal on light backgrounds
- **Typography:**
  - Headlines: Bold serif font (elegant, authoritative feel)
  - Body text: Clean sans-serif for readability
- **Overall Feel:** Clean, minimal, high-end consulting aesthetic with strong contrast between sections

---

## Page Sections (Top to Bottom)

---

### Section 1: Navigation Header

**Layout:** Full-width, minimal header  
**Background:** White/cream  
**Content:**
- Logo/Brand name: "Imperium Acquisition" (text-based, left-aligned)
- Optional: Navigation links (right-aligned) — may be omitted for simplicity

**Design Notes:**
- Keep minimal and unobtrusive
- Thin horizontal line below header as separator

---

### Section 2: Hero Section

**Layout:** Two-column layout on desktop, stacked on mobile  
**Background:** Cream/off-white

**Left Column (40%):**
- Professional photo of the founder (Charlie)
- Photo shows him gesturing at a whiteboard, action-oriented
- Photo should have slight shadow or frame effect

**Right Column (60%):**
- **Main Headline (H1):**  
  `"Client Acquisition For Agency Owners, Coaches & Consultants"`
- **Subheadline:**  
  `"I help agency owners, coaches & consultants get more clients."`

**Design Notes:**
- Headline should be large, bold serif typography
- Subheadline in smaller, lighter weight
- Generous whitespace around content
- Vertically centered content alignment

---

### Section 3: About / Introduction Section

**Layout:** Two-column on desktop, stacked on mobile  
**Background:** Deep forest green (primary brand color)  
**Text Color:** White

**Left Column (60%):**
- **Section Headline (H2):**  
  `"Hey I'm Charlie!"`  
  (Replace "Charlie" with actual founder name — this is a placeholder)
  
- **Bold Introduction Paragraph:**  
  `"I help agency owners, coaches & consultants build systems to sign more clients with ease. Predictable, consistent & reliable systems!"`

- **Body Copy:**
  ```
  It's not easy to run an agency or a coaching business. You're already doing 101 things, spread too thin, overworked and underpaid. A lot of agency owners and coaches get stuck in the 'glorified freelancer' stage, where their entire business depends on them, their time and their energy to run.
  
  What you really truly need to scale and grow is a system. A reliable, predictable and consistent way to generate new business, without you having to 'work harder' or 'hustle' or 'lock in'.
  
  That's where I can help.
  ```

**Right Column (40%):**
- Secondary photo of founder (presenting/teaching context)
- Shows credibility and authority

**Design Notes:**
- First paragraph should be bold/emphasized
- Comfortable line height for readability
- Smooth scroll transition from hero section

---

### Section 4: How It Works (The System)

**Layout:** Two-column on desktop, content left, image right  
**Background:** White/cream  
**Section Title:** `"How It Works..."`

**Content - 3 Steps:**

| Step | Title | Description (placeholder — needs real copy) |
|------|-------|---------------------------------------------|
| Step 1 | Craft Offer | [PLACEHOLDER: Describe the offer creation process] |
| Step 2 | Generate Qualified LEADS | [PLACEHOLDER: Describe lead generation system] |
| Step 3 | Book Appointments | [PLACEHOLDER: Describe appointment booking process] |

**Right Side:**
- Large image of a conference/presentation room (social proof, scale)

**Design Notes:**
- Step titles should be bold, slightly larger than body
- Clear visual hierarchy between steps
- Consider numbered badges or icons for each step
- Adequate spacing between steps

---

### Section 5: How To Work With Me

**Layout:** Two-column, image left, content right  
**Background:** White/cream  
**Section Title:** `"How To Work With Me"`

**Left Column:**
- Photo of founder at whiteboard (teaching/explaining pose)

**Right Column - 3 Steps:**

| Number | Title | Description (placeholder) |
|--------|-------|---------------------------|
| 01 | Book A Call | [PLACEHOLDER: Describe what happens on the call] |
| 02 | Receive Your Custom Plan | [PLACEHOLDER: Describe the custom plan delivery] |
| 03 | Achieve The Result | [PLACEHOLDER: Describe expected outcomes] |

**Design Notes:**
- Use `01 | Title` format for visual consistency
- Numbers should be bold/prominent
- Pipe separator adds premium feel
- Clean, scannable layout

---

### Section 6: Call-to-Action (CTA) Section

**Layout:** Centered, single column  
**Background:** White/cream

**Content:**
- **Headline:** `"Let's Book Your Call"`
- **CTA Button:** Link to booking calendar/funnel
- **Button Text Suggestion:** `"Book Your Free Strategy Call"` or similar

**Design Notes:**
- This is the primary conversion point
- Button should be prominent (consider green background to match brand)
- Add subtle hover animation on button
- Consider adding urgency or scarcity element (optional)

---

### Section 7: Footer

**Layout:** Full-width, simple footer  
**Background:** Black or very dark color

**Content:**
- **Company Name:** `"Blue Ocean Media"` (or actual company name)
- **Social Media:** Instagram handle with icon
- **Email:** Contact email with envelope icon
- **Phone:** Phone number with phone icon

**Design Notes:**
- Left-aligned content
- Icons before each contact method
- Subtle, non-distracting design
- Consider adding copyright line

---

## Technical Requirements

### Responsive Breakpoints
- **Desktop:** 1200px+
- **Tablet:** 768px - 1199px
- **Mobile:** < 768px

### Mobile Behavior
- All two-column layouts stack vertically
- Images scale appropriately or reposition
- Navigation collapses if present
- CTA buttons become full-width
- Typography scales down proportionally

### Performance
- Optimize all images (WebP format preferred)
- Lazy load below-the-fold images
- Minimize CSS/JS bundle size
- Target < 3s load time on 3G

### Accessibility
- Semantic HTML structure
- Alt text on all images
- Sufficient color contrast (especially on green backgrounds)
- Keyboard navigable
- Focus states on interactive elements

---

## Placeholder Content to Replace

The following items need real content from the business owner:

1. **Founder name** (currently "Charlie")
2. **Step descriptions** in "How It Works" section (currently lorem ipsum)
3. **Step descriptions** in "How To Work With Me" section (currently lorem ipsum)
4. **Actual photos** of the founder
5. **Company name** in footer (currently "Blue Ocean Media")
6. **Social media handle**
7. **Contact email**
8. **Phone number**
9. **Booking calendar/funnel link** for CTA button

---

## Image Requirements

| Location | Description | Suggested Dimensions |
|----------|-------------|---------------------|
| Hero | Founder pointing at whiteboard | 600x800px (portrait) |
| About Section | Founder presenting | 500x400px (landscape) |
| How It Works | Conference/audience photo | 600x400px (landscape) |
| How To Work | Founder at whiteboard | 500x600px (portrait) |

---

## Suggested Tech Stack

**Option A (Simple):**
- HTML5 + CSS3 + Vanilla JavaScript
- Single-page, static site

**Option B (React):**
- React with Tailwind CSS
- Component-based architecture
- Easy to iterate and maintain

**Hosting Recommendations:**
- Vercel, Netlify, or GitHub Pages for static
- Cloudflare Pages for edge performance

---

## Success Metrics

- Clear value proposition visible within 5 seconds
- Single, focused CTA (book a call)
- Professional, trustworthy appearance
- Fast load time
- Mobile-friendly experience

---

## Notes for Claude Code

1. **Start with mobile-first CSS** then enhance for larger screens
2. **Use CSS custom properties** for the color palette to enable easy theming
3. **Implement smooth scroll** for any anchor links
4. **Add subtle animations** on scroll (fade-in sections) for polish
5. **Test contrast ratios** especially for white text on green backgrounds
6. **Keep the design clean** — this is a premium consulting service, not a flashy startup

---

## File Structure Suggestion

```
/landing-page
├── index.html
├── styles/
│   └── main.css
├── scripts/
│   └── main.js (if needed)
├── images/
│   ├── hero-photo.webp
│   ├── about-photo.webp
│   ├── conference-photo.webp
│   └── whiteboard-photo.webp
└── README.md
```

---

*Document Version: 1.0*  
*Created for: Imperium Acquisition*  
*Template Source: ClickFunnels mentor template*
