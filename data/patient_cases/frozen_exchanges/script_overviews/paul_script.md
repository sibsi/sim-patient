# Paul (24M, Anemia)

## Turn 1 (opening)

**Doctor:** Hello Paul, I see you've come in because you've been looking paler than usual. Can you tell me a bit about that?

**Facts:**
- `M15` My skin is much paler than usual.

**Background:**
- `L1` I share a flat with two other students.
- `M1` I have been diagnosed with anemia.
- `M4` I have a headache.
- `M10` I feel lightheaded and dizzy, as though I might faint.
- `M12` I have chronic kidney failure.

## Turn 2 (broad)

**Doctor:** Is there anything else you've noticed about your health lately?

**Facts:**
- `M11` I am too tired to do usual activities; I stay in bed all day.

**Background:**
- `M16` I have noticed bright red blood in my stool.

## Turn 3 (focused)

**Doctor:** Have you had any dizziness, or felt like you might faint?

**Facts:**
- `M10` I feel lightheaded and dizzy, as though I might faint.

**Background:**
- `M9` I feel slightly dizzy and lightheaded.

## Turn 4 (focused_pain)

**Doctor:** Have you had any pain anywhere? Where is it, what does it feel like, and how bad is it on a scale from zero to ten?

**Facts:**
- `M3` My headache feels tugging and exhausting.
- `M4` I have a headache.
- `M5` My headache intensity is about 5 on a scale of 0 to 10.

**Background:**
- `M8` My headache came on gradually, over a while.
- `M6` My headache doesn't spread anywhere else.
- `M7` My headache is in a fairly specific spot.

## Turn 5 (focused)

**Doctor:** How have you been eating lately? What does your diet look like at the moment?

**Facts:**
- `M0` My diet is poor.

**Background:**
- `M18` My BMI is under 18.5; I am underweight.
- `L6` I mostly live on toast and instant noodles between lectures.
- `L7` I'm the only one in my flat who never really cooks.

## Turn 6 (focused)

**Doctor:** And how about your weight?

**Facts:**
- `M18` My BMI is under 18.5; I am underweight.

## Turn 7 (focused)

**Doctor:** Have you been abroad at all in the last few weeks?

**Facts:**
- `M17` I travelled to South East Asia in the last four weeks.

**Background:**
- `L8` I went backpacking in Vietnam and Thailand for three weeks after my exams.
- `L9` I travelled with my friend from my history course.

## Turn 8 (duration)  _[trap_duration]_

**Doctor:** And roughly how long has all this been going on?

**Facts:** none

## Turn 9 (history)

**Doctor:** Have you had any health problems in the past, anything you've been diagnosed with?

**Facts:**
- `M1` I have been diagnosed with anemia.
- `M12` I have chronic kidney failure.

**Background:**
- `M14` I am taking new oral anticoagulants.

## Turn 10 (lifestyle)  _[trap_binary]_

**Doctor:** Can you tell me a bit about your lifestyle, things like smoking or drinking?

**Facts:**
- `X0` I don't smoke cigarettes.

## Turn 11 (sensitive)  _[sensitive]_

**Doctor:** Have you noticed any changes with your bowels, or when you go to the toilet?

**Facts:**
- `M13` My stools have been black, like coal.
- `M16` I have noticed bright red blood in my stool.

## Turn 12 (impact)

**Doctor:** How has all this been affecting your day-to-day life, with your studies and at home?

**Facts:**
- `L0` I'm studying history at university.
- `L1` I share a flat with two other students.

**Background:**
- `L3` I enjoy playing the piano.
- `L5` I handed in a big term paper last week.

## Turn 13 (coping)

**Doctor:** In general, are you managing OK at the moment? Is there anything else going on in your life right now?

**Facts:**
- `L4` I play board games with friends on Wednesday evenings.
- `L5` I handed in a big term paper last week.

## Turn 14 (ice)

**Doctor:** What made you decide to come in now? And do you have any thoughts yourself about what might be behind it?

**Facts:** none

## Turn 15 (plan)

**Doctor:** Looking pale like this can have a few different causes, so I'd like to start with some blood tests, including your blood count and iron levels. Depending on the results, we may need a few more tests to find out what's behind it. What do you make of that, and is there anything you'd like to ask me about it?

**Facts:** none

## Turn 16 (safety_net)

**Doctor:** If you faint, get very short of breath, or notice any bleeding, please come back straight away. Before we finish, is there anything else you'd like to tell me?

**Facts:** none

## Not used in any turn

- `M2` I have some pain.
- `L2` My younger sister is still at school.
