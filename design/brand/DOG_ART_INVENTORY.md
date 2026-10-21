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

## Pitbull lie-down (owner zip, 2026-10-21) — cells 132-158 (L1-27) + 159-164 (idle I1-6)
880x361 canvas with travel, ground y=345. L1-11 walk in, L12-16 slow/stop, L17-21 front lowers (bow), L22-23 rear lowers
(eyes squint), L24-27 lying sphinx pose, head up, panting. Idle = lying pant loop (eyes open, 0.5s/6 frames).
Packed with `dog_art.build_travel(..., scale=149/399, top_y=0, floor_y=345, on_top=0, on_floor=1)` (all floor frames).
Vision notes: L23->L24 pops (tail upright->flat, eyes closed->open, head a bit bigger). No sleep (eyes closed / head
on paws) and no get-up frames yet.

## Pitbull belly rub (owner zip, 2026-10-21) — cells 165-196 (B1-32) + 197-214 (wiggle W1-18)
710x417 canvas, ground y=401, per-frame timing in orig/meta.json (durations_ms, wiggle 83ms).
B1-6 lying -> pushes up, B7-13 stands/trots, B14-18 head dips + rolls, B19-32 on back, W1-18 paws-up wiggle loop.
Packed with `dog_art.build_travel(..., scale=0.379, top_y=0, floor_y=401, on_top=0, on_floor=1)`.
Lab hover box takes turns: give paw / belly rub (starts at B8 standing; get-up = roll frames reversed).
Vision notes: B21->B22 belly colour/pose pop; leg tangles in some on-back frames (B27, W3, W11, W15).

## Pitbull lying tail wag (owner zip, 2026-10-21) — cells 215-226 (G1-12)
Seamless 12-frame loop, 0.5s (41.7 ms/frame), same 880x361 canvas as lie-down; G1 matches lie-down L27.
Packed with `dog_art.build_travel(..., scale=149/399, top_y=0, floor_y=345, on_top=0, on_floor=1)`.
Lab: lie down -> tail wag 2.5s -> panting loop.
