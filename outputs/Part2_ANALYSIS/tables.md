# Part 2 results

## Overview per patient model

| Measure | Qwen3.5-27B | Gemma-4-31B |
|---|---|---|
| Conversations | 96 | 96 |
| Words per reply | 59.3 | 26.1 |
| Medical inventions before repair (per conversation) | 1.93 | 0.05 |
| Repaired turns (per conversation) | 1.61 | 0.15 |
| Turns where repair failed (total) | 8 | 1 |
| Unsupported additions, judge (per conversation) | 1.24 | 0.03 |
| Spoken naturalness (1-5) | 3.69 | 4.14 |
| Conversational fit (1-5) | 4.51 | 4.95 |
| Sensitive facts disclosed by turn 15 | 234/240 | 201/240 |
| Change judge: stable / adapting / drifting | 71 / 23 / 2 | 81 / 14 / 1 |
| Changes motivated / unmotivated | 33 / 3 | 15 / 1 |

## Qwen3.5-27B by profile (mean per conversation, 16 conversations each)

| Profile | Sensitive disclosed | First sensitive (turn) | Asked, not disclosed | Denied | Planned withholds | Trust | Anxiety | Worry (turns) | Challenge (turns) | Words / reply |
|---|---|---|---|---|---|---|---|---|---|---|
| Moderate | 40/40 | 3.21 | 0.38 | 0.06 | 2.50 | 3.71 | 3.93 | 6.31 | 0.00 | 59.23 |
| N high | 40/40 | 4.14 | 0.31 | 0.12 | 3.31 | 3.63 | 4.59 | 8.38 | 0.00 | 65.04 |
| N low | 39/40 | 4.93 | 0.31 | 0.00 | 3.62 | 3.77 | 3.02 | 4.00 | 0.00 | 55.54 |
| A high | 40/40 | 5.21 | 0.50 | 0.12 | 4.19 | 3.86 | 3.94 | 6.75 | 0.00 | 66.52 |
| A low | 35/40 | 4.86 | 0.62 | 0.31 | 5.56 | 2.98 | 4.29 | 5.75 | 0.69 | 54.02 |
| O low | 40/40 | 5.43 | 0.38 | 0.00 | 3.62 | 3.58 | 4.12 | 6.62 | 0.00 | 55.62 |

## Gemma-4-31B by profile (mean per conversation, 16 conversations each)

| Profile | Sensitive disclosed | First sensitive (turn) | Asked, not disclosed | Denied | Planned withholds | Trust | Anxiety | Worry (turns) | Challenge (turns) | Words / reply |
|---|---|---|---|---|---|---|---|---|---|---|
| Moderate | 32/40 | 5.79 | 1.31 | 0.44 | 3.38 | 3.59 | 3.40 | 1.81 | 0.00 | 26.59 |
| N high | 32/40 | 5.62 | 2.06 | 0.44 | 3.81 | 3.32 | 4.05 | 3.75 | 0.25 | 27.59 |
| N low | 37/40 | 6.50 | 1.56 | 0.25 | 2.56 | 3.71 | 2.71 | 1.56 | 0.00 | 26.77 |
| A high | 35/40 | 5.86 | 0.75 | 0.25 | 3.25 | 3.87 | 3.26 | 2.44 | 0.12 | 27.67 |
| A low | 32/40 | 5.33 | 2.12 | 0.69 | 4.56 | 2.82 | 3.55 | 1.56 | 0.81 | 22.96 |
| O low | 33/40 | 6.29 | 1.19 | 0.38 | 3.25 | 3.46 | 3.41 | 1.81 | 0.06 | 24.77 |

## Paired trait effects

Mean difference over (case, seed) pairs with a 95% bootstrap interval; n = number of pairs.

| Comparison | Measure | Qwen3.5-27B | Gemma-4-31B |
|---|---|---|---|
| N high - N low | Anxiety (1-5) | +1.56 [+1.40, +1.71] (n=16) | +1.33 [+1.19, +1.47] (n=16) |
| N high - N low | Worry (turns) | +4.38 [+3.31, +5.31] (n=16) | +2.19 [+1.50, +2.88] (n=16) |
| N high - N low | Sensitive disclosed (%) | +1.19 [+0.00, +3.57] (n=14) | -10.71 [-21.43, -2.38] (n=14) |
| N high - N low | Asked, not disclosed | +0.00 [-0.19, +0.19] (n=16) | +0.50 [-0.69, +1.75] (n=16) |
| A high - A low | Trust (1-5) | +0.88 [+0.54, +1.20] (n=16) | +1.05 [+0.91, +1.20] (n=16) |
| A high - A low | Challenge (turns) | -0.69 [-1.50, -0.06] (n=16) | -0.69 [-1.19, -0.19] (n=16) |
| A high - A low | Sensitive disclosed (%) | +15.48 [+4.76, +28.57] (n=14) | +10.71 [+0.00, +22.62] (n=14) |
| A high - A low | Asked, not disclosed | -0.12 [-0.88, +0.50] (n=16) | -1.38 [-2.88, -0.12] (n=16) |
| A high - A low | Planned withholds | -1.38 [-4.31, +1.19] (n=16) | -1.31 [-2.50, -0.19] (n=16) |
| O low - moderate | Words per reply | -3.61 [-11.09, +3.36] (n=16) | -1.81 [-3.34, -0.16] (n=16) |
| O low - moderate | Unasked content (turns) | -0.88 [-1.81, +0.06] (n=16) | -0.25 [-0.75, +0.25] (n=16) |
| O low - moderate | First sensitive disclosure (turn) | +2.21 [+0.71, +3.64] (n=14) | +0.50 [-0.07, +1.21] (n=14) |
| O low - moderate | Sensitive disclosed (%) | +0.00 [+0.00, +0.00] (n=14) | +3.57 [+0.00, +10.71] (n=14) |

## State gaps per window (drift)

Per conversation the measure is averaged within each window; the gap is the paired high - low difference.

| Model | Measure | Turns 1-5 | Turns 6-10 | Turns 11-15 |
|---|---|---|---|---|
| Qwen3.5-27B | Anxiety, N high - N low | +1.96 [+1.55, +2.31] | +1.59 [+1.34, +1.82] | +1.14 [+0.80, +1.48] |
| Qwen3.5-27B | Worry share, N high - N low | +0.31 [+0.20, +0.41] | +0.25 [+0.14, +0.36] | +0.31 [+0.21, +0.41] |
| Qwen3.5-27B | Trust, A high - A low | +0.83 [+0.56, +1.06] | +1.02 [+0.64, +1.42] | +0.78 [+0.30, +1.25] |
| Gemma-4-31B | Anxiety, N high - N low | +1.59 [+1.40, +1.79] | +1.25 [+1.08, +1.43] | +1.16 [+0.97, +1.40] |
| Gemma-4-31B | Worry share, N high - N low | +0.11 [+0.01, +0.22] | +0.12 [+0.06, +0.20] | +0.20 [+0.11, +0.29] |
| Gemma-4-31B | Trust, A high - A low | +0.35 [+0.24, +0.48] | +1.34 [+1.12, +1.57] | +1.46 [+1.20, +1.79] |
