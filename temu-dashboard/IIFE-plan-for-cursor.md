# Temu Dashboard IIFE Wrapping Plan — for Cursor

## Backup
Safe copy at: C:\Users\an'kang\Desktop\POD智能定制\temu-dashboard.html.cursor-safety
If anything fails: copy the safety file back over temu-dashboard.html.

## Goal
Wrap each page render function and its private helpers in IIFE (Immediately Invoked Function Expression). 
Only the main render function is exposed to `window.`; helper functions stay private inside the IIFE scope.

## File
C:\Users\an'kang\Desktop\POD智能定制\temu-dashboard.html
~1500 lines, UTF-8 with CRLF line endings.

## Confirmed: Single IIFE Works
A single IIFE on `renderProducts` was tested and verified to work:
```
window.renderProducts = (function() {
    function renderProducts() { ... }
    return renderProducts;
})();
```
The switchPage mechanism calls render functions by name (e.g. `renderProducts()`) from the global scope. 
Assigning to `window.renderXxx` exposes the function correctly in non-strict mode.

## Confirmed: Top-Down Insertion Fails  
Previous attempts failed because lines were inserted top-down, shifting all subsequent line numbers.
The fix: process BOTTOM-UP so that earlier inserts do not affect later ones.

## Function Boundaries (0-based line numbers, use with `-split "`r`n"`)
```
renderImportPage        open=905  close=921   standalone IIFE
renderProducts          open=926  close=944   standalone IIFE
renderRules             open=945  close=963   standalone IIFE
renderPredict           open=964  close=972   standalone IIFE
doPrediction            open=973  close=989   STAY GLOBAL (called by onclick="doPrediction()")
renderBlacklist         open=990  close=1016  standalone IIFE
─── ⑥ diagnosis GROUP (single IIFE) ───
compareSnapshots        open=1021 close=1063  PRIVATE (inside group)
suggestPruning          open=1065 close=1089  PRIVATE (inside group)
generateDirectionAdvice open=1094 close=1128  PRIVATE (inside group)
renderDiagnosis         open=1133 close=1293  EXPOSED as window.renderDiagnosis
─── end group ───
renderStorePage         open=1298 close=1362  standalone IIFE
─── ⑧ PK GROUP (single IIFE) ───
renderPKPage            open=1366 close=1382  EXPOSED as window.renderPKPage
renderPKWithBoth        open=1384 close=1461  PRIVATE (inside group)
renderPKNoStore         open=1462 close=1466  PRIVATE (inside group)
renderPKNoProducts      open=1468 close=1472  PRIVATE (inside group)
renderPKNoData          open=1474 close=1478  PRIVATE (inside group)
─── end group ───
```

## Implementation: Bottom-Up Insertion

Read the file as a list of lines. Process from BOTTOM to TOP. Each IIFE adds exactly 3 lines (open + return + close). Track offset.

### Pattern for standalone IIFE (e.g. renderProducts):
```
BEFORE:
  function renderProducts() {
      ...body...
  }

AFTER:
  window.renderProducts = (function() {
      function renderProducts() {
          ...body...
      }
      return renderProducts;
  })();
```

### Pattern for GROUP IIFE (diagnosis group):
```
BEFORE:
  function compareSnapshots() { ... }
  function suggestPruning() { ... }
  function generateDirectionAdvice() { ... }
  function renderDiagnosis() { ... }

AFTER:
  window.renderDiagnosis = (function() {
      function compareSnapshots() { ... }
      function suggestPruning() { ... }
      function generateDirectionAdvice() { ... }
      function renderDiagnosis() { ... }
      return renderDiagnosis;
  })();
```

### Pattern for GROUP IIFE (PK group):
BEFORE: all PK functions in sequence
AFTER: `window.renderPKPage = (function(){ ...all PK functions... return renderPKPage; })();`

### Pseudocode:
```
lines = ReadAllLines(file)
groups = [
    {name:"⑧ pk", open:1366, close:1478, win:"renderPKPage", members:["renderPKPage","renderPKWithBoth","renderPKNoStore","renderPKNoProducts","renderPKNoData"]},
    {name:"renderStorePage", open:1298, close:1362, win:"renderStorePage"},
    {name:"⑥ diagnosis", open:1021, close:1293, win:"renderDiagnosis", members:["compareSnapshots","suggestPruning","generateDirectionAdvice","renderDiagnosis"]},
    {name:"renderBlacklist", open:990, close:1016, win:"renderBlacklist"},
    {name:"renderPredict", open:964, close:972, win:"renderPredict"},
    {name:"renderRules", open:945, close:963, win:"renderRules"},
    {name:"renderProducts", open:926, close:944, win:"renderProducts"},
    {name:"renderImportPage", open:905, close:921, win:"renderImportPage"},
]

offset = 0
for each group in reversed(groups):    // BOTTOM-UP
    op = group.open
    cl = group.close + offset          // adjust for prior inserts
    op = op + offset
    
    if group has members:              // GROUP: one IIFE for all
        // Indent the first member
        lines[op] = "    " + lines[op]
        // Insert window.xxx = (function() { before the group
        lines.insert(op, "window." + group.win + " = (function() {")
        // Insert return + })(); after the group
        lines.insert(cl + 1, "    return " + group.win + ";")
        lines.insert(cl + 2, "})();")
        offset += 3
    else:                              // STANDALONE: one IIFE
        // Indent the function
        lines[op] = "    " + lines[op]
        lines.insert(op, "window." + group.win + " = (function() {")
        lines.insert(cl + 1, "    return " + group.win + ";")
        lines.insert(cl + 2, "})();")
        offset += 3

WriteAllLines(lines)
```

## Verification After Implementation
1. Search for `return renderXxx` for all 8 render functions (import/products/rules/predict/blacklist/diagnosis/store/pk)
2. Count `<div`, `</div>`, `<details`, `</details>` — must balance
3. Search for `g.sf(` to ensure no regression
4. Open in browser, upload Excel data, click all 8 sidebar items
5. If any page does not switch: git checkout the safety file

## Critical Rules
- `doPrediction` line 973 MUST NOT be wrapped (called by onclick="doPrediction()" from innerHTML)
- `compareSnapshots`, `suggestPruning`, `generateDirectionAdvice` are PRIVATE inside diagnosis group IIFE — NOT exposed to window
- `renderPKWithBoth`, `renderPKNoStore`, `renderPKNoProducts`, `renderPKNoData` are PRIVATE inside PK group IIFE — NOT exposed to window
- Use CRLF line endings (`r`n)
- Process BOTTOM-UP to avoid line number shifts
- Track cumulative offset as lines are inserted
