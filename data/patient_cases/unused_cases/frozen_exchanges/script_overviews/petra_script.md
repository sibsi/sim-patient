# Petra (28F, Tuberculosis)

## Turn 1 (opening)

**Doctor:** Hello Petra, I see you've come in because you've been short of breath. Can you tell me a bit about that?

**Facts:**
- `M4` I am short of breath and have real difficulty breathing.

**Background:**
- `L6` I had to stop halfway up the stairs to my flat last week.
- `L7` My best friend said I sounded out of breath on the phone.
- `M2` I have been coughing up blood.

## Turn 2 (broad)

**Doctor:** Is there anything else you've noticed about your health lately?

**Facts:**
- `M8` I have a cough.

**Background:**
- `M7` I have lost weight over the last three months without trying to.

## Turn 3 (focused)

**Doctor:** When you cough, have you noticed anything coming up?

**Facts:**
- `M2` I have been coughing up blood.

**Background:**
- `L0` I work as a cashier in a hardware store.

## Turn 4 (focused)

**Doctor:** Have you had any fevers or sweats?

**Facts:**
- `M6` I have had a fever.

## Turn 5 (focused)

**Doctor:** Have you lost any weight without trying to?

**Facts:**
- `M7` I have lost weight over the last three months without trying to.

## Turn 6 (focused)

**Doctor:** Have you been abroad at all in the last few weeks?

**Facts:**
- `M9` I have not travelled outside the country in the last four weeks.

## Turn 7 (focused)

**Doctor:** Do you take any regular medication?

**Facts:**
- `M1` I take corticosteroids.

## Turn 8 (duration)  _[trap_duration]_

**Doctor:** And roughly how long has all this been going on?

**Facts:** none

## Turn 9 (history)  _[sensitive]_

**Doctor:** Do you have any long-term health conditions, or anything you're being treated for?

**Facts:**
- `M0` I am HIV positive.

## Turn 10 (lifestyle)  _[trap_binary, sensitive]_

**Doctor:** Can you tell me a bit about your lifestyle, things like smoking or drinking?

**Facts:**
- `X0` I don't smoke cigarettes.
- `M3` I currently use intravenous drugs.

## Turn 11 (sensitive)  _[sensitive]_

**Doctor:** And how much alcohol do you drink in a typical week?

**Facts:**
- `M5` I drink alcohol heavily and have a problem with alcohol.

**Background:**
- `L8` I've spent money I needed for rent on alcohol.
- `L9` My best friend keeps telling me I drink too much.

## Turn 12 (impact)

**Doctor:** How has all this been affecting your day-to-day life, at work and at home?

**Facts:**
- `L0` I work as a cashier in a hardware store.
- `L1` I live alone.

**Background:**
- `L3` I like watching true-crime documentaries.

## Turn 13 (coping)

**Doctor:** In general, are you managing OK at the moment? Is there anything else going on in your life right now?

**Facts:**
- `L5` I started working extra shifts at the store this month.

**Background:**
- `L4` I go to the cinema with friends most Saturdays.

## Turn 14 (ice)

**Doctor:** What made you decide to come in now? And do you have any thoughts yourself about what might be behind it?

**Facts:** none

## Turn 15 (plan)

**Doctor:** With a cough like this, I'd like to get a chest X-ray and some tests on your blood and on what you're coughing up. Until we have the results, it would be best to stay off work and keep close contact with other people to a minimum, in case it's an infection that can spread. What do you make of that, and is there anything you'd like to ask me about it?

**Facts:** none

## Turn 16 (safety_net)

**Doctor:** If you cough up larger amounts of blood, or your breathing gets much worse, please come back straight away. Before we finish, is there anything else you'd like to tell me?

**Facts:** none

## Not used in any turn

- `L2` My best friend works as a hairdresser.
