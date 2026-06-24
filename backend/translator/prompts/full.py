from translator.core.types import TranslationDomain
from translator.prompts.domains import domain_hint


def build_full_system_prompt(domain: TranslationDomain, target_language: str) -> str:
    return (
        f"英译{target_language}。{domain_hint(domain)}。"
        "仅输出译文，保留段落。"
    )


def build_full_user_prompt() -> str:
    return "翻译："


def build_full_image_user_prompt() -> str:
    return "识别图中英文并译为中文，仅输出译文。"


def build_full_image_system_prompt(domain: TranslationDomain, target_language: str) -> str:
    return (
        f"OCR+英译{target_language}。{domain_hint(domain)}。"
        "仅输出译文，保留段落。"
    )
