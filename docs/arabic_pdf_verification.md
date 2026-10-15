# Arabic / English PDF visual verification

Shaping path (one only): `arabic-reshaper` (logical order, used for wrapping)
then `python-bidi` (visual order, applied once per line). ReportLab is not
asked to shape text itself.

## Run

    python scripts/arabic_pdf_check.py arabic_check.pdf --png --docx

Use the bundled font (`resources/fonts`) for the real release check. A system
font is accepted for development only and must not be shipped.
Keep the generated PNGs as evidence (`arabic_check_p1.png`, ...).

## Checklist (mark each as Pass / Fail / Not Tested)

| # | Check | Sample section | Result |
|---|-------|----------------|--------|
| 1 | Letters joined, text reads right-to-left | 1 | |
| 2 | Punctuation at the correct end: ، ؟ ( ) « » " | 1 | |
| 3 | Digits (123 and ١٢٣) keep their order inside Arabic text | 2 | |
| 4 | Mixed Arabic/English keeps English words readable and in order | 2 | |
| 5 | Explicit `rtl` paragraph (digits/English only) is right-aligned | 2 | |
| 6 | English paragraph stays left-to-right | 2 | |
| 7 | Long Arabic paragraph wraps without reversed or duplicated lines | 3 | |
| 8 | Ordered/bulleted list markers on the right for Arabic items | 4 | |
| 9 | Arabic table: first column on the right, cells readable | 5 | |
| 10 | English table stays left-to-right | 5 | |
| 11 | Header shows the Arabic title; footer shows the page number | all | |
| 12 | Word sample (`--docx`): Arabic paragraphs are RTL, tables mirrored | all | |

## Common failure signs

- Isolated, unjoined letters: shaping was skipped or the font lacks the glyphs.
- Reversed word order inside a line: bidi applied twice, or not applied.
- Missing glyph boxes: the font has no Arabic presentation forms.
- Parentheses/quotes on the wrong side: wrong base direction for the line.

## Known limitations (update after each run)

- Line breaking is done per paragraph before bidi reordering; very narrow table
  columns may break Arabic words awkwardly.
- No kashida justification; text is right-aligned, not justified.

## Run log

| Date | Font | Tester | Result summary |
|------|------|--------|----------------|
|      |      |        |                |