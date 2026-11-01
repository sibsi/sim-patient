# Jonas (55M, Pneumonia)

## Turn 1 (opening)

**Doctor:** Hello Jonas, I see you've come in because you've had a fever. Can you tell me a bit about that?

**Facts:**
- `M11` I have had a fever.

**Background:**
- `M12` I have had chills and shivers.
- `M8` My cough brings up mucus that's coloured, and more of it than usual.
- `L6` My wife Sabine has been taking my temperature every evening.

## Turn 2 (broad)

**Doctor:** Is there anything else you've noticed about your health lately?

**Facts:**
- `M25` I have lost my appetite and get full more quickly than usual.

**Background:**
- `M28` My BMI is under 18.5; I am underweight.

## Turn 3 (focused)

**Doctor:** Have you had a cough? Is anything coming up when you cough?

**Facts:**
- `M8` My cough brings up mucus that's coloured, and more of it than usual.

## Turn 4 (focused_pain)

**Doctor:** Have you had any pain anywhere? Where is it, what does it feel like, and how bad is it on a scale from zero to ten?

**Facts:**
- `M1` The pain in the right side of my chest and the left side of my upper back feels sharp.
- `M2` I have pain in the right side of my chest and the left side of my upper back.
- `M3` The pain in the right side of my chest and the left side of my upper back is about 2 out of 10.

**Background:**
- `M6` The pain in the right side of my chest and the left side of my upper back came on fairly quickly.
- `M4` The pain in the right side of my chest and the left side of my upper back doesn't spread anywhere else.
- `M5` I cannot pinpoint the pain in the right side of my chest and the left side of my upper back; it covers a wide area.

## Turn 5 (focused)

**Doctor:** How has your breathing been? Do you get short of breath?

**Facts:**
- `M7` I am short of breath and have real difficulty breathing.

**Background:**
- `L0` I work as a locksmith.

## Turn 6 (focused)

**Doctor:** Have you had any shivering or chills?

**Facts:**
- `M12` I have had chills and shivers.

## Turn 7 (focused)

**Doctor:** Have you been abroad at all in the last few weeks?

**Facts:**
- `M27` I have not travelled outside the country in the last four weeks.

## Turn 8 (duration)  _[trap_duration]_

**Doctor:** And roughly how long has all this been going on?

**Facts:** none

## Turn 9 (history)

**Doctor:** Have you had any lung or heart problems in the past, or any other long-term conditions?

**Facts:**
- `M15` I have chronic obstructive pulmonary disease.
- `M13` I have heart failure.
- `M16` I have asthma and have had to use a bronchodilator in the past.
- `M14` I have had a stroke.

**Background:**
- `M26` I had surgery within the last month.

## Turn 10 (lifestyle)  _[sensitive]_

**Doctor:** Can you tell me a bit about your lifestyle, things like smoking or drinking?

**Facts:**
- `M10` I smoke cigarettes.

## Turn 11 (sensitive)  _[sensitive]_

**Doctor:** And how much alcohol do you drink in a typical week?

**Facts:**
- `M9` I drink alcohol heavily and have a problem with alcohol.

**Background:**
- `L7` I keep bottles hidden in my workshop so my wife doesn't see how much I drink.
- `L8` My wife has told me more than once that I should cut down.

## Turn 12 (impact)

**Doctor:** How has all this been affecting your day-to-day life, at work and at home?

**Facts:**
- `L0` I work as a locksmith.
- `L1` I live with my wife, Sabine.

**Background:**
- `L3` I like doing crossword puzzles.

## Turn 13 (coping)

**Doctor:** In general, are you managing OK at the moment? Is there anything else going on in your life right now?

**Facts:**
- `L4` I play cards with friends every Friday evening.
- `L5` My wife and I celebrated our 30th wedding anniversary last week.

## Turn 14 (ice)

**Doctor:** What made you decide to come in now? And do you have any thoughts yourself about what might be behind it?

**Facts:** none

## Turn 15 (plan)

**Doctor:** Symptoms like yours could be a chest infection, so I'd like to arrange a chest X-ray and some blood tests. If it is an infection, we would usually start antibiotics. What do you make of that, and is there anything you'd like to ask me about it?

**Facts:** none

## Turn 16 (safety_net)

**Doctor:** If your breathing gets worse, you feel confused, or you feel much more unwell, please come back straight away. Before we finish, is there anything else you'd like to tell me?

**Facts:** none

## Not used in any turn

- `M0` I have some pain.
- `M17` I have lesions, redness, and skin problems related to why I am here.
- `M18` My rash is pink.
- `M19` My lesions peel.
- `M20` My rash is moderately swollen.
- `M21` The affected area is on my neck, my bottom, my right side and my right shoulder.
- `M22` My pain from the rash is about 3 on a scale of 0 to 10.
- `M23` My lesions are smaller than a centimetre across.
- `M24` My itching intensity is about 1 on a scale of 0 to 10.
- `M29` My vaccinations are up to date.
- `L2` My son is studying engineering in Aachen.
