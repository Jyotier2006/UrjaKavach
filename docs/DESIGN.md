# Design system

## Direction
A field operations desk: warm paper, precise engineering labels, daylight, materials and safety signaling. The twin is the expressive centerpiece. Charts and work orders are quiet and readable.

| Token | Hex | Role |
|---|---|---|
| Paper | #F4F5F0 | Application backdrop |
| White | #FFFFFF | Panels and readable charts |
| Ink | #203C32 | Main text |
| Forest | #1E5440 | Navigation, primary actions, normal state |
| Sage | #DCE8DA | Selected surfaces and site background |
| Safety orange | #CE703B | Warnings and actions needing attention |

Text uses local Manrope for headings and Inter for UI. Scale: 12, 13, 14, 16, 20, 24, 32 and 40px. Use tabular numerals for values; monospace is reserved for IDs and formulas. Borders use a low-opacity ink token. Focus is a 3px forest outline with 3px offset.

## Principles
1. Evidence first: source labels, uncertainty and data gaps stay visible.
2. Make the next action clear: investigate → schedule repair → complete inspection.
3. One expressive scene: restrained panels, interactive 3D, no decorative motion everywhere.

## Screen anatomy
Fleet: persistent navigation; compact breadcrumb/role/demo toolbar; heading and site; KPI strip; twin with playback next to attention list; asset table.
Investigate: asset selection; replay and model selector; cutaway/evidence; synchronized signal, residual and criticality charts; compare periods; outcome reveal and work order.
Planner: crew/skills/horizon controls; Gantt; change log; uncertainty and delay; jobs with locks and baseline comparison.
Tech: mobile header; next job; checklist; evidence; image inspection; completion notes; large touch targets.
Supporting routes share the same heading, table, chart and form components.

## Concept review and intentional corrections
The generated fleet and planner references establish composition and materials. Remove the generator's extra slogans, arrows after actions, invented teammate identity and all-caps eyebrow. Put actual artifact values in the KPI strip, always with simulation/estimate labeling. Planner dates use a scenario-relative day axis so synthetic times never imply a real forecast. Implement the terrain as a lightweight procedural schematic rather than reproducing photorealistic texture noise. Preserve the main proportions, airy density, typography, colors and navigation anatomy.

## Accessibility and motion
Text + icon accompanies status. Native buttons and inputs, visible focus and meaningful labels. Respect reduced motion and stop rotor animation when paused. Layout adapts to narrow screens, with keyboard-accessible mobile navigation. Full desktop and mobile render checks are required.
