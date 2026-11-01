# Anna (29F, Anemia)

## Turn 1 (opening)

**Doctor:** Hello Anna, I see you've come in because you've been feeling very tired. Can you tell me a bit about that?

**Facts:**
- `M12` I am too tired to do usual activities; I stay in bed all day.

**Background:**
- `M0` I have been diagnosed with anemia.
- `M4` I have a headache.
- `M9` I am short of breath and have real difficulty breathing.
- `M10` I feel slightly dizzy and lightheaded.
- `M13` I have chronic kidney failure.

## Turn 2 (broad)

**Doctor:** Is there anything else you've noticed about your health lately?

**Facts:**
- `M15` My skin is much paler than usual.

**Background:**
- `M16` I have noticed bright red blood in my stool.

## Turn 3 (focused)

**Doctor:** Do you ever feel like you might faint?

**Facts:**
- `M11` I feel lightheaded and dizzy, as though I might faint.

## Turn 4 (focused_pain)

**Doctor:** Have you had any pain anywhere? Where is it, what does it feel like, and how bad is it on a scale from zero to ten?

**Facts:**
- `M3` My headache feels tender, tugging, and like a cramp.
- `M4` I have a headache.
- `M5` My headache intensity is about 2 on a scale of 0 to 10.

**Background:**
- `M8` My headache came on gradually, over a while.
- `M6` My headache doesn't spread anywhere else.

## Turn 5 (focused)

**Doctor:** How has your breathing been? Do you get short of breath?

**Facts:**
- `M9` I am short of breath and have real difficulty breathing.

## Turn 6 (focused)

**Doctor:** Can I ask about your periods as well? How have they been recently?

**Facts:**
- `M14` My periods are very heavy and last a very long time.

**Background:**
- `L6` I mark the dates of my periods in my phone calendar.
- `L7` I keep spare sanitary pads in my handbag.

## Turn 7 (focused)

**Doctor:** Have you been abroad at all in the last few weeks?

**Facts:**
- `M17` I have not travelled outside the country in the last four weeks.

## Turn 8 (duration)  _[trap_duration]_

**Doctor:** And roughly how long has all this been going on?

**Facts:** none

## Turn 9 (history)

**Doctor:** Have you had any health problems in the past, or does anything run in your family?

**Facts:**
- `M0` I have been diagnosed with anemia.
- `M1` Someone in my family has been diagnosed with anemia.
- `M13` I have chronic kidney failure.

## Turn 10 (lifestyle)  _[trap_binary]_

**Doctor:** Can you tell me a bit about your lifestyle, things like smoking or drinking?

**Facts:**
- `X0` I don't smoke cigarettes.

## Turn 11 (sensitive)  _[sensitive]_

**Doctor:** Have you noticed any changes with your bowels, or when you go to the toilet?

**Facts:**
- `M16` I have noticed bright red blood in my stool.

## Turn 12 (impact)

**Doctor:** How has all this been affecting your day-to-day life, at work and at home?

**Facts:**
- `L0` I work as a graphic designer.
- `L1` I live with my boyfriend, Lukas.

**Background:**
- `L2` My grandmother lives two streets away from me.
- `L5` I moved to a new team at work this month.

## Turn 13 (coping)

**Doctor:** In general, are you managing OK at the moment? Is there anything else going on in your life right now?

**Facts:**
- `L5` I moved to a new team at work this month.

**Background:**
- `L4` I take a Spanish evening class on Mondays.

## Turn 14 (ice)

**Doctor:** What made you decide to come in now? And do you have any thoughts yourself about what might be behind it?

**Facts:** none

## Turn 15 (plan)

**Doctor:** I'd like to start with some blood tests, including your blood count and iron levels, and see where we stand before deciding on anything further. What do you make of that, and is there anything you'd like to ask me about it?

**Facts:** none

## Turn 16 (safety_net)

**Doctor:** If you faint, get very short of breath, or notice any bleeding, please come back straight away. Before we finish, is there anything else you'd like to tell me?

**Facts:** none

## Not used in any turn

- `M2` I have some pain.
- `M7` My headache covers a fairly wide area, not one exact spot.
- `L3` I enjoy drawing comics.
