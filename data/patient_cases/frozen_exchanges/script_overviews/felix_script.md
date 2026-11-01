# Felix (29M, Tuberculosis)

## Turn 1 (opening)

**Doctor:** Hello Felix, I see you've come in because you've been coughing up blood. Can you tell me a bit about that?

**Facts:**
- `M1` I have been coughing up blood.

**Background:**
- `L6` My cousin saw the blood on a tissue and told me to get it checked.
- `L7` It started during a rehearsal and I had to step out.
- `M3` I am short of breath and have real difficulty breathing.

## Turn 2 (broad)

**Doctor:** Is there anything else you've noticed about your health lately?

**Facts:**
- `M7` I have a cough.

**Background:**
- `M6` I have lost weight over the last three months without trying to.

## Turn 3 (focused)

**Doctor:** How has your breathing been? Do you get short of breath?

**Facts:**
- `M3` I am short of breath and have real difficulty breathing.

**Background:**
- `L0` I work as a sound technician at a theatre.

## Turn 4 (focused)

**Doctor:** Have you had any fevers or sweats?

**Facts:**
- `M5` I have had a fever.

## Turn 5 (focused)

**Doctor:** Have you lost any weight without trying to?

**Facts:**
- `M6` I have lost weight over the last three months without trying to.

## Turn 6 (focused)

**Doctor:** Have you been abroad at all in the last few weeks?

**Facts:**
- `M8` I have not travelled outside the country in the last four weeks.

## Turn 7 (focused)

**Doctor:** Do you take any regular medication?

**Facts:**
- `M0` I take corticosteroids.

## Turn 8 (duration)  _[trap_duration]_

**Doctor:** And roughly how long has all this been going on?

**Facts:** none

## Turn 9 (history)  _[trap_binary]_

**Doctor:** Do you have any long-term health conditions, or anything you're being treated for?

**Facts:**
- `X2` No, I don't have any long-term health conditions.

## Turn 10 (lifestyle)  _[trap_binary, sensitive]_

**Doctor:** Just a couple of questions that can sometimes affect your symptoms. Do you smoke, or do you use any drugs?

**Facts:**
- `X0` I don't smoke cigarettes.
- `M2` I currently use intravenous drugs.

## Turn 11 (sensitive)  _[sensitive]_

**Doctor:** And how much alcohol do you drink in a typical week?

**Facts:**
- `M4` I drink alcohol heavily and have a problem with alcohol.

**Background:**
- `L8` I've missed shifts at the theatre because I was too hungover to go in.
- `L9` My cousin has told me a few times that I should cut down.

## Turn 12 (impact)

**Doctor:** How has all this been affecting your day-to-day life, at work and at home?

**Facts:**
- `L0` I work as a sound technician at a theatre.
- `L1` I share a flat with my cousin.

**Background:**
- `L3` I enjoy playing the guitar.

## Turn 13 (coping)

**Doctor:** In general, are you managing OK at the moment? Is there anything else going on in your life right now?

**Facts:**
- `L4` I rehearse with a band every Thursday evening.
- `L5` My band plays its first concert next month.

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

- `L2` My older sister is a lawyer.
