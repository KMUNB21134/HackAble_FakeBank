# Hackers.md

**This document is meant for hackers who are going to try to hack this as practice.**
After all, this is meant for learning.
Good job going to this GitHub page.

If you're stuck, here are a few nudges — not answers. They point at
*where* to look, not what you'll find or how to exploit it. If you want
the full answer key instead, `README.md` spells everything out (don't
peek if you're treating this like a challenge).

## Getting a feel for the site

- Look at what the browser actually sends and receives — DevTools'
  Network tab, view-source, and any files a server tends to publish by
  default. Not everything the app can do is linked from the UI.
- How is your connection to this site protected? Think about what
  someone watching the network between you and the server — not the
  server itself — could actually see.

## The login form

- Both fields end up somewhere on the server. What happens if you feed
  them characters a "name" or "password" wouldn't normally contain?
- Nobody's stopping you from trying the same login over and over. What
  would that let you do, given enough guesses?

## Your account

- Something you type during registration shows up again later,
  somewhere you'll see it every time you log in. Pay close attention to
  exactly how it's displayed, not just that it's displayed.
- If you ever get a look at how passwords are stored, don't just note
  *that* they're hashed — look closely at what the stored value itself
  looks like.

## Moving money

- The transfer form has an optional field. Why would something be
  optional unless there's another way to satisfy whatever it's checking?
- Try values for "amount" and "recipient" that a careful app would
  reject. Does this one?

## When things go wrong

- Not every input is handled the same way. If you can make the server
  crash instead of just reject you, pay attention to what it shows you
  afterward — a "friendly" error page isn't always the end of the road.

## Keeping score

- Somewhere on this site is a page that quietly tracks which of these
  you've actually pulled off. It's not linked from anywhere in the UI -
  you'll need to find it the same way you'd find anything else that's
  "hidden."
- One challenge on that page can't be solved by triggering a crash alone.
  It wants proof you did something *with* the shell you landed in.

## Good luck

If you get through all of it, go read `app.py` and see how close your
mental model was.
