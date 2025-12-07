# Product Hunt Launch: Division of Labor (Srini vs Claude)

## Overview

The Product Hunt Launch Plan spec is comprehensive. This update clarifies **who does what** and accounts for work already in progress (email newsletters sent, beta flow established).

---

## Status: What's Already Done

**Email Infrastructure:**
- Newsletters already sent to 6K subscribers
- Beta signup flow is live and tested
- Email list is warmed (no cold outreach needed day-of)

**Assets Partially Complete:**
- Demo video exists (investor walkthrough)
- Landing page is live (orchestrateos.com)
- Architecture diagrams available
- Tool inventory documented (47 tools)

**What Still Needs Work:**
- Product Hunt-specific gallery assets
- Launch day copy (tagline, description, maker comment)
- Coordinated social media push
- Day-of monitoring and engagement

---

## Division of Labor: Srini vs Claude

### Srini's Responsibilities (Human-Only Tasks)

**Pre-Launch (7 Days Before):**
- [ ] **Final positioning call**: Review tagline/description drafts from Claude, decide which to use
- [ ] **Hunter selection** (if applicable): Reach out to potential hunters with established PH followings
- [ ] **Influencer outreach**: Personal DMs to AI/dev influencers for launch day support
- [ ] **Set launch date**: Choose optimal day (Tue-Thu, check PH calendar for competitor launches)

**Launch Day:**
- [ ] **Be online all day**: Respond to comments personally (< 15 min response time)
- [ ] **Monitor rankings**: Track position vs competitors hourly
- [ ] **Engage authentically**: Answer questions with depth, not generic "Thanks!"
- [ ] **Share updates**: Tweet milestones ("#3 Product of the Day!" → "#1!")
- [ ] **Rally supporters**: Text/DM key supporters during slow momentum periods

**Post-Launch:**
- [ ] **Thank supporters personally**: Individual messages to top commenters
- [ ] **Conduct retrospective**: What worked, what didn't, what to replicate
- [ ] **Follow up with beta users**: Personal check-ins with early testers

### Claude's Responsibilities (Automatable Tasks)

**Phase 1: Asset Creation (7 Days Before)**
- [ ] **Draft tagline options** (5 variations, 60 char max)
- [ ] **Write product description** (260 char, hook + proof + CTA)
- [ ] **Create maker comment** (founder story + problem + solution + proof + CTA)
- [ ] **Generate gallery image prompts** for Ideogram (6 images: architecture, dashboard, tools, workflow, comparison, testimonial)
- [ ] **Script demo video** (30-60s: problem → solution → proof → CTA)
- [ ] **Write pre-launch email sequence** (Day -7, Day -3, Day -1 emails)
- [ ] **Draft social media posts** (Twitter threads, LinkedIn posts, Reddit posts)

**Phase 2: Pre-Launch Coordination (3-7 Days Before)**
- [ ] **Schedule social posts** using Buffer (timing optimized for engagement)
- [ ] **Prepare comment response templates** (generic thank-you, feature request, comparison, criticism)
- [ ] **Generate analytics dashboard** (track PH traffic, beta signups, conversion rates)
- [ ] **Create monitoring checklist** (upvote velocity, comment engagement, external referrals)

**Phase 3: Launch Day Support**
- [ ] **Post at 12:01 AM PST**: Submit Product Hunt listing (if Srini delegates this)
- [ ] **Send email blast**: Trigger newsletter to full list with PH link
- [ ] **Publish social posts**: Twitter, LinkedIn, Reddit, Indie Hackers, Hacker News
- [ ] **Monitor metrics**: Log upvote count, comment count, ranking changes every hour
- [ ] **Generate mid-day report**: Tweet thread summarizing PH comments/questions at 12 PM
- [ ] **Track external traffic**: Google Analytics → PH referral conversions

**Phase 4: Post-Launch Documentation**
- [ ] **Create wrap-up thread**: "We launched on Product Hunt. Here's what happened."
- [ ] **Write results analysis doc**: Final ranking, upvotes, comments, signups, lessons learned
- [ ] **Draft "How We Did It" blog post**: Tactical breakdown for Medium/dev.to
- [ ] **Update marketing materials**: Add "#1 Product of the Day" badge to website, GitHub, etc.

