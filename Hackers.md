# Hackers.md

**This document is meant for hackers who are going to try to hack this as practice.**
After all, this is meant for learning.
Good job going to this GitHub page.

If you are stuck on something, here are a few **hints**. They're ordered
roughly login → account → money, but feel free to jump around. If you want
the full answer key instead of hints, `README.md` spells everything out
(don't peek if you're treating this like a challenge).

## General

- Try using DevTools to see the frontend on some of the pages — view
  source, check the Network tab, and read any HTML comments left behind.
- Check for a `robots.txt`. Sites tell crawlers what *not* to index for a
  reason — sometimes that reason is "we forgot this shouldn't be public."

## Login page

- The login form takes a username and password and puts them into a
  database query. What happens if your "username" isn't just a name?
- Comment syntax exists in SQL for a reason. If you can end the query
  early, does the rest of it even matter?
- There's no limit on how many times you can try a password. What would
  a tool like Hydra do here?

## Getting in without logging in at all

- Not every route has to be linked from the UI to exist. Guessing paths
  is one way to find them — but you don't always have to guess blind.

## Passwords

- If you do get your hands on the password data, look at how it's
  stored. Does the hash length/format tell you which algorithm was
  used? Some algorithms are a lot faster to crack than others.

## Your account

- What you type as a username during registration comes back to you
  later, somewhere you'll see it every time you log in. Is it treated
  as plain text there, or could it be treated as something else?
- If a page will render whatever you put in a field without cleaning it
  up first, what's the smallest snippet of HTML/JS you could use to
  prove it executes?

## Transfers

- The transfer form has three fields, but only two of them are
  required. What's the third one for, and where would its value have
  to come from to be "valid"?
- If something is generated from a formula instead of pulled from a
  secret store, can you compute it yourself? Check the page source on
  the transfer page for a clue about how that value is built.
- Does the app check that the amount you're sending is actually
  positive? What about whether you can afford it?
- Does the app check that the person you're sending money to actually
  exists?

## Good luck

If you get through all of it, go read `app.py` and see how close your
mental model was.
