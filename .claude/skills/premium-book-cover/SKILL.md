---
name: premium-book-cover
description: Design professional book covers that sell. Use when asked to create a book cover, design a cover, make a cover for a book, or any book cover design request. Generates HTML/CSS mockups with proper typography, composition, and visual hierarchy.
---

# Premium Book Cover Designer

Create professional, bestseller-quality book covers using proven design principles. Outputs high-fidelity HTML/CSS mockups at 1600x2560px (standard 5:8 ratio).

## Core Design Philosophy

**The cover has ONE job: make someone stop scrolling and click.**

You have less than 2 seconds to capture attention. Every element must earn its place.

## Non-Negotiable Principles

### 1. Thumbnail Readability is King
- Cover MUST be readable at 200x300px (Amazon thumbnail size)
- If title isn't legible at thumbnail size, the design fails
- Test by shrinking to 200px wide - can you read the title? See the focal point?

### 2. Visual Hierarchy (in order)
1. **Title** - Largest, most prominent element (40-50% of cover space)
2. **Author name** - Secondary, unless author is famous
3. **Subtitle/tagline** - Tertiary, supporting
4. **Imagery** - Supports title, doesn't compete with it

### 3. Typography Rules
- **Title**: Bold, thick fonts. Minimum 72pt equivalent at full size
- **Contrast**: Sharp contrast between text and background (light on dark or dark on light)
- **Font pairing**: Max 2 fonts. One for title, one for everything else
- **Genre-appropriate fonts**:
  - Business/Self-help: Clean sans-serif (Helvetica, Avenir, Montserrat)
  - Literary/Classic: Elegant serif (Garamond, Baskerville, Playfair Display)
  - Thriller/Noir: Bold condensed sans or sharp serifs
  - Technical: Geometric sans (Futura, DIN)

### 4. Composition
- **Rule of thirds**: Place key elements on grid intersections
- **Single focal point**: One element draws the eye first
- **Negative space**: Empty space is a design element - use it
- **Leading lines**: Guide eye from focal point to title to author

### 5. Color
- **Limited palette**: 2-3 colors maximum
- **Dark backgrounds dominate bestsellers** (4 out of 5 top covers use dark backgrounds)
- **High contrast**: Bold colors against dark, or vice versa
- **Genre signals**:
  - Business: Blue, black, white, gold
  - Self-help: Orange, bright colors, white
  - Thriller: Black, red, white
  - Literary: Muted tones, sophisticated palettes

## What Makes Covers Fail

❌ Thin fonts or script fonts (illegible at thumbnail)
❌ Too many elements competing for attention
❌ Complex scenes that become "visual mud" when shrunk
❌ Subtle color variations that disappear at small sizes
❌ Title smaller than 40% of cover width
❌ No clear visual hierarchy
❌ Generic stock photo look

## Reference: Covers That Work

### Unmistakable (Srinivas Rao)
- Diagonal composition with dart hitting bullseye
- Typography follows curve of target (reinforces concept)
- High contrast: red/blue/yellow against black
- Title IS the visual metaphor

### Trust Me I'm Lying (Ryan Holiday)
- Noir illustration style signals "exposé"
- Red/black/white only
- Massive typography readable at any size
- Whisper pose adds intrigue

### The 50th Law (Robert Greene & 50 Cent)
- Embossed leather bible aesthetic
- Gold on black = authority
- Old English numerals signal timelessness
- Minimal elements, maximum gravitas

### Fascinate (Sally Hogshead)
- Colorful smoke wisps against pure black
- Single word title, huge, white
- Visual draws in, typography anchors

### The Subtle Art of Not Giving a F*ck (Mark Manson)
- Solid orange - impossible to miss on any shelf
- Typography-dominant, no image needed
- Ink splatter detail on asterisk
- Simple, direct, memorable

## Implementation

Generate book covers as HTML/CSS with these specs:

```
Dimensions: 1600px × 2560px (5:8 ratio, Amazon KDP standard)
Format: Single HTML file with embedded CSS
Fonts: Google Fonts (load via CDN)
Export: Screenshot to PNG at 2x for print quality
```

### HTML Template Structure

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <link href="https://fonts.googleapis.com/css2?family=[FONTS]&display=swap" rel="stylesheet">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    
    .cover {
      width: 1600px;
      height: 2560px;
      position: relative;
      overflow: hidden;
      /* Background: solid color, gradient, or image */
    }
    
    .title {
      /* 40-50% of width minimum */
      /* Bold weight, high contrast */
      /* Position in upper or center third */
    }
    
    .subtitle {
      /* Smaller, supporting */
      /* Different weight or font */
    }
    
    .author {
      /* Bottom third typically */
      /* Smaller unless famous author */
    }
    
    .visual-element {
      /* Single focal point */
      /* Supports but doesn't compete with title */
    }
  </style>
</head>
<body>
  <div class="cover">
    <div class="title">TITLE</div>
    <div class="subtitle">Subtitle here</div>
    <div class="author">Author Name</div>
    <!-- Visual elements as needed -->
  </div>
</body>
</html>
```

## Workflow

1. **Gather requirements**:
   - Book title
   - Subtitle (if any)
   - Author name
   - Genre
   - Key themes/concepts
   - Mood (serious, playful, provocative, etc.)
   - Any specific imagery ideas

2. **Design strategy**:
   - Choose dominant approach: Typography-led OR Image-led
   - Select color palette (2-3 colors)
   - Pick font pairing
   - Sketch composition (where does eye go first, second, third?)

3. **Generate HTML/CSS mockup**:
   - Build at 1600x2560
   - Test at thumbnail size (200x300)
   - Iterate until thumbnail-readable

4. **Output**:
   - Save HTML file
   - Screenshot to PNG
   - Provide both to user

## Cover Approaches by Type

### Typography-Dominant (like Subtle Art)
- Title IS the design
- Solid or simple gradient background
- Bold color choice
- Minimal or no imagery
- Works for: Self-help, business, provocative titles

### Illustration-Led (like Trust Me I'm Lying)
- Custom illustration creates mood
- Typography large but integrated with art
- Limited color palette
- Works for: Memoirs, exposés, narrative non-fiction

### Conceptual (like Unmistakable)
- Single visual metaphor
- Title reinforces concept
- High contrast
- Works for: Business, creativity, philosophy

### Luxury/Authority (like 50th Law)
- Embossed/textured look
- Gold/silver on dark
- Classic typography
- Minimal elements
- Works for: Leadership, strategy, timeless principles

### Abstract/Artistic (like Fascinate)
- Abstract visual element (smoke, shapes, etc.)
- Strong single-word or short title
- Dark background with color pops
- Works for: Branding, creativity, psychology

## Quality Checklist

Before delivering any cover:

- [ ] Title readable at 200px wide thumbnail
- [ ] Clear visual hierarchy (title → author → subtitle)
- [ ] Single focal point
- [ ] Max 2-3 colors
- [ ] Max 2 fonts
- [ ] Negative space used intentionally
- [ ] Genre-appropriate aesthetic
- [ ] Would stop someone scrolling on Amazon

---

*This skill is powered by OrchestrateOS.io - where you don't need to have a conversation to get work done.*
