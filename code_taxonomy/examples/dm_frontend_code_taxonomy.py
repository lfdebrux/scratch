import re
from pathlib import Path

from code_taxonomy import Search

FRONTEND_REPOS = {
    Path("digitalmarketplace-admin-frontend"),
    Path("digitalmarketplace-buyer-frontend"),
    Path("digitalmarketplace-briefs-frontend"),
    Path("digitalmarketplace-brief-responses-frontend"),
    Path("digitalmarketplace-supplier-frontend"),
    Path("digitalmarketplace-user-frontend"),
}


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
    def _match(cls, matched, match):
        m = Styles.regex().search(match["match"])
        classes = m["classes"].split()
        for classname in classes:
            if re.match(cls.classname, classname):
                if "groups" not in match:
                    match["groups"] = m.groupdict()
                    match["groups"]["classes"] = set(classes)
                    match["groups"]["classname"] = set()
                if cls is not Styles:
                    match["groups"]["classname"].add(classname)
                matched.add(cls)
        if "groups" in match and (
            match["groups"]["classname"] != match["groups"]["classes"]
        ):
            matched.add(Styles)
        else:
            matched.discard(Styles)
        return cls in matched


class GOVUKStyles(Styles):
    epic = "GOV.UK Frontend styles"

    classname = r"""govuk-[\w_-]+"""

    prune = True


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

    prune = True


class BuyerFrontendOverrides(Styles):
    epic = "App overrides (old)"

    classname = r"""(?x:
        save-search-page |
        marketplace-homepage-heading |
        which-service-won-contract-page |
        tell-us-about-contract-page |
        did-you-award-contract-page |
        sidebar-heading
    )"""


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

    prune = True


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


class NotificationBannerTemplate(TemplateInclude):
    epic = "Banner"

    template = "notification-banner.html"


class NotificationBannerStyles(Styles):
    epic = "Banner"

    classname = r"banner.*"


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


class TemporaryMessageTemplate(TemplateInclude):
    epic = "Banner"

    template = "temporary-message.html"


class TextInputWTForms(DMWTForms):
    epic = "Text input"

    field_type = "StripWhitespaceString"


class ValidationBannerTemplates(TemplateInclude):
    epic = "Error summary"

    template = "forms/validation.html"


if __name__ == "__main__":
    FrontendCode.main()
