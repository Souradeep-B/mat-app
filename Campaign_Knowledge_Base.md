# Campaign Knowledge Base

## Purpose

Stores campaign-specific learnings accumulated from each audience pull. This is separate from the master skill (`Marketing_automation_skill.md`) which contains only generic rules.

**Before building any query — always check this file first for a prior similar campaign.**

---

## How to Use

- **Check before building:** look for an entry matching the same client + campaign type
- **Cross-client application:** if the method is exactly the same, it can be applied to a different client — but only if the logic is identical, not just similar
- **Activity methods:** all activity-fetching approaches are stored here, not in the master skill
- **Auto-populated:** entries are added automatically during each audience pull when campaign-specific knowledge is learned

---

## Entries

*(No entries yet — will be populated as audience pulls are completed)*

---

## Entry Template

```
### [Client] — [Campaign Type] — [Year]
**OPM Ticket:** OPM-XX
**WF Number:** WFXXXXXXXX
**Campaign:** [Campaign name]
**Channel:** Email / Direct Mail / Both

#### What was unique about this pull
- [Specific filter, activity logic, or approach that was non-standard]

#### Activity details (if activity-based)
- External Activity ID(s): [e.g., OPTUM.HEALTHSURVEY.COMPLETE]
- Method used: Method A (target_loyalty__user_target) / Method B (incentive_earning_detail)
- Primary source used: CRD / Sanity MCP / Databricks production_sanity_data
- How fetched: [Steps taken to resolve the correct external_activity_id and target_rule_id — which source confirmed it]

#### Reusable for
- [Same client next year / Different client with same activity type / etc.]
```

---

## ROI Entry Template

Use this when a new ROI metric or report structure is discovered (via "Ask MAT" or a new campaign type). Save immediately after the metric is confirmed working.

```
### [Client] — [Campaign Type] — ROI — [Year]
**OPM Ticket:** OPM-XX
**Campaign:** [Name]

#### Campaign intent (what the email was trying to achieve)
- [e.g. Remind users to redeem gift card / Drive activity completions / Move users from 0% to 100%]

#### ROI structure used
- Sections shown: [e.g. Delivery counts + Incentive completion change + Bucket distribution + Migration matrix]
- Buckets: [e.g. 0%, 1-25%, 26-50%, 51-75%, 76-99%, 100% — or custom if different]
- T+N used: [e.g. T+15 scheduler / T+30 manual]

#### Additional metrics (added via Ask MAT)
- **Metric:** [Description, e.g. gift card redemption rate]
- **Table used:** [Full table name + schema]
- **Query approach:** [How it was scoped to campaign user IDs]

#### T+N user population query
- Source: [read_api_9000084.contact_info + campaign_group — or override if different]
- Any special scoping needed: [e.g. exclude members who left the plan between T+0 and T+N]

#### Reusable for
- [Same client next year / Different client with same campaign type / etc.]
```
