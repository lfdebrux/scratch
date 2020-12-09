%title: A tool for searching for and classifying code fragments
%author: Laurence de Bruxelles
%date: 2020-10-28

-> Code taxonomy
================

Laurence de Bruxelles
@lfdebrux
Developer for the Digital Marketplace

---

The problem
-----------

The Digital Marketplace is a moderately large project:

- 6 frontend apps
- 3 api apps
- 5+ internal libraries
- 10+ other active repositories
- who knows how many lines of code ¯\\_(ツ)_/¯

You get pretty good at searching for things!

---

The problem (continued)
-----------------------

For an ongoing mission that started (semi-)recently, we needed to replace a lot
of frontend code.

Some of it looked like this:

    {% include "toolkit/template.html" %}

or this:

    {% from "toolkit/macro.html" import macro %)

Some of it even looked like this:

    class InputForm(Form):
        ...

And some of it looked like this!:

    <div class="oh-noes"> ... </div>

---

The problem (part 3)
--------------------

To make the mission manageable we wanted to:

- Find and count up all these bits of frontend code
- Break them up into epics related by frontend component (not code!)
- Keep track of the count so we could see how much is left to replace
  and how long things are taking


Doing all of this involved remembering a lot of quite complicated command line
invocations...

    Include example of rg

---

A solution?
-----------

It quickly became clear what I needed to do; I automated it!

```
1       #!/usr/bin/env python3
2
3       """Find and document frontend components we use in our codebase
4       """
...
988     if __name__ == "__main__":
989           # main = Components()
990           # main.write_csv(sys.stdout, records)
991           # main = Templates()
992           # main = ContentLoaderComponents()
993           # main = FlashMessages()
...
996           # main.do(sys.stdout)
997           main()
```

It quickly got out of hand...

> https://gist.github.com/lfdebrux/72cdd7f87a2a7dd72266a74b5f13a52a

---

A solution (redux)
------------------

So two weeks ago I sat down and took what was good from the mega script and
made

-> 🎉🎉🎉 code_taxonomy.py 🎉🎉🎉 <-

It lets you save all your regexes in a Python file, using a nifty DSL, and
tells you what it finds in a format that can be quickly stuck in a spreadsheet.

So you can do the same massive search over and over again.

---

-> Demo Time <-

---

    $ # doitlive alias: cat="highlight -O ansi"

    # an example taxonomy file
    $ cat examples/python_taxonomy.py

    # executing the file runs the search
    # there are a few different output options
    $ python3 examples/python_taxonomy.py all
    $ python3 examples/python_taxonomy.py all --summary

    # a real example can be quite a bit more complicated
    # dm_frontend_code_taxonomy.py has lots of different epics,
    # some of which can be searched for in different ways
    $ python3 examples/dm_frontend_code_taxonomy.py --help

    # and the total number of lines of code is more manageable
    $ wc -l examples/dm_frontend_code_taxonomy.py
    $ wc -l code_taxonomy.py

---

Questions for you
-----------------

- Is this a problem you've had?

- How have you solved it?

- What tools are out there that already do what I'm trying to do?

- Is this new tool something you want?

---

Questions for me
----------------

---

-> Thank you <-

This demo was made with
[mdp](https://github.com/visit1985/mdp)
and [doitlive](https://doitlive.readthedocs.io/)
