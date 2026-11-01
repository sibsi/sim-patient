# Olivia (41F, Pneumonia)

## Turn 1 (opening)

**Doctor:** Hello Olivia, I see you've come in because you've been short of breath. Can you tell me a bit about that?

**Facts:**
- `M7` I am short of breath and have real difficulty breathing.

**Background:**
- `M11` I have had a fever.
- `M29` I have a cough.
- `L6` My mother noticed I had to stop and catch my breath when we went shopping.

## Turn 2 (broad)

**Doctor:** Is there anything else you've noticed about your health lately?

**Facts:**
- `M27` I have noticed new tiredness, a vague general discomfort, widespread muscle aches, and a change in overall well-being.

**Background:**
- `M31` My BMI is under 18.5; I am underweight.

## Turn 3 (focused)

**Doctor:** Have you had a cough? Is anything coming up when you cough?

**Facts:**
- `M29` I have a cough.
- `M8` My cough brings up mucus that's coloured, and more of it than usual.

## Turn 4 (focused_pain)

**Doctor:** Have you had any pain anywhere? Where is it, what does it feel like, and how bad is it on a scale from zero to ten?

**Facts:**
- `M1` The pain in my chest and my upper back feels sharp.
- `M2` I have pain in my chest and my upper back.
- `M32` My pain gets worse when I breathe in deeply.

**Background:**
- `M6` The pain in my chest and my upper back came on gradually, over a while.
- `M4` The pain in my chest and my upper back doesn't spread anywhere else.
- `M5` The pain in my chest and my upper back is in a fairly specific spot.

## Turn 5 (focused)

**Doctor:** Have you had a fever?

**Facts:**
- `M11` I have had a fever.

**Background:**
- `L0` I work as a translator.

## Turn 6 (focused)

**Doctor:** Have you had any shivering or chills?

**Facts:**
- `M12` I have had chills and shivers.

## Turn 7 (focused)

**Doctor:** Have you been abroad at all in the last few weeks?

**Facts:**
- `M30` I have not travelled outside the country in the last four weeks.

## Turn 8 (duration)  _[trap_duration]_

**Doctor:** And roughly how long has all this been going on?

**Facts:** none

## Turn 9 (history)

**Doctor:** Have you had any lung or heart problems in the past, or any other long-term conditions?

**Facts:**
- `M16` I have had pneumonia.
- `M17` I have chronic obstructive pulmonary disease.
- `M13` I have Parkinson's disease.
- `M14` I have heart failure.
- `M15` I have had a stroke.

**Background:**
- `M28` I had surgery within the last month.

## Turn 10 (lifestyle)  _[sensitive]_

**Doctor:** Can you tell me a bit about your lifestyle, things like smoking or drinking?

**Facts:**
- `M10` I smoke cigarettes.

## Turn 11 (sensitive)  _[sensitive]_

**Doctor:** And how much alcohol do you drink in a typical week?

**Facts:**
- `M9` I drink alcohol heavily and have a problem with alcohol.

**Background:**
- `L7` I've tried to stop drinking a few times but never lasted more than a couple of weeks.
- `L8` My brother has told me I should cut down.

## Turn 12 (impact)

**Doctor:** How has all this been affecting your day-to-day life, at work and at home?

**Facts:**
- `L0` I work as a translator.
- `L1` I live with my mother.

**Background:**
- `L3` I enjoy knitting.

## Turn 13 (coping)

**Doctor:** In general, are you managing OK at the moment? Is there anything else going on in your life right now?

**Facts:**
- `L4` I take part in an online writing group on Sunday evenings.
- `L5` My mother's birthday is this weekend.

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
- `M3` The pain in my chest and my upper back is about 1 out of 10.
- `M18` I have lesions, redness, and skin problems related to why I am here.
- `M19` My rash is pink.
- `M20` My lesions peel.
- `M21` My rash isn't swollen.
- `M22` The affected area is on my upper back, my lower back and my left shoulder.
- `M23` My pain from the rash is about 2 on a scale of 0 to 10.
- `M24` My lesions are smaller than a centimetre across.
- `M25` My rash doesn't itch.
- `M26` I have muscle pain all over.
- `L2` My brother is a carpenter.
