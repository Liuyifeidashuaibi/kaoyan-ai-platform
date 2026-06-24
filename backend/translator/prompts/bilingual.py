from translator.core.types import TranslationDomain


def domain_hint(domain: TranslationDomain) -> str:
    hints = {
        TranslationDomain.TEXTBOOK: "教材",
        TranslationDomain.PAPER: "学术论文",
        TranslationDomain.TECHNICAL: "技术文档",
    }
    return hints[domain]


def build_bilingual_system_prompt(
    domain: TranslationDomain, target_language: str
) -> str:
    # Do NOT include concrete EN/ZH example sentences — small draft models echo them.
    return (
        f"你是专业英译{target_language}译者，文体：{domain_hint(domain)}。"
        "对用户给出的每个英文句子：先输出该句英文原文（与输入完全一致，不改写），"
        "下一行输出准确中文译文；组与组之间空一行。"
        "禁止合并多句、禁止编号、禁止解释、禁止只输出中文、禁止输出与输入无关的内容。"
    )


def build_bilingual_user_prompt() -> str:
    return "逐句双语对照："


def build_bilingual_batch_user_prompt(sentences: list[str]) -> str:
    n = len(sentences)
    return f"以下{n}个英文句子，逐句输出双语（每句先英后中，句间空行）："


def build_bilingual_image_user_prompt() -> str:
    return "图中英文逐句双语：每句英+中，句间空行。"
