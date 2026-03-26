from __future__ import annotations


def should_attempt_title_generation(
    enable_title: bool, images, product_info: str = ""
) -> bool:
    return bool(enable_title and (images or str(product_info or "").strip()))


def generate_titles_or_raise(client, images, product_info: str, template_prompt: str):
    has_images = bool(images)
    clean_info = str(product_info or "").strip()

    if has_images:
        titles = client.generate_titles_from_image(images, clean_info, template_prompt)
    elif clean_info:
        titles = client.generate_titles(clean_info, template_prompt)
    else:
        raise ValueError("请至少提供商品图片或商品信息后再生成标题")

    if titles:
        return titles

    last_error = str(getattr(client, "last_error", "") or "").strip()
    if last_error:
        raise ValueError(last_error)
    raise ValueError("标题生成失败，模型未返回可解析的标题内容")


def filter_titles_by_compliance(titles: list, compliance_checker, compliance_mode: str):
    if not titles:
        return [], []

    if compliance_checker is None:
        return list(titles), []

    filtered = []
    warnings = []

    if len(titles) >= 2:
        pair_count = len(titles) // 2
        for idx in range(pair_count):
            english = titles[idx * 2]
            chinese = titles[idx * 2 + 1]
            ok, _, note = compliance_checker(english, compliance_mode)
            if ok:
                filtered.extend([english, chinese])
            else:
                warnings.append(f"标题 {idx + 1} 未通过合规检测: {note}")

        if len(titles) % 2 == 1:
            trailing = titles[-1]
            ok, _, note = compliance_checker(trailing, compliance_mode)
            if ok:
                filtered.append(trailing)
            else:
                warnings.append(f"标题 {pair_count + 1} 未通过合规检测: {note}")
        return filtered, warnings

    for idx, title in enumerate(titles):
        ok, _, note = compliance_checker(title, compliance_mode)
        if ok:
            filtered.append(title)
        else:
            warnings.append(f"标题 {idx + 1} 未通过合规检测: {note}")

    return filtered, warnings


def generate_compliant_titles_or_raise(
    client,
    images,
    product_info: str,
    template_prompt: str,
    compliance_checker=None,
    compliance_mode: str = "strict",
):
    titles = generate_titles_or_raise(client, images, product_info, template_prompt)
    filtered_titles, warnings = filter_titles_by_compliance(
        titles, compliance_checker, compliance_mode
    )

    if titles and not filtered_titles:
        detail = "；".join(warnings) if warnings else "标题未通过合规检测"
        raise ValueError(detail)

    return filtered_titles, warnings
