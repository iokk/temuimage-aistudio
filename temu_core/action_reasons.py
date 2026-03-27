from __future__ import annotations


def combo_analysis_reasons(image_count: int):
    reasons = []
    if int(image_count or 0) <= 0:
        reasons.append("请先上传至少 1 张商品图")
    return reasons


def combo_requirements_reasons(has_anchor: bool, total_count: int, max_total: int):
    reasons = []
    if not has_anchor:
        reasons.append("请先完成商品分析")
    if int(total_count or 0) <= 0:
        reasons.append("请至少选择 1 个出图类型")
    if int(total_count or 0) > int(max_total or 0):
        reasons.append(f"当前已超过最大生成数量 {max_total}")
    return reasons


def combo_generate_reasons(req_count: int, generating: bool):
    reasons = []
    if int(req_count or 0) <= 0:
        reasons.append("请先生成图需文案")
    if generating:
        reasons.append("当前任务正在生成中，请等待完成")
    return reasons


def smart_generate_reasons(image_count: int, product_name: str, total_count: int):
    reasons = []
    if int(image_count or 0) <= 0:
        reasons.append("请先上传至少 1 张商品图")
    if not str(product_name or "").strip():
        reasons.append("请填写商品名称")
    if int(total_count or 0) <= 0:
        reasons.append("请至少选择 1 个图片类型")
    return reasons


def title_generate_reasons(input_mode: str, product_info: str, image_count: int):
    reasons = []
    mode = str(input_mode or "")
    if mode in ["🖼️ 图片分析", "🔀 图片+文字"] and int(image_count or 0) <= 0:
        reasons.append("请先上传至少 1 张图片")
    if (
        mode in ["📝 文字描述", "🔀 图片+文字"]
        and not str(product_info or "").strip()
        and mode != "🖼️ 图片分析"
    ):
        reasons.append("请补充商品信息，或改为纯图片分析模式")
    return reasons


def translate_generate_reasons(
    upload_count: int,
    need_text: bool,
    need_image: bool,
    provider: str,
    text_supported: bool,
    image_supported: bool,
):
    reasons = []
    if int(upload_count or 0) <= 0:
        reasons.append("请先上传至少 1 张图片")
    if provider == "relay":
        if need_text and not text_supported:
            reasons.append("当前模型不支持图片文字提取/翻译")
        if need_image and not image_supported:
            reasons.append("当前模型不支持翻译出图")
    return reasons
