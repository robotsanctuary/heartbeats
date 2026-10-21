# Dog art inventory (2026-10-21)

Contact sheet: /Volumes/Extreme/heartbeats-data/site-shots/dog-inventory.jpg (labels below match it).
Style match with J (the original golden puppy): J, R, L same; F, Wa close; Wb and Wc are different drawings.

| Set | Folder | Frames | Usable for |
|---|---|---|---|
| J jump | dog-src-jump | J1 sit, J2-6 leap stretched, J7 rear up, J8 sit tall, J9 rising leap, J10 spring, J11 low leap, J12 crouch (edge cut) | sit, jump up |
| R run | dog-src-run | R1-R8 leap/stretch variants, R2 sit, R9 spring, R10 sit, R11 broken | bounding run |
| L land | dog-src-land | L1 dive, L2 front paws down, L3 crouch | jump down (done) |
| F frolic | dog-src-frolic | F1/F7/F8 standing, F2 trot step, F3-F6 stretch | standing pose, frolic (weak) |
| Wa walk v1 | dog-src-walk-v1 | 8 near-identical strides | not useful |
| Wb walk v2 | dog-src-walk | front paws only | not useful (different style) |
| Wc walk v3 | art-inbox/walk3-234145 | Wc1 stand, Wc2-5 near front step, Wc9-12 broken | not useful (different style) |

Gaps: walk (back legs never lift), lie down, sleep, real gallop gather pose, sniff, give paw.
Prompts for the gaps are in the chat of 2026-10-21; base image = F1 (standing, J style).

## Pitbull jump-down (owner zip, 2026-10-21) — cells 111-131
21 real-RGBA frames on a 1016x649 canvas that includes travel (box top y=331, floor y=633, box right edge x=439).
1-3 walk to edge, 4-7 crouch/lean over, 8-10 push off, 11-14 dive, 15-16 FRONT paws land, 17-19 rear drops, 20-21 stand.
Packed with `dog_art.build_travel(..., scale=149/399, top_y=331, floor_y=633, on_top=10, on_floor=19)` -> `dog-pitbulljumpdown.png/.json`
(dx/up/hind per frame; the lab replays the motion). Timing from `orig/dog_jumpdown.css` (5.168s).
Vision notes: ears look pointier in 11-16 (dive); frame 21 turns toward the viewer (3/4 view) — may "pop" when joining the walk.
