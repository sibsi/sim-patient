# Sabine (24F, GERD)

## Turn 1 (opening)

**Doctor:** Hello Sabine, I see you've come in because of a burning feeling in your stomach and throat. Can you tell me a bit about that?

**Facts:**
- `M10` I get a burning feeling that starts in my stomach and rises into my throat, sometimes with a bitter taste in my mouth.

**Background:**
- `M13` My symptoms get worse after I eat.

## Turn 2 (broad)

**Doctor:** Is there anything else you've noticed about your health lately?

**Facts:**
- `M11` I have a cough.

**Background:**
- `M4` The pain in my belly spreads to my chest.

## Turn 3 (focused)

**Doctor:** Does anything make it better or worse, for example eating, or lying down?

**Facts:**
- `M13` My symptoms get worse after I eat.
- `M14` My symptoms are worse when I lie down and better when I sit up.

## Turn 4 (focused_pain)

**Doctor:** Have you had any pain anywhere? Where is it, what does it feel like, does it spread anywhere, and how bad is it on a scale from zero to ten?

**Facts:**
- `M1` The pain in my belly feels throbbing, like a stab, and burning.
- `M2` I have pain in my belly.
- `M3` The pain in my belly is about 7 out of 10.
- `M4` The pain in my belly spreads to my chest.

**Background:**
- `M6` The pain in my belly came on gradually, over a while.
- `M5` The pain in my belly covers a fairly wide area, not one exact spot.

## Turn 5 (focused)

**Doctor:** Is there any chance you could be pregnant?

**Facts:**
- `M9` I am pregnant.

**Background:**
- `L6` Jonas and I found out about the pregnancy a few weeks ago.
- `L7` I've downloaded a pregnancy app to keep track of the weeks.

## Turn 6 (focused)

**Doctor:** And how about your weight?

**Facts:**
- `M7` I am significantly overweight for my height.

## Turn 7 (focused)

**Doctor:** Have you been abroad at all in the last few weeks?

**Facts:**
- `M12` I have not travelled outside the country in the last four weeks.

## Turn 8 (duration)  _[trap_duration]_

**Doctor:** And roughly how long has all this been going on?

**Facts:** none

## Turn 9 (history)  _[trap_binary]_

**Doctor:** Have you had any health problems in the past, or any long-term conditions?

**Facts:**
- `X2` No, I don't have any long-term health conditions.

## Turn 10 (lifestyle)  _[sensitive, trap_binary]_

**Doctor:** Can you tell me a bit about your lifestyle, things like smoking or drinking?

**Facts:**
- `M8` I smoke cigarettes.
- `X1` I don't drink alcohol.

**Background:**
- `L8` I've smoked since I was a teenager.

## Turn 11 (sensitive)  _[trap_binary]_

**Doctor:** Have you noticed any changes with your bowels, or when you go to the toilet?

**Facts:**
- `X3` I haven't noticed any blood in my stool or black stools.

## Turn 12 (impact)

**Doctor:** How has all this been affecting your day-to-day life, at work and at home?

**Facts:**
- `L0` I work as a hotel receptionist.
- `L1` I live with my boyfriend, Jonas.

**Background:**
- `L2` My best friend Lena lives in the flat next door.

## Turn 13 (coping)

**Doctor:** In general, are you managing OK at the moment? Is there anything else going on in your life right now?

**Facts:**
- `L4` I go to a ceramics class on Thursday evenings.
- `L5` Jonas and I started looking for a bigger flat this month.

## Turn 14 (ice)

**Doctor:** What made you decide to come in now? And do you have any thoughts yourself about what might be behind it?

**Facts:** none

## Turn 15 (plan)

**Doctor:** This sounds like it could be acid coming up from your stomach, so I'd suggest starting with some simple changes, like smaller meals and not eating late in the evening. There is also medication that can help with this. What do you make of that, and is there anything you'd like to ask me about it?

**Facts:** none

## Turn 16 (safety_net)

**Doctor:** If the pain gets much worse or spreads to your arm or jaw, if you have trouble swallowing, or if you vomit blood, please come back straight away. Before we finish, is there anything else you'd like to tell me?

**Facts:** none

## Not used in any turn

- `M0` I have some pain.
- `L3` I enjoy watching fantasy series.
