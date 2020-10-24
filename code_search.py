#!/usr/bin/env python3

"""
Find and classify code

This package lets you find bits of code in a large codebase using a Python DSL.

Bugs
====

It needs to be better documented.

In some places the code is excessively clever, and in others it is overly simplistic.

---

Copyright (c) 2020, Crown Copyright (Government Digital Service)
"""

import csv
import itertools
import json
import logging
import re
import string
import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from pathlib import Path
from typing import (
    ClassVar,
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

FRONTEND_REPOS = {
    Path("digitalmarketplace-admin-frontend"),
    Path("digitalmarketplace-buyer-frontend"),
    Path("digitalmarketplace-briefs-frontend"),
    Path("digitalmarketplace-brief-responses-frontend"),
    Path("digitalmarketplace-supplier-frontend"),
    Path("digitalmarketplace-user-frontend"),
}


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
        """Walk through the class hierarchy depth first

        >>> class TestSearch(Search):
        ...     pattern = ...
        >>> class A(TestSearch):
        ...     pattern = ...
        >>> list(TestSearch.all_searches())
        [<class 'code_search.A'>, <class 'code_search.TestSearch'>]
        >>> class B(A):
        ...     pattern = ...
        >>> list(TestSearch.all_searches())
        [<class 'code_search.B'>, <class 'code_search.A'>, <class 'code_search.TestSearch'>]
        """
        for subclass in cls.__subclasses__():
            if subclass.__subclasses__():
                yield from subclass.all_searches(include_self=False)
            yield subclass  # depth first, THIS IS IMPORTANT
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
    ) -> Iterator[dict]:
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
        matches = (result["data"] for result in results if result["type"] == "match")
        return matches

    @classmethod
    def _match(cls, matched: Set[Type["Search"]], match: dict, submatch: dict) -> bool:
        # this is repeating work that rg has done, but rg provides lots of nice
        # things I don't want to reimplement
        m = cls.regex().match(submatch["match"])
        if m:
            submatch["groups"] = m.groupdict()  # this is useful for debugging
        return bool(m)

    @classmethod
    def search_for(
        cls,
        searches: Iterable[Type["Search"]],
        *,
        paths: Optional[Iterable[Path]] = None,
    ) -> Iterator[dict]:
        logging.debug(f"searching for {searches}")
        # We are going to construct a list of searches, depth first.
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
            matches = cls._search(pattern, paths or args[1], args[2])

            def _classify(
                match: dict, searches: Iterable[Type["Search"]]
            ) -> Set[Type["Search"]]:
                matched: Set[Type[Search]] = set()
                for search in searches:
                    if any(issubclass(m, search) for m in matched):
                        # Skip superclasses of already matched classes.
                        # There's probably a data structure that would do away
                        # with the need for this test.
                        continue
                    for submatch in match["submatches"]:
                        if search._match(matched, match, submatch):
                            matched.add(search)
                return matched

            matches = map(
                lambda m: {
                    **m,
                    "epics": [sub.epic for sub in _classify(m, subsearches)],
                    "github_url": github_url(m),
                },
                matches,
            )

            yield from matches

    @classmethod
    def main(cls, argv=None) -> None:
        searches: Iterable[Type[Search]]
        epics: Dict[str, List[Type[Search]]]

        searches = set(s for s in Search.all_searches() if hasattr(s, "epic"))
        epics = {
            epic_key: list(epic_searches)
            for epic_key, epic_searches in itertools.groupby(
                searches,
                key=lambda c: c.epic.lower().replace(" ", "-").replace(".", ""),
            )
        }
        epics.setdefault("all", [cls])

        epics_help = "\n\t" + "\n\t".join(sorted(epics.keys()))
        parser = ArgumentParser(
            epilog=f"You can search using for following epics:\n{epics_help}",
            formatter_class=RawDescriptionHelpFormatter,
        )
        parser.add_argument(
            "epics", choices=epics.keys(), metavar="<epic>", help="epics to search for",
        )
        parser.add_argument(
            "--format", choices=("csv", "json", "plain"), default="plain"
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
        matches = Search.search_for(searches, paths=args.path)

        if args.format == "json":

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
                        str(m["path"]), m["line_number"], m["lines"].strip(), epic,
                    )


def test_code_search():
    """Test the functioning of Search.search_for()
    """
    # test fixtures
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as testdir:
        testdir = Path(testdir)
        (testdir / "test1.txt").write_text("Hello foo")
        (testdir / "test2.txt").write_text("Hello bar")
        (testdir / "test3.txt").write_text("Goodbye foobar")

        class Hello(Search):
            epic = "Hello"
            paths = (testdir,)
            pattern = r"Hello {name}"
            name = ".*"

        class HelloFoo(Hello):
            epic = "Hello foo"
            name = "foo"

        matches = list(Search.search_for([Hello, HelloFoo]))

        assert len(matches) == 2
        for match in matches:
            assert str(match["path"]).startswith(str(testdir))
            if match["path"].name == "test1.txt":
                assert match["epics"] == ["Hello foo"]
                assert match["lines"] == "Hello foo"
            elif match["path"].name == "test2.txt":
                assert match["epics"] == ["Hello"]
                assert match["lines"] == "Hello bar"
            else:
                assert match["path"].name != "test3.txt"

    return None


