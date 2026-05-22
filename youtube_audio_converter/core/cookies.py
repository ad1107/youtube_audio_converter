import re


def normalize_cookiesfrombrowser(spec: str):
    """Convert a browser cookie spec string into the tuple form yt-dlp expects."""
    spec = (spec or "").strip()
    if not spec or spec.lower() == "none":
        return None

    match = re.fullmatch(
        r"(?x)\s*(?P<name>[^+:]+)(?:\s*:\s*(?!:)(?P<profile>.+?))?(?:\s*::\s*(?P<container>.+))?\s*",
        spec,
    )
    if not match:
        return (spec,)

    browser_name = match.group("name").strip()
    profile = match.group("profile")
    container = match.group("container")

    if profile is not None:
        profile = profile.strip() or None
    if container is not None:
        container = container.strip() or None

    values = [browser_name]
    if profile is not None or container is not None:
        values.append(profile)
    if container is not None:
        values.append(None)
        values.append(container)
    return tuple(values)
