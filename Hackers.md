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
- You're not the only one logging in. Something else on this server
  does too, on its own, every so often, using real credentials it
  never shows you anywhere. If your connection to the site has the
  problem above, that's worth paying attention to.

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
- Not every seeded account belongs to a fictional person. One exists
  purely so its password can be cracked - and logging in with it for
  real is the point.
- The dashboard has a feature meant for exactly one account. It's on
  every page whether that's you or not - you just can't see it. Being
  unable to see something and being unable to reach it are not the same
  problem, and you already know a way to become someone else here.

## Moving money

- The transfer form has an optional field. Why would something be
  optional unless there's another way to satisfy whatever it's checking?
- Try values for "amount" and "recipient" that a careful app would
  reject. Does this one?

## When things go wrong

- Not every input is handled the same way. If you can make the server
  crash instead of just reject you, pay attention to what it shows you
  afterward — a "friendly" error page isn't always the end of the road.
- Whatever you can reach that way isn't limited to looking around. If
  you can read files, ask yourself what else is sitting right next to
  the one you were looking for — like a record of every transfer
  anyone's ever made.
- That record keeps more than the amount and the date. If you made a
  transfer and want it to look like you never did, think about what
  else it wrote down about where the request came from.

## Not everyone logs in with a browser

- There's a second way into this bank meant for scripts, not people. It
  hands back something other than the usual cookie. Look at the three
  parts of what it gives you — the middle one is just readable text if
  you know how it's encoded, no secret required.
- The first part of that same thing tells the server how to check it.
  What if you got to decide that yourself instead of the server?
- If something signs data with a secret, and that secret is sitting
  somewhere you already have access to for other reasons on this
  project, you don't need to break the signature at all.

## Keeping score

- Somewhere on this site is a page that quietly tracks which of these
  you've actually pulled off. It's not linked from anywhere in the UI,
  and unlike some other hidden things here, nothing hands you the path
  directly - you'll have to think about where else a URL might turn up.
- One challenge on that page can't be solved by triggering a crash alone.
  It wants proof you did something *with* the shell you landed in.

## Good luck

If you get through all of it, go read `app.py` and see how close your
mental model was.
