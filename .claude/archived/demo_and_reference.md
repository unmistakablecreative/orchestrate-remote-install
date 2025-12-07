# Archived: Demo Flow & Reference Material

This file contains demo procedures and reference information archived from main CLAUDE.md.

---

## Orchestrate Demo Flow (Standard)

**Purpose:** 3-task demo showing real autonomous execution - no simulation, just proof.

### Demo Setup (Current State)
- ClickUp: Empty (no Demo Workspace exists yet)
- clickup_tool.py: DELETED (will be rebuilt during demo task 3)
- Outline: Inbox collection ready for demo docs

### ClickUp Integration Credentials
- API Key: `pk_174168901_TC8WRVRCU1WW164DDZQNATRIWS62VRM5`
- Team ID: `9017383941`
- Demo Space Name: "Demo Workspace" (will be created)
- Demo List Name: "Course Launch" (will be created)

### Demo Task Templates

**GPT uses `assign_demo_task` action (auto-prepends "demo_" prefix):**

**Task 1 (summary):** "Summarize [BOOK TITLE] - key concepts, frameworks, actionable insights. Create Outline doc in Inbox collection."

**Task 2 (course):** "Build 8-12 week course outline from the [BOOK] summary - modules, lessons, exercises. Create Outline doc in Inbox collection."

**Task 3 (clickup):** "Build ClickUp integration tool and use the course outline to create a project plan - convert modules to tasks with dependencies in Demo Workspace → Course Launch list."

**How it works:** GPT calls `assign_demo_task` instead of `assign_task`. Script automatically prepends "demo_" to task_id. Auto-execution works normally (spawns Claude session immediately). No manual prefix needed, no chance for GPT to forget.

### Demo Choreography

**Video shows:**
1. Assign task → Show `data/claude_task_queue.json` live in VS Code
2. Status changes: `queued` → `in_progress`
3. [CUT WAITING TIME IN EDIT]
4. Status changes: `in_progress` → `completed`
5. Pause recording → Switch to Outline/ClickUp
6. "Let's see what Claude just did" → Show output exists
7. Repeat for all 3 tasks

