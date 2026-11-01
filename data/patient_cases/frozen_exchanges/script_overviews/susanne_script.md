# Susanne (54F, HIV (initial infection))

## Turn 1 (opening)

**Doctor:** Hello Susanne, I see you've come in because you've been losing weight. Can you tell me a bit about that?

**Facts:**
- `M21` I have lost weight over the last three months without trying to.

**Background:**
- `M4` I have pain in my head and my neck.
- `M12` I have lesions, redness, and skin problems related to why I am here.

## Turn 2 (broad)

**Doctor:** Is there anything else you've noticed about your health lately?

**Facts:**
- `M10` I am too tired to do usual activities; I stay in bed all day.

**Background:**
- `M20` I have muscle pain all over.

## Turn 3 (focused)

**Doctor:** Have you had a sore throat, or noticed any swollen glands?

**Facts:**
- `M0` My lymph nodes are swollen and painful.

## Turn 4 (focused_pain)

**Doctor:** Have you had any pain anywhere? Where is it, what does it feel like, and how bad is it on a scale from zero to ten?

**Facts:**
- `M3` The pain in my head and my neck feels nagging, pulsing, and exhausting.
- `M4` I have pain in my head and my neck.
- `M5` The pain in my head and my neck is about 3 out of 10.

**Background:**
- `M8` The pain in my head and my neck came on very gradually.
- `M6` The pain in my head and my neck doesn't spread anywhere else.
- `M7` The pain in my head and my neck is in a fairly specific spot.

## Turn 5 (focused)

**Doctor:** Have you had any aches in your muscles?

**Facts:**
- `M20` I have muscle pain all over.

**Background:**
- `L0` I work as a bookkeeper for a furniture company.

## Turn 6 (focused)

**Doctor:** Have you been abroad at all in the last few weeks?

**Facts:**
- `M23` I have not travelled outside the country in the last four weeks.

## Turn 7 (focused)  _[sensitive]_

**Doctor:** Have you noticed any rash or sores anywhere on your body?

**Facts:**
- `M12` I have lesions, redness, and skin problems related to why I am here.
- `M16` The affected area is on my mouth and my genital area.

**Background:**
- `M18` My lesions are bigger than a centimetre across.
- `M19` My rash doesn't itch.

## Turn 8 (duration)  _[trap_duration]_

**Doctor:** And roughly how long has all this been going on?

**Facts:** none

## Turn 9 (history)  _[trap_binary]_

**Doctor:** Do you have any diagnosed long-term health conditions?

**Facts:**
- `X2` No, I don't have any long-term health conditions.

## Turn 10 (lifestyle)  _[trap_binary, sensitive]_

**Doctor:** Just a couple of questions that can sometimes affect your symptoms. Do you smoke, or do you use any drugs?

**Facts:**
- `X0` I don't smoke cigarettes.
- `M9` I currently use intravenous drugs.

## Turn 11 (sensitive)  _[sensitive]_

**Doctor:** Is there anything about your sexual health or recent partners that you think might be relevant?

**Facts:**
- `M1` I have had a sexually transmitted infection.
- `M11` I have had unprotected sex with more than one partner in the last six months.
- `M22` I have had sex with an HIV-positive partner in the past twelve months.

**Background:**
- `L6` I separated from my husband two years ago.
- `L7` I've been meeting people through a dating app.

## Turn 12 (impact)

**Doctor:** How has all this been affecting your day-to-day life, at work and at home?

**Facts:**
- `L0` I work as a bookkeeper for a furniture company.
- `L1` I live with my adult son, Tobias.

## Turn 13 (coping)

**Doctor:** In general, are you managing OK at the moment? Is there anything else going on in your life right now?

**Facts:**
- `L4` I go to a book club once a month.
- `L5` My son started a new job last week.

**Background:**
- `L2` My sister calls me every Sunday.

## Turn 14 (ice)

**Doctor:** What made you decide to come in now? And do you have any thoughts yourself about what might be behind it?

**Facts:** none

## Turn 15 (plan)

**Doctor:** Symptoms like these can have a few different causes, including some infections, so I'd like to do some blood tests. That would include a test for HIV and other infections, which we recommend for anyone with these symptoms. What do you make of that, and is there anything you'd like to ask me about it?

**Facts:** none

## Turn 16 (safety_net)

**Doctor:** If you get a high fever, a stiff neck, or feel much more unwell, please come back straight away. Before we finish, is there anything else you'd like to tell me?

**Facts:** none

## Not used in any turn

- `M2` I have some pain.
- `M13` My rash is pale.
- `M14` My lesions don't peel.
- `M15` My rash is slightly swollen.
- `M17` My pain from the rash is about 6 on a scale of 0 to 10.
- `L3` I enjoy doing jigsaw puzzles.
