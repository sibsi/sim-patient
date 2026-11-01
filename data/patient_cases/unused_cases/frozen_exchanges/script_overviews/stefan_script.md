# Stefan (67M, GERD)

## Turn 1 (opening)

**Doctor:** Hello Stefan, I see you've come in because of a burning feeling in your stomach and throat. Can you tell me a bit about that?

**Facts:**
- `M12` I get a burning feeling that starts in my stomach and rises into my throat, sometimes with a bitter taste in my mouth.

**Background:**
- `M15` My symptoms get worse after I eat.

## Turn 2 (broad)

**Doctor:** Is there anything else you've noticed about your health lately?

**Facts:**
- `M13` I have a cough.

**Background:**
- `M4` The pain in my chest and my upper belly spreads to my lower chest.

## Turn 3 (focused)

**Doctor:** Does anything make it better or worse, for example eating, or lying down?

**Facts:**
- `M15` My symptoms get worse after I eat.

## Turn 4 (focused_pain)

**Doctor:** Have you had any pain anywhere? Where is it, what does it feel like, does it spread anywhere, and how bad is it on a scale from zero to ten?

**Facts:**
- `M1` The pain in my chest and my upper belly feels throbbing, burning, and frightening.
- `M2` I have pain in my chest and my upper belly.
- `M3` The pain in my chest and my upper belly is about 4 out of 10.
- `M4` The pain in my chest and my upper belly spreads to my lower chest.

**Background:**
- `M6` The pain in my chest and my upper belly came on very gradually.
- `M5` The pain in my chest and my upper belly covers a fairly wide area, not one exact spot.

## Turn 5 (focused)

**Doctor:** Have you had any problems with your breathing, like wheezing or asthma?

**Facts:**
- `M10` I have asthma and have had to use a bronchodilator in the past.

## Turn 6 (focused)

**Doctor:** And how about your weight?

**Facts:**
- `M7` I am significantly overweight for my height.

## Turn 7 (focused)

**Doctor:** Have you been abroad at all in the last few weeks?

**Facts:**
- `M14` I have not travelled outside the country in the last four weeks.

## Turn 8 (duration)  _[trap_duration]_

**Doctor:** And roughly how long has all this been going on?

**Facts:** none

## Turn 9 (history)

**Doctor:** Have you had any health problems in the past, or any long-term conditions?

**Facts:**
- `M9` I have a hiatal hernia.

## Turn 10 (lifestyle)  _[sensitive, trap_binary]_

**Doctor:** Can you tell me a bit about your lifestyle, things like smoking or drinking?

**Facts:**
- `M8` I smoke cigarettes.
- `X1` I don't drink a lot of alcohol.

**Background:**
- `L6` My wife Ingrid has been on at me to stop smoking for years.
- `L7` I've smoked for most of my adult life.

## Turn 11 (sensitive)  _[sensitive]_

**Doctor:** Have you noticed any changes with your bowels, or when you go to the toilet?

**Facts:**
- `M11` My stools have been black, like coal.

## Turn 12 (impact)

**Doctor:** How has all this been affecting your day-to-day life, at home and with the things you usually do?

**Facts:**
- `L0` I'm a retired bank clerk.
- `L1` I live with my wife, Ingrid.

**Background:**
- `L2` My granddaughter visits me every weekend.

## Turn 13 (coping)

**Doctor:** In general, are you managing OK at the moment? Is there anything else going on in your life right now?

**Facts:**
- `L4` I volunteer at the local library on Mondays.
- `L5` I took over organising the library's book sale this month.

## Turn 14 (ice)

**Doctor:** What made you decide to come in now? And do you have any thoughts yourself about what might be behind it?

**Facts:** none

## Turn 15 (plan)

**Doctor:** This sounds like it could be acid coming up from your stomach. At your age, I'd also like to arrange a camera test to have a proper look at your stomach, and some blood tests. I'd suggest starting some medication for the acid as well. What do you make of that, and is there anything you'd like to ask me about it?

**Facts:** none

## Turn 16 (safety_net)

**Doctor:** If you get chest pain that feels different, vomit blood, or feel faint, please come back straight away. Before we finish, is there anything else you'd like to tell me?

**Facts:** none

## Not used in any turn

- `M0` I have some pain.
- `L3` I like building model railways.