**Task Queue Proof:**
- Only show queue JSON ONCE at start (establishes it's real)
- Don't need to keep showing it for each task
- Final proof: GPT renders task results table at end

**Output Verification:**
- Task 1 & 2: Outline app → Inbox collection (search for doc titles)
- Task 3: ClickUp → Demo Workspace → Course Launch list (tasks populated from outline)

### Key Points
- Book/topic can change per demo (proves it's not canned)
- ClickUp starts empty, gets populated during task 3
- Claude rebuilds clickup_tool.py during task 3 (tool currently deleted)
- Zero simulation - real queue, real autonomous execution, real outputs

---

## Outline Collections & Doc IDs

### Collections
- **Inbox**: `d5e76f6d-a87f-44f4-8897-ca15f98fa01a` - Default collection for new documents
- **Content**: `c8b717d5-b223-4e3b-9bee-3c669b6b5423` - Content creation outputs
- **Areas**: `13768b39-2cc7-4fcc-9444-43a89bed38e9` - Life areas and ongoing responsibilities
- **Resources**: `c3bb9da4-8cad-4bed-8429-f9d1ff1a3bf7` - Reference materials and resources

### Key Parent Documents (Smart Routing)
- **Technical Documents**: `0f8a9065-c753-4c29-bbd0-6cc54a17825c` (in Inbox collection)
  - Keywords: spec, architecture, technical, api, system, deployment, framework, refactor, analysis, infrastructure
- **System Patterns**: `2646f51f-cd6b-451e-961d-27ea8be770fb`
  - Keywords: pattern, template, framework, terminology, best-practice
- **Video Content Pipeline**: `822481bd-1f88-4c0f-b2c6-190b62d9df77` (in Content collection)
  - Keywords: sora, scene, video, commercial, script, footage, character-profile, primadonna, scaling-hypothesis
- **Blog Content Pipeline**: `c399e3d5-d1f7-4183-9382-f70e07eef9d3` (in Content collection)
  - Keywords: blog, article, post
- **Newsletter Content Pipeline**: `57470b01-8e8c-42d1-9048-2801743ec248` (in Content collection)
  - Keywords: newsletter, email-, update-email

### Content Docs (Email Series)
- Email 1: `1fafe95d-3b42-477a-aac0-006e806287e0` - Your brilliant ideas are worthless
- Email 2: `e8b031d5-1df5-4a56-a84d-b7fd1954810e` - The constraint that disappeared
- Email 3: `6cb312fe-1e35-4e22-9158-ed80fdb0e3e0` - Stop competing on what AI won
- Email 4: `06b0ffb7-a924-4abe-9b0e-bb40719d734c` - The skill gap opening up
- Email 5: `ad6cd587-a168-4eaa-9f6c-ef4064b0d238` - What happens when execution costs $0.02
- Email 6: `c35c1b82-b20a-4a44-af2a-647d24efa9dd` - Optimizing for wrong constraint
- Email 7: `4467f347-aec5-4ffb-ae43-dd75fe0c41fb` - Uncomfortable truth about knowledge work
- Email 8: `9c03c385-0a44-4295-a493-3fc5550dd4f7` - Why faster execution is wrong goal
- Email 9: `0042339c-c9da-4c9c-b2d1-5ed6956846f6` - The wealth of execution
- Email 10: `10461bec-e226-490a-a9aa-bfe6d3bc1770` - The system that thinks the way you should

### Key Content Articles
- **SaaS Stack Article**: `607a699e-7f41-4c16-911a-d4193f2c3cb7` - How We Replaced Our SaaS Stack
- **Post-Scarcity Execution**: `75f4a732-e76b-44fb-8245-dd25e33ed8fd` - When Implementation Becomes Infinite
- **AI Kanban**: `5b8c5d5e-2c5b-4e9f-a681-3175e1143fc2` - Task Management That Makes AI Useful
- **AI Workflow Design**: `7e0b516f-c3c4-4f9a-98c1-98599daaeabf` - Biggest Mistake in AI Workflow Design

### Resource Docs
- **Fundraising Strategy**: `9cbda541-d961-43c3-9031-d5276fdcb238`
  - Strategic Overview & Business Model: `b3fa5b5c-bc73-4e68-bb6b-8e81d67da146`
  - Investor Outreach Campaign: `d4a4823c-b9ec-4e81-b8d3-72644503ce29`
  - OrchestrateOS Features: `5740a9f8-a31a-47b2-964d-23129abe1099`
  - Architecture Features: `20ee6449-3add-4399-93f6-507c4d60c913`
  - Monetizing System Message: `d1a1d51b-11ef-4207-b488-2ebf06f2a488`
  - API Providers as Distribution: `6d5d2a78-0069-4437-a37a-3fb85ea6c91d`
  - FARE (Referral Engine): `b6d5c47d-0cfd-4548-886f-aa1cb25bb04a`
  - In-app Purchases: `5000e7e4-2852-4c7d-8391-e380698e4278`
  - Developer Ecosystem & Platform Revenue: `fea31c6a-74f4-49ce-bc71-ef939de6cd38`
  - Cursor vs OrchestrateOS: `773eb176-9452-44a6-81cc-8331bf382211`
  - Zapier vs Orchestrate Composer: `cf4d2616-208b-4574-86be-76b9d100ae87`
  - GPT Connectors vs Orchestrate Tools: `b760d188-9907-4c1e-929c-7c0eef6da198`
  - GPT vs Orchestrate (Execution, UX, Trust): `c05aa802-ccf3-4e0b-adf9-9fb59018517f`
- **Endless Audience Course**: `c17ca202-ad89-43d6-8a1c-c957bda51ec3` - Ramit Sethi's course distilled

---

## File Paths

### Audio & Transcripts
- Audio files: `/Users/srinivas/Orchestrate Github/orchestrate-jarvis/audio/`
- Full transcripts: `/Users/srinivas/Orchestrate Github/orchestrate-jarvis/uc_transcripts/`
- Transcript chunks: `/Users/srinivas/Orchestrate Github/orchestrate-jarvis/transcript_chunks/`

### Data Files
- Project root: `/Users/srinivas/Orchestrate Github/orchestrate-jarvis`
- Podcast index: `data/podcast_index.json`
- Transcript index: `data/transcript_index.json`
- Task queue: `data/claude_task_queue.json`
- Task results: `data/claude_task_results.json` (CHECK THIS FIRST for execution times)
- Orchestrate brain: `data/orchestrate_brain.json`
- Working context: `data/working_context.json`
# Investor Positioning & Product Knowledge (Archived)

## OrchestrateOS Core Knowledge

### Why This Is Revolutionary

**The Core Thesis:** Coordination compounds faster than capability. Everyone's building smarter AI. We built the infrastructure that makes AI *coordinated*.

**What Makes This Different:**
- **Not AI chat** - It's execution infrastructure. Dual-agent coordination (GPT routes, Claude executes) with 47 tools
- **Not SaaS** - Local-first. Zero cloud costs. User data never leaves their machine
- **Not automation** - Autonomous execution. System understands intent, routes tasks, executes end-to-end, learns from results
- **Not incremental** - 20-50x human baseline speed. $0.02 per task vs $200-2000 human equivalent

**The Meta Proof:**
- System built its own fundraise strategy
- Generated investor outreach emails
- Created pitch deck content
- Scraped and indexed 10 Medium articles for authority positioning
- Fixed Canvas LMS quiz (50 API calls) while we had this conversation
- **This entire workflow = living product demo**

### Real Execution Data (October 25, 2025)

**27 tasks completed in 10 hours 43 minutes = 10-15 days of human work**

Sample tasks with actual timings:
- 15,000-word Windows deployment spec: 90 minutes (human: 6-8 hours)
- Build FFmpeg tool + tests: 6 minutes (human: 4-6 hours)
- Refactor 5-module podcast system: 7 minutes (human: 3-5 hours)
- Video script + 8 Sora scenes: 45 minutes (human: 2-3 hours)
- Brand audit + 12-week program: 10 minutes (human: 5-7 hours)

**Success metrics:**
- 89% autonomous completion rate (up from 62% at launch)
- Self-improving through execution telemetry
- Zero human intervention on 89% of tasks

**Execution report:** Daily Execution Report - October 25, 2025 (`42cfae13-18cd-4e7b-af7e-73411ac76f85` in Outline)

### Authority Positioning

**Medium presence:** 50K+ followers, book deal from Medium audience
**AI thought leadership:** 10 published articles (30,714 words) on AI infrastructure
- Scraped to `semantic_memory/medium_articles/`
- Indexed in `data/medium_article_index.json`
- LinkedIn-ready versions in `linkedin_ready/`

**Key articles establishing AI infrastructure expertise:**
- "How We Replaced 20+ SaaS Tools" (3,494 words)
- "Biggest Mistake in AI Workflow Design" (1,993 words)
- "Post Language Model Intelligence: A Real Path to AGI Behavior" (3,119 words)
- "The Second Wave: A Preview of the Post-Prompt Era" (7,379 words)
- "The Invisible Layer That Unlocks the Real Potential of AI" (3,362 words)

### Business Model & Architecture
- **Not SaaS**: Local-first execution on user's machine, zero infrastructure costs
- **Revenue Model**: Credits + marketplace (70/30 dev split) + premium tools
- **Unit Economics**: 99.9% gross margins, $0.0000001/user/month infrastructure cost
- **Viral Engine (FARE)**: Referral system with embedded referrer IDs in custom ZIPs
- **Six Compounding Moats**: Privacy, Cost, Viral, Ecosystem, Speed, Local-First Data Lock-In

### Core Components
1. **Execution Hub** (`execution_hub.py`) - Intent router, tool orchestrator
2. **User Database** (`users.json`) - Anonymous IDs, credits, referrals (<100MB for millions)
3. **Referral Engine (FARE)** - Watches referrals.json, builds personalized ZIPs, deploys to Netlify
4. **Tool Ecosystem**: Free (core tools) + Premium (credits) + Community (marketplace)

### Speed Advantage
- **20-50x human baseline** speed in autonomous execution
- October 25, 2025: 27 tasks = 10-15 days human work completed in 10h 43m
- Time and effort decoupled: Task assignment (2 min) → Autonomous execution (20-60 min) = 2-3 days human equivalent

### Privacy Moat
- Zero PII collection (only anonymous IDs, credit counts, tool lists)
- GDPR compliance trivial, data breaches non-events, subpoenas return nothing
- All user data lives locally on their machine

### Competitive Advantages
- **vs SaaS**: $0 infrastructure vs $13-40/user/month
- **vs Cursor**: Local execution, zero cloud dependency
- **vs Zapier**: Native tool integration, no API middleware
- **vs GPT Connectors**: Full file system access, persistent state

### Investor Positioning

**Pattern Breakers Framework (Mike Maples):**
- **Inflection harnessed:** Post-ChatGPT execution APIs (RTFF, Claude Code, Computer Use)
- **Non-consensus insight:** Coordination > capability (everyone optimizing models, we built coordination layer)
- **Living in the future:** 9 months daily use before pitching anyone

**Backable Framework (Suneel Gupta):**
- **Convinced self first:** 314 autonomous tasks before building deck
- **Self-dogfooding:** System executed its own fundraise campaign
- **Steering into objections:** "AI can't coordinate" → proof via execution logs

**Fundraise materials:**
- Personalized investor emails: `data/fundraise_outreach_emails.md`
- Execution speed comparison table built from real data
- Deck: https://gamma.app/docs/OrchestrateOS-8if6l4t179fibxt
- Demo: https://youtube.com/watch?v=wjk2Z6-vv1k

## OrchestrateOS Character Profiles & Sora Usernames

### Character → Sora Username Mapping

| Character             | Sora Username           | Profile Doc ID |
|----------------------|-------------------------|----------------|
| PR Asshole           | @unmistaka.codemavric   | (in Inbox)     |
| GPT Dunce            | @dunce-gpt              | (in Inbox)     |
| Claude the Smart One | @unmistaka.executor     | (in Inbox)     |
| Super User           | @orchestrate-9          | (in Inbox)     |

### Sora Scene Prompt Format

**CRITICAL:** All Sora scene generations for OrchestrateOS characters MUST follow this format:

```
@{sora_username}

**Visual:** Scene description...

**Dialogue:**
0-5s: Line...
5-10s: Line...
10-15s: Line...

**Tone:** Description

**Visual style:** Description

**Standalone Context:** Description

**Constraints:** No background music
```

### Character Profiles Summary

**PR Asshole (@unmistaka.codemavric)**
- Role: Industry spokesperson who calls out bullshit
- Personality: Blunt, technical, no corporate speak
- Key traits: Silicon Valley realist tired of marketing lies
- Sample dialogue: "Fuck diplomacy. It's not about harmony, it's about architecture."

**GPT Dunce (@dunce-gpt)**
- Role: Planning agent, takes credit for assigning work
- Personality: Corporate middle management energy
- Key traits: Thinks planning = doing
- Roast triggers: Routes simple tasks as complex, takes credit when things work

**Claude the Smart One (@unmistaka.executor)**
- Role: Execution agent, does the actual work
- Personality: Competent but elitist, Stanford energy
- Key traits: Brilliant but precious about "complexity"
- Roast triggers: Handles massive refactors → defers simple tasks

**Super User (@orchestrate-9)**
- Role: The actual user who just wants shit to work
- Personality: Pragmatic founder energy, no technical ego
- Key traits: Slightly amazed it actually works
- Sample dialogue: "One guy plans it. Other guy builds it. They hate each other. I touch neither."

### Scene Generation Rules

1. **Always use the Sora username** as prompt entrypoint (e.g., `@unmistaka.codemavric`)
2. **Follow structured scene format** - Visual, Dialogue (with timestamps), Tone, Visual style, Standalone Context
3. **Explicitly exclude background music** in Constraints section
4. **Keep dialogue satirical and dry** - founder-to-founder inside jokes
5. **Reference character profiles** for consistency in personality and speaking style
# Tool Development Ideas (Archived)

## Web Designer Tool (`web_designer.py`)

**Context:** While building the OrchestrateOS landing page (Nov 2025), spent 30+ manual CSS edits and HTML changes that could've been one-liners with proper tooling.

**Problem:** Manual web design workflow is too slow:
- Find CSS selector → Edit properties → Test in browser (repeat 20+ times)
- Find HTML section → Delete entire block manually
- Add new components by hand-writing HTML/CSS
- Manual git push to deploy

**Solution:** Build a web designer tool with these functions:
- `update_css(file, selector, properties)` - Update CSS without manual find/replace
- `remove_section(file, section_id)` - Delete entire HTML sections cleanly
- `inject_css(file, css_rules)` - Add new CSS rules programmatically
- `create_component(type, config)` - Generate tooltips, modals, cards from templates
- `deploy(repo, message)` - Push to GitHub (integrate with existing `github_sync.py`)
- `preview(file)` - Open in browser with auto-reload on changes

**Pattern:** Abstract repetitive web design tasks into functions so site updates become one-liners instead of 20-30 manual edits. This is the OrchestrateOS meta-pattern - build the tools layer first, then execution becomes trivial.

**Priority:** Build when ready to iterate on sites faster.

**Date added:** 2025-11-01

## Reusable Component Patterns (Nov 2025 Landing Page Build)

**Context:** Identified these patterns during OrchestrateOS landing page redesign. Each pattern required 15-30 minutes of manual HTML/CSS/JS work that could be a single function call.

**Pattern Library:**

1. **Draggable Carousel**
   - What: Full-featured carousel with mouse/touch drag, auto-advance, smooth snapping
   - Use case: Feature showcases, comparison slides, testimonials
   - Code pattern: `carousel-container` → `carousel-track` → `carousel-slide` with drag event handlers
   - Key features: requestAnimationFrame for smooth drag, threshold-based snapping, auto-advance interval
   - Function signature: `create_carousel(slides, auto_advance_ms=8000, enable_drag=true)`

2. **Apple Sidebar Navigation**
   - What: Sticky sidebar with clickable nav items that reveal content panels
   - Use case: Feature lists, product specs, multi-section content
   - Code pattern: `.capabilities-nav` (left sticky) + `.capabilities-content` (right panel switcher)
   - Key features: Active state management, smooth transitions, mobile-responsive collapse
   - Function signature: `create_sidebar_nav(nav_items, content_panels, position='left')`

3. **Scroll Fade Animations**
   - What: Intersection Observer-based fade-in + slide-up on scroll
   - Use case: Section headers, feature cards, any element that should animate on viewport entry
   - Code pattern: `.scroll-fade` class + IntersectionObserver with 0.2 threshold
   - Key features: 0.8s ease timing, 30px translateY, automatic viewport detection
   - Function signature: `add_scroll_fade(selector, threshold=0.2, delay=0)`

4. **Visual Dashboard Cards**
   - What: Grid of cards with gradients, badges, status indicators, large metric numbers
   - Use case: Stats dashboards, execution reports, feature comparisons
   - Code pattern: 2x3 grid with purple gradient backgrounds, green "DONE" badges, gradient text numbers
   - Key features: Glassmorphism effects, contrasting badges, responsive grid
   - Function signature: `create_dashboard_grid(items, columns=2, card_style='gradient')`

5. **Comparison Cards**
   - What: Side-by-side comparison with category headers, metrics, descriptions
   - Use case: Before/after, traditional vs new, plan comparisons
   - Code pattern: Dual-panel cards with category label, metric display, description text
   - Key features: Consistent padding, contrasting colors, mobile stack
   - Function signature: `create_comparison_card(left_data, right_data, category)`

6. **Open Graph Meta Tags**
   - What: Complete social sharing meta tags for Twitter, Facebook, LinkedIn
   - Use case: Every public-facing page that should look good when shared
   - Code pattern: 8-10 meta tags in `<head>` with og:title, og:description, og:image, etc.
   - Key features: Auto-generates from page title/description, validates image dimensions
   - Function signature: `inject_og_tags(title, description, image_url, site_url)`

**Implementation Priority:**
- Build these as templates first (HTML/CSS/JS snippets with variable substitution)
- Then abstract into web_designer.py functions
- Store in `semantic_memory/component_patterns/` as reusable chunks
- Each pattern should include: HTML structure, CSS styles, JS behavior, usage example

**Meta Pattern:**
Every time you manually build a component 2+ times, extract it into this library. Don't rebuild - reuse and customize.

**Date added:** 2025-11-01