#
# Rules
#


class FrontendCode(Search):
    epic = "All components"

    paths = FRONTEND_REPOS
    globs = {"!__snapshots__/**", "!*/tests/**"}


class Styles(FrontendCode):
    epic = "All styles"

    pattern = r"""<{element} [^>]*class=["']{classes}["'][^>]*>"""

    element = (
        r"(a|button|div|h[1-6]|input|li|ol|p|strong|ul)"  # no need to look at all tags
    )
    classes = r"(?:{classname}[ ]?)+"
    classname = r"[\w_-]+"

    @classmethod
    def _match(cls, matched, match, submatch):
        m = Styles.regex().search(submatch["match"])
        classes = m["classes"].split()
        for classname in classes:
            if re.match(cls.classname, classname):
                if "groups" not in submatch:
                    submatch["groups"] = m.groupdict()
                    submatch["groups"]["classes"] = set(classes)
                    submatch["groups"]["classname"] = set()
                if cls is not Styles:
                    submatch["groups"]["classname"].add(classname)
                matched.add(cls)
        if "groups" in submatch and (
            submatch["groups"]["classname"] != submatch["groups"]["classes"]
        ):
            matched.add(Styles)
        else:
            matched.discard(Styles)
        return cls in matched


class GOVUKStyles(Styles):
    epic = "GOV.UK Frontend styles"

    classname = r"""govuk-[\w_-]+"""


class JinjaCode(FrontendCode):
    epic = "All Jinja code"


class MacroImport(JinjaCode):
    epic = "All macros"

    pattern = r"""\{{% import ['"]toolkit/{macros_from}['"]( as \w*)? %\}}"""

    macros_from = r"""[^'"]+"""


class TemplateInclude(JinjaCode):
    epic = "All templates"

    pattern = r"""\{{% include ['"]toolkit/{template}['"] %\}}"""

    template = r"""[^'"]+"""


class DMWTForms(FrontendCode):
    epic = "DMUtils WTForms"

    pattern = r"DM{field_type}Field"

    field_type = r"(Boolean|Decimal|Hidden|Integer|Radio|String|Email|StripWhitespaceString|Date)"


#
# Epics
#


class AppStyles(Styles):
    epic = "App overrides"

    classname = r"app-*"


class CheckboxesWTForms(DMWTForms):
    epic = "Checkboxes"

    field_type = "Boolean"


class ContactDetails(TemplateInclude):
    epic = "Contact details"

    template = "contact-details.html"


class DateInputWTForms(DMWTForms):
    epic = "Date input"

    field_type = "Date"


class DMSpeak(Styles):
    epic = "DMSpeak"

    classname = r"(dmspeak|legal-content|single-question-page)"


class DMFrontendStyles(Styles):
    epic = "Digital Marketplace GOV.UK Frontend styles"

    classname = r"dm-.*"


class JavaScript(Styles):
    epic = "JavaScript"

    classname = r"js-.*"


class Headings(Styles):
    epic = "Typography"

    classname = r"(heading-.*|sidebar-heading|marketplace-homepage-heading)"


class InstructionListStyles(Styles):
    epic = "Instruction list"

    classname = r"browse-list.*"


class InstructionListTemplate(TemplateInclude):
    epic = "Instruction list"

    template = "instruction-list.html"


class InsetText(Styles):
    epic = "Inset text"

    classname = r"(panel.*|notice.*)"


class RadiosTemplate(TemplateInclude):
    epic = "Radios"

    template = r"forms/(_selection-button|selection-buttons).html"


class RadiosWTForms(DMWTForms):
    epic = "Radios"

    field_type = "Radio"


class SearchSummaryStyles(Styles):
    epic = "Search summary"

    classname = "search-summary.*"


class SearchSummaryTemplate(TemplateInclude):
    epic = "Search summary"

    template = "search-summary.html"


class TextInputWTForms(DMWTForms):
    epic = "Text input"

    field_type = "StripWhitespaceString"


class ValidationBannerTemplates(TemplateInclude):
    epic = "Error summary"

    template = "forms/validation.html"


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--test":
        from sh import black, flake8, mypy, python

        sep = "------------------"
        err = lambda *args: print(*args, file=sys.stderr)  # noqa: E731

        try:
            err("running unit tests")
            python("-m", "doctest", __file__, _fg=True)
        except sh.ErrorReturnCode:
            err(sep)

        try:
            err("running integration test")
            test_code_search()
        except AssertionError as e:
            err(f"integration test test_code_search() failed with error: {e}")
            err(sep)

        try:
            err(f"flake8 {sys.argv[0]}")
            flake8(__file__, ignore="E501", _fg=True)
        except sh.ErrorReturnCode:
            err(sep)

        try:
            err(f"mypy {sys.argv[0]}")
            mypy(__file__, _fg=True)
        except sh.ErrorReturnCode:
            pass
        finally:
            err(sep)

        try:
            err(f"black {sys.argv[0]}")
            black(__file__, check=True, _fg=True)
        except sh.ErrorReturnCode:
            pass
        finally:
            err(sep)

    else:
        Search.main()
