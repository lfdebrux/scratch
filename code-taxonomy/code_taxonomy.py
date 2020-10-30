#!/usr/bin/env python3

"""
Find and classify code

This package lets you find bits of code in a large codebase using a Python DSL.

Requirements
============

This tool relies on ripgrep (https://github.com/BurntSushi/ripgrep) to do file
searching, make sure it is installed somewhere in your PATH.

You'll also need to install the following Python packages to use this tool:

    pip install sh

Bugs
====

It needs to be better documented.

In some places the code is excessively clever, and in others it is overly simplistic.

---

Copyright (c) 2020, Crown Copyright (Government Digital Service)
"""

import collections
import csv
import datetime
import itertools
import json
import logging
import re
import string
import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from pathlib import Path
from typing import (
    Any,
    ClassVar,
    Counter,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Pattern,
    Set,
    Tuple,
    Type,
)

import sh  # type: ignore
from sh import git, rg  # type: ignore
from typing_extensions import TypedDict

_repos: Dict[str, str] = {}


def github_url(match) -> Optional[str]:
    repo, *path = match["path"].parts
    if repo in _repos:
        revision = _repos[repo]
    else:
        try:
            ret = git("-C", repo, "rev-parse", "--short", "HEAD")
        except sh.ErrorReturnCode:
            return None
        revision = str(ret).strip()
        _repos[repo] = revision
    org = "alphagov"
    line_number = f"L{match['line_number']}"
    return (
        f"https://github.com/{org}/{repo}/blob/{revision}/{Path(*path)}#{line_number}"
    )


class Match(TypedDict):
    lines: str
    line_number: int
    match: str
    path: Path


class ClassifiedMatch(Match):
    epics: Set[str]
    github_url: Optional[str]

    # By default this is the output of re.Match.groupdict() but if you override
    # Search._match() you can put whatever you find useful here
    groups: Dict[str, Any]


