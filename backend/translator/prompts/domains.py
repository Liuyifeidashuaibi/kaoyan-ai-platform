from translator.core.types import TranslationDomain


def domain_hint(domain: TranslationDomain) -> str:
    hints = {
        TranslationDomain.TEXTBOOK: "教材",
        TranslationDomain.PAPER: "学术论文",
        TranslationDomain.TECHNICAL: "技术文档",
    }
    return hints[domain]
