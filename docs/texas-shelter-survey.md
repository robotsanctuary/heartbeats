# Texas shelter survey (2026-10-19)

Which Texas shelters publish their at-risk animals in a form we can collect.
Checked by fetching the pages on 2026-10-19; sizes are counts from that day.

Key finding: Dallas's 24petconnect RSS key (`id=td48ev36`) only works for
Dallas. Every other 24petconnect shelter tried (HSTN, HRRS, MTGM, SANT, WACO,
KLEN, TMPL, GARL, CRPC, PP*) returns an empty feed. So sharing Dallas's
software doesn't make a shelter a free add.

## Tier 1: per-animal deadline dates

| Shelter | Source | Format | Now | Effort |
|---|---|---|---|---|
| Fort Worth ACC | fortworthtexas.gov/departments/code-compliance/animals/urgent-placement-pets | HTML list (8 pages) + detail page "Review scheduled for <date>" (when euthanasia risk starts) | ~90-96 | Medium |
| San Antonio ACS | sanantonio.gov/acs/ACS_website_euth_capacity.pdf (+ ACS_website_urgent_medical_animals.pdf) | Text PDF, nightly; "I need to leave by MM/DD/YYYY or I may be euthanized"; photos embedded | 19 dogs + 50 medical (no date) | Medium |
| Austin Animal Center | austintexas.gov/animal-services/urgent-and-rescue-placement -> published Google Sheets (CSV) | Rescue-only list has "Euth Deadline"; urgent list has none; no photos (join Adopets by ID) | 5 + 19 | Easy |
| Houston BARC | houstontx.gov/barc/barcdata/BARC_LOSV2.pdf | 15 MB PDF, 21 pages, "DueOut Date" (release date, not explicit euth date) | many | Hard |

## Tier 2: urgent flag, no date

| Shelter | Source | Format | Now | Effort |
|---|---|---|---|---|
| Abilene (All Kind) | shelterluv.com/api/v3/available-animals/41906?saved_query=4334&embedded=1 | JSON, "URGENT LIST" attribute | 13 | Easy |
| El Paso | petbridge.org/animals/animals-all-responsive.php?ClientID=35&Filter=At-Risk&Species=All | HTML fragment + detail pages (days in care, reason) | 16 | Easy-Medium |
| Collin County (McKinney/Frisco) | api.collincountytx.gov/AnimalShelterAPI/.../AnimalSearch | XML, Stage='Pre-Euthanasia' | 1 | Easy |
| Garland | Google Sheet linked from garlandtx.gov/191 (link changes; re-read each run) | Sheet: RSQ / A/R status, reason | 53 | Medium |
| Arlington | Petango iframe, stageID=14285 "VIP Rescue Only" | HTML | 15 | Medium |
| San Marcos | ci.san-marcos.tx.us/4423/At-Risk-List | HTML table with Deadline column (empty today) | 16 | Medium |

## No public at-risk list (general listing only)

Harris County (686 animals; euth notices emailed to rescues only), Montgomery
County, Fort Bend, Galveston, Corpus Christi, Waco, Killeen, Temple, Lubbock,
Midland, San Angelo, Wichita Falls, Smith County (Tyler), Longview, Mesquite,
Grand Prairie, Tri-City (Cedar Hill), Odessa, Aggieland Humane, New Braunfels
(HSNBA), Williamson County (urgent = length of stay, site Cloudflare-blocked).
Frisco and Tarrant County have no shelter of their own.

## Blocked / not identified (bot walls)

Irving, Carrollton, Plano, Amarillo, Laredo, Brownsville, Beaumont, Denton's
urgent list, Lewisville. Need a manual browser visit.

Full subagent notes: ~/.hermes/cache/delegation/live/deleg_c318fa74/
