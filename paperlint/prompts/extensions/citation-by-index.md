# Citation Extension: Line-Indexed References

> **Status: NOT YET WIRED** — The orchestrator does not append this file to Discovery.
> Line-only references conflict with quote-based verification unless the pipeline gains
> a resolver from line indices back to exact spans.

_Addendum for non-Anthropic models. Intended to be appended to the Discovery system prompt when the Citations API is not available._

---

## How to Reference the Document

The paper has been pre-processed into a line-numbered format organized by section. Each line has a number. Each section has a heading.

**When you find a defect, reference it by section and line number.** Do not quote the text. Point to it.

Example — instead of:
```
Quoted text: "this is is undefined behaviour"
```

Write:
```
Location: §1 Abstract, L3-L4
Defect: "is" is doubled
Correction: remove the duplicate "is"
```

The reader can look up §1, lines 3-4 to see the exact text. You do not need to reproduce it.

## Why

- You cannot misquote what you never quoted
- Line references are verifiable — the reader checks the line, not your memory
- The orchestrator can resolve line references back to exact text if needed

## Rules

- Always provide the section identifier (§ number or heading) AND line number(s)
- Use line ranges for multi-line defects: L15-L17
- If a defect spans sections, cite both: §3 L45 – §4 L2
- One location per finding — do not cite multiple locations in a single finding