---

## Task Assignment (Batch for Claude)

**Immediate Next Steps (Assign to Queue):**

1. **`draft_ph_tagline_options`** - Generate 5 tagline variations (60 char max)
2. **`write_ph_product_description`** - 260 char description (hook + proof + CTA)
3. **`create_ph_maker_comment`** - Founder story + architectural proof
4. **`generate_ph_gallery_prompts`** - 6 image prompts for Ideogram
5. **`draft_ph_prelaunch_emails`** - Day -7, Day -3, Day -1 email templates
6. **`write_ph_social_posts`** - Twitter threads, LinkedIn, Reddit posts
7. **`create_ph_comment_templates`** - Response templates for different scenarios
8. **`build_ph_monitoring_dashboard`** - Metrics tracking + hourly log format

**Day-Of Execution (Trigger When Ready):**

9. **`send_ph_email_blast`** - Email 6K subscribers at 12:01 AM PST
10. **`publish_ph_social_posts`** - Post to all channels with PH link
11. **`generate_ph_midday_report`** - Tweet thread at 12 PM with comment summary
12. **`create_ph_wrapup_thread`** - Post-launch results tweet thread

---

## Adjustments for "Newsletters in Progress"

**Original Plan Said:**
- Email list needs warming with 3-email sequence (Day -7, Day -3, Day -1)
- Beta signup flow needs testing
- Cold outreach required day-of

**Current Reality:**
- Email list already warmed (newsletters sent regularly)
- Beta signup flow is live and functional
- **Adjustment**: Skip multi-stage email warm-up. Send single pre-launch announcement (Day -1) and launch blast (12:01 AM).

**Revised Email Strategy:**
- **Day -1 (11 AM PST)**: "We're launching on Product Hunt tomorrow. Here's why you should care."
  - Brief architecture explanation
  - Link to demo video
  - Ask for support: "Upvote, comment, share"
- **Launch Day (12:01 AM PST)**: "We're live on Product Hunt right now."
  - Direct PH link
  - One-sentence ask: "Support us with an upvote and comment"
  - Pre-written tweet they can share

**What This Saves:**
- 2 fewer emails (reduces list fatigue)
- Simpler coordination (only 2 sends instead of 4)
- Still achieves goal: warm audience ready to act on launch day

---

## Launch Day Timeline (Revised)

**12:01 AM - Launch**
- Srini or Claude: Submit Product Hunt post
- Claude: Trigger email blast + social posts
- Srini: Post maker comment, share to personal Twitter

**12:01 AM - 6:00 AM - Overnight Push**
- Claude: Monitor upvote velocity, log metrics hourly
- Srini: Sleep (delegate monitoring to Claude)

**6:00 AM - Morning Check**
- Srini: Review comments, respond to critical questions
- Claude: Generate morning summary report (upvotes, comments, ranking)

**9:00 AM - 9:00 PM - Active Engagement Window**
- Srini: Online all day, respond to comments < 15 min
- Claude: Share updates to Twitter, monitor metrics, generate mid-day report
- Both: Coordinate external traffic pushes (Twitter threads, LinkedIn, Medium)

**9:00 PM - End of Day**
- Srini: Final ranking check, thank top supporters
- Claude: Generate end-of-day report (final stats, beta signups, conversion rates)

---

## Success Metrics (Unchanged)

**Primary Goal:** #1 Product of the Day

**Secondary Goals:**
- 400+ upvotes
- 50+ comments
- 500+ beta signups
- 10+ quality discussions in comments
- 5+ influencer mentions/shares

---

## Next Actions

**For Srini:**
1. Review this division of labor doc
2. Confirm launch date (recommend next Tue-Thu)
3. Assign Claude tasks to queue using batch_assign_tasks
4. Schedule personal calendar block for launch day (12:01 AM - 11:59 PM PST)

**For Claude:**
1. Wait for task assignment
2. Execute asset creation tasks (tagline, description, emails, social posts)
3. Prepare monitoring dashboard for launch day
4. Stand by for launch day execution triggers

---

**Doc ID Reference:** This updates `Product Hunt Launch Plan – OrchestrateOS` (a57418a5-798b-4f0c-8a18-dbd7f63eb975)

#Inbox