class Search:
    epic: ClassVar[str]

    globs: ClassVar[Set[str]] = set()
    paths: ClassVar[Set[Path]] = {Path(".")}

    pattern: ClassVar[str]

    _repos: Dict[str, str] = {}

    @classmethod
    def isconcrete(cls) -> bool:
        return hasattr(cls, "pattern")  # TODO: improve this

    @classmethod
    def all_searches(cls, include_self=True) -> Iterable:
        """Walk through the class hierarchy leaves first (post-order)

        >>> class TestSearch(Search):
        ...     pattern = ...
        >>> class A(TestSearch):
        ...     pattern = ...
        >>> list(TestSearch.all_searches())
        [<class 'code_taxonomy.A'>, <class 'code_taxonomy.TestSearch'>]
        >>> class B(A):
        ...     pattern = ...
        >>> list(TestSearch.all_searches())
        [<class 'code_taxonomy.B'>, <class 'code_taxonomy.A'>, <class 'code_taxonomy.TestSearch'>]
        """
        for subclass in cls.__subclasses__():
            if subclass.__subclasses__():
                yield from subclass.all_searches(include_self=False)
            yield subclass  # post-order, THIS IS IMPORTANT
        if include_self:
            yield cls

    @classmethod
    def regex(cls) -> Pattern:
        r"""
        >>> class Root(Search):
        ...     pattern = r"{root}/\w.html"
        ...     root = r"."
        >>> Root.regex()
        re.compile('(?P<root>.)/\\w.html')
        >>> class Subdir(Root):
        ...     root = r"path/to/subdir"
        >>> Subdir.regex()
        re.compile('(?P<root>path/to/subdir)/\\w.html')
        """

        class RegexFormatter(string.Formatter):
            def get_value(self, key, args, kwargs):
                try:
                    regex = getattr(cls, key)
                    regex = RegexFormatter().format(regex)
                except AttributeError:
                    raise KeyError(f"{cls} has no attribute {key}")
                return f"(?P<{key}>{regex})"

        pattern = RegexFormatter().format(cls.pattern)
        try:
            return re.compile(pattern)
        except re.error as e:
            raise AttributeError(
                f"could not compile pattern {pattern!r} for {cls}: {e}"
            )

    @staticmethod
    def rg_json_object_hook(obj):
        """
        >>> Search.rg_json_object_hook({'text': 'Hello world!'})
        'Hello world!'
        >>> Search.rg_json_object_hook({'path': 'path/to/dir'})
        {'path': PosixPath('path/to/dir')}
        """
        if set(obj.keys()) <= {"text", "bytes"}:
            if "text" in obj:
                return obj["text"]
        if "path" in obj:
            obj["path"] = Path(obj["path"])
        return obj

    @classmethod
    def _search(
        cls, pattern: Pattern, paths: Iterable[Path], globs: Iterable[str]
    ) -> Iterator[Match]:
        args: Tuple[str, ...] = tuple(
            itertools.chain(
                *itertools.product(("-e",), [pattern.pattern]),
                *itertools.product(("-g",), globs),
                map(str, paths),
            )
        )
        logging.debug(f"rg args: {' '.join(args)}")
        out = rg(*args, json=True, _tty_out=False, _iter=True, _ok_code=[0, 1])
        results = (
            json.loads(line, object_hook=cls.rg_json_object_hook) for line in out
        )
        rg_matches = (result["data"] for result in results if result["type"] == "match")
        for m in rg_matches:
            for sub in m["submatches"]:
                match: Match = m.copy()
                del match["submatches"]
                match.update(sub)
                yield match

    @classmethod
    def _match(cls, matched: Set[Type["Search"]], match: Match) -> bool:
        # this is repeating work that rg has done, but rg provides lots of nice
        # things I don't want to reimplement
        m = cls.regex().match(match["match"])
        if m:
            match["groups"] = m.groupdict()  # this is useful for debugging
        return bool(m)

    @classmethod
    def search_for(
        cls,
        searches: Iterable[Type["Search"]],
        *,
        paths: Optional[Iterable[Path]] = None,
    ) -> Iterator[ClassifiedMatch]:
        logging.debug(f"searching for {searches}")
        # We are going to construct a list of searches, tree leaves first.
        # This assumes your class hierarchy has more specific searches the
        # deeper it goes. You may get odd results otherwise.
        search_args = itertools.groupby(
            (sub for s in searches for sub in s.all_searches() if sub.isconcrete()),
            key=lambda s: (s.pattern, frozenset(s.paths), frozenset(s.globs)),
        )

        for args, _subsearches in search_args:
            subsearches = list()
            # drop duplicates while preserving order, in case `searches`
            # included two classes that are related.
            for sub in _subsearches:
                if sub.isconcrete() and sub not in subsearches:
                    subsearches.append(sub)

            pattern = subsearches[-1].regex()  # get the widest search pattern
            _matches = cls._search(pattern, paths or args[1], args[2])

            def _classify(
                match: Match, searches: Iterable[Type["Search"]]
            ) -> Set[Type["Search"]]:
                matched: Set[Type[Search]] = set()
                for search in searches:
                    if any(issubclass(m, search) for m in matched):
                        # Skip superclasses of already matched classes.
                        # There's probably a data structure that would do away
                        # with the need for this test.
                        continue
                    if search._match(matched, match):
                        matched.add(search)
                return matched

            matches: Iterator[ClassifiedMatch] = map(
                lambda m: {
                    **m,
                    "epics": {sub.epic for sub in _classify(m, subsearches)},
                    "github_url": github_url(m),
                },
                _matches,
            )

            prune: Set[str] = {
                sub.epic
                for s in searches
                for sub in s.all_searches()
                if sub not in searches and getattr(sub, "prune", False)
            }
            if prune:
                logging.debug(f"pruning epics {prune}")
                matches = map(lambda m: {**m, "epics": m["epics"] - prune}, matches)
                matches = filter(lambda m: bool(m["epics"]), matches)

            yield from matches

    @classmethod
    def main(cls, argv=None) -> None:
        searches: Iterable[Type[Search]]
        epics: Dict[str, List[Type[Search]]]

        def search_epic_key(s: Search) -> str:
            return s.epic.lower().translate(
                str.maketrans({" ": "-", ".": "", "(": "", ")": ""})
            )

        searches = set(s for s in cls.all_searches() if hasattr(s, "epic"))
        epics = {
            epic_key: list(epic_searches)
            for epic_key, epic_searches in itertools.groupby(
                sorted(searches, key=search_epic_key),
                key=search_epic_key,
            )
        }
        epics.setdefault("all", [cls])

        epics_help = "\n\t" + "\n\t".join(sorted(epics.keys()))
        parser = ArgumentParser(
            epilog=f"You can search using for following epics:\n{epics_help}",
            formatter_class=RawDescriptionHelpFormatter,
        )
        parser.add_argument(
            "epics",
            choices=epics.keys(),
            metavar="<epic>",
            help="epics to search for",
        )

        iso_date_parser = lambda s: datetime.datetime.strptime(s, "%Y-%m-%d").date()
        parser.add_argument("--from-date", type=iso_date_parser)
        parser.add_argument("--to-date", type=iso_date_parser)
        parser.add_argument(
            "--format", choices=("csv", "json", "plain"), default="plain"
        )
        parser.add_argument(
            "--summary",
            action="store_true",
            help="print statistics instead of normal output",
        )
        parser.add_argument("--path", action="append")
        parser.add_argument("--verbose", "-v", action="count", default=0)
        args = parser.parse_args()

        if args.verbose >= 1:
            logging.basicConfig(level="DEBUG")
            logging.getLogger("sh").setLevel("WARNING")
        if args.verbose >= 4:
            logging.getLogger("sh").setLevel("DEBUG")

        searches = epics[args.epics]

        if args.from_date:
            if not args.to_date:
                args.to_date = datetime.date.today()
            date_range = [
                args.from_date + datetime.timedelta(days=n)
                for n in range(
                    0, (args.to_date - args.from_date).days + 1, 7
                )
            ]
            paths = {
                path
                for s in searches
                for search in s.all_searches()
                for path in search.paths
            }
            repos = {path: {} for path in paths}
            # check all paths are okay
            okay = True
            for path in paths:
                try:
                    git_status = str(
                        git("-C", path, "status", porcelain="v2", branch=True)
                    ).splitlines()
                    branch_head = [
                        l.split(" ")[2]
                        for l in git_status
                        if l.startswith("# branch.head")
                    ][0]
                    repos[path]["ORIG_HEAD"] = branch_head
                    if branch_head == "(detached)" in git_status:
                        print(
                            f"git repo {path} is in a detached state, you should checkout a branch before using --from-date",
                            file=sys.stderr,
                        )
                        okay = False
                    if any(l.startswith(("1", "2", "u")) for l in git_status):
                        print(
                            f"git repo {path} has changes, you should stash these before using --from-date",
                            file=sys.stderr,
                        )
                        okay = False
                except sh.ErrorReturnCode as e:
                    print(f"git status failed for {path}: {e}", file=sys.stderr)
                    okay = False
            if not okay:
                print(
                    "the --date-from feature requires all paths to be a clean git repo",
                    file=sys.stderr,
                )
                return
            for path in paths:
                repos[path]["date_revs"] = {
                    date: str(
                        git(
                            "-C",
                            path,
                            "rev-list",
                            "-1",
                            f"--before={date.strftime('%Y-%m-%d')}",
                            "--merges",  # try and restrict to working trees
                            "--branches=ma*",  # main or master
                        )
                    ).strip()
                    or None
                    for date in date_range
                }
                if not all(repos[path]["date_revs"].values()):
                    most_recent_bad_date = max(
                        date
                        for date, value in repos[path]["date_revs"].items()
                        if value is None
                    )
                    print(
                        f"date {most_recent_bad_date} is too far in the past for {path}"
                    )
                    okay = False
            if not okay:
                return
            try:
                date_totals = {
                    date: {
                        "revisions": {
                            path: repos[path]["date_revs"][date] for path in repos
                        }
                    }
                    for date in date_range
                }
                print("date", "count", sep=",")
                for date in date_range:
                    for path in paths:
                        git(
                            "-C", path, "checkout", date_totals[date]["revisions"][path]
                        )
                    matches = list(Search.search_for(searches))
                    date_totals[date]["matches"] = matches
                    print(date, len(matches), sep=",")
            finally:
                for path in repos:
                    try:
                        git("-C", path, "checkout", repos[path]["ORIG_HEAD"])
                    except sh.ErrorReturnCode as e:
                        print(
                            f"warning, could not checkout {repos[path]['ORIG_HEAD']} in {path}: {e}"
                        )
            return

        matches = Search.search_for(searches, paths=args.path)

        if args.summary:
            counter: Counter[str] = collections.Counter()
            for m in matches:
                for epic in m["epics"]:
                    counter[epic] += 1
            print("epic", "count", sep=",")
            for epic, count in counter.items():
                print(epic, count, sep=",")
        elif args.format == "json":

            def json_dumps_default(obj):
                if isinstance(obj, Path):
                    return str(obj)
                elif isinstance(obj, set):
                    return tuple(obj)
                else:
                    raise TypeError(obj)

            print(json.dumps(list(matches), default=json_dumps_default, indent=2))
        elif args.format == "csv":
            csvwriter = csv.writer(sys.stdout)
            csvwriter.writerow(["file", "line", "code", "github_url", "epic"])
            for m in matches:
                for epic in m["epics"]:
                    csvwriter.writerow(
                        [
                            str(m["path"]),
                            m["line_number"],
                            m["lines"].strip(),
                            f"""=HYPERLINK("{m['github_url']}", "link")""",
                            epic,
                        ]
                    )
        elif args.format == "plain":
            printer = lambda *args: print(*args, sep=",")  # noqa: E731
            printer("file", "line", "code", "epic")
            for m in matches:
                for epic in m["epics"]:
                    printer(
                        str(m["path"]),
                        m["line_number"],
                        m["lines"].strip(),
                        epic,
                    )


if __name__ == "__main__":
    Search.main()
