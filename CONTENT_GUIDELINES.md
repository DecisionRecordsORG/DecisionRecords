# Content Guidelines for Decision Records

This document defines content creation standards for the Decision Records website. Follow these guidelines when creating blog posts, marketing pages, and educational content.

## Core Principle: Glanceable by Default

Most readers do not read entire articles. They scan to find details relevant to them or details the writer signals as important. Design all content for glanceability first, depth second.

## Typography Standards

### Headings (H2, H3)
- **Purpose**: Entry points for scanning readers
- **Style**: Sentence case (not all lowercase, not ALL CAPS for full headings)
- **Length**: 3-8 words, clear and specific
- **Font weight**: 600 (semi-bold) minimum
- **Spacing**: Generous whitespace above headings (2-2.5em margin-top)

### Body Text
- **Font size**: 1.05rem minimum (16.8px base)
- **Line height**: 1.7 ratio for comfortable reading
- **Line length**: 65-75 characters max (700px container)
- **Paragraph length**: 3-4 sentences maximum
- **Font family**: System sans-serif stack for optimal rendering

### Key Phrases & Takeaways
- Use **bold** for scannable key phrases within paragraphs
- Bold the most important 2-3 words that convey the paragraph's core message
- Readers scanning should be able to understand the gist from bold text alone

### Lists
- Prefer bulleted lists over dense paragraphs
- Each list item: one idea, one line when possible
- Use lists to break up any sequence of 3+ related items

## Content Structure

### Article Opening (First 2 Paragraphs)
- State the problem or question immediately
- No lengthy introductions or background
- Reader should know within 10 seconds if this article is relevant to them

### Section Design
- Each H2 section should be independently valuable
- A reader who jumps to any H2 should understand that section without reading prior content
- End sections with a clear takeaway or transition

### Visual Hierarchy for Scanning
```
H1: Article Title (one per page)
├── Lead paragraph (larger font, 1.2rem)
├── H2: Major Section
│   ├── Short paragraph with **key phrase** bolded
│   ├── Bullet list of supporting points
│   └── Transition sentence
├── H2: Next Section
│   └── ...
└── Conclusion with bold summary statement
```

### Pull Quotes / Blockquotes
- Use for single-sentence insights worth highlighting
- Should make sense out of context
- Style: left border, subtle background, italic

## Glanceability Checklist

Before publishing any content, verify:

- [ ] Can a reader understand the main point by reading only the title and H2 headings?
- [ ] Are the most important phrases in each paragraph bolded?
- [ ] Is there a clear visual hierarchy (title > headings > body)?
- [ ] Are paragraphs short enough to not feel like walls of text?
- [ ] Would a 30-second scan give the reader value?

## Visual Content Standards

### Placeholder Images (SVG)
Create abstract, conceptual illustrations that:
- Use the brand color palette (#2563EB blue, slate grays #64748B, #94A3B8)
- Convey the article theme without being literal
- Include geometric shapes: rounded rectangles, circles, simple paths
- Suggest people/collaboration through abstract silhouettes
- Maintain clean, minimal aesthetic (no gradients, no heavy detail)

### Image Dimensions
- Blog list thumbnails: 800x500 (16:10 aspect ratio)
- Hero images: 800x400 or full-width responsive

### Color Palette for Illustrations
```
Primary:    #2563EB (blue)
Secondary:  #1E40AF (dark blue)
Accent:     #60A5FA (light blue)
Grays:      #64748B, #94A3B8, #CBD5E1, #E2E8F0
Background: #F8FAFC
Success:    #4ADE80, #16A34A
Warning:    #F59E0B, #FBBF24
Error:      #F87171, #DC2626
```

## Tone & Voice

### What We Sound Like
- **Direct**: State the point, then elaborate
- **Confident but not arrogant**: We have opinions backed by reasoning
- **Practical**: Focus on what readers can do, not abstract theory
- **Respectful of reader time**: Every sentence earns its place

### What We Avoid
- Marketing superlatives ("revolutionary", "game-changing")
- Filler phrases ("It's worth noting that...", "As you may know...")
- Excessive hedging ("might", "perhaps", "in some cases")
- Jargon without explanation

### Example Transformations

❌ "It's important to understand that decision documentation can potentially help teams in various ways."

✅ "**Decision documentation helps teams** communicate faster and onboard new members without meetings."

---

❌ "In many cases, organizations find that..."

✅ "Organizations lose decision context when..."

## Blog Post Template

```markdown
# [Clear, Specific Title as a Question or Statement]

[Lead paragraph - 2-3 sentences stating the core problem or insight. Larger font.]

## [First H2 - The Setup/Problem]

[2-3 short paragraphs with **key phrases bolded**]

## [Second H2 - The Insight]

[Explanation with bullet points where appropriate]

- Point one
- Point two
- Point three

## [Third H2 - The Practical Application]

[Actionable content - what can the reader do?]

## [Final H2 - Conclusion/Call to Action]

[One paragraph summary. **Bold the main takeaway.**]
```

## SEO & Meta Standards

### Title Tags
- Format: `[Article Title] | DecisionRecords`
- Length: 50-60 characters

### Meta Descriptions
- Length: 150-160 characters
- Include the core value proposition
- Written as a complete sentence

### H-Tag Structure
- One H1 per page (article title)
- H2 for major sections (3-5 per article)
- H3 sparingly for subsections

## Content Categories

Use consistent category labels:
- **Documentation** - General decision documentation practices
- **Startups** - Content for early-stage companies
- **Enterprise** - Content for larger organizations
- **Governance** - Decision governance and compliance
- **Teams** - Team collaboration and communication
- **Technical** - Architecture decisions, ADRs, technical debt

---

*Last updated: December 2024*
*Reference: Google Fonts readability research, NN/g glanceable typography guidelines*
