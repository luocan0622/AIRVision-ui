"""测试资源命名工具：test_数字 序号生成。"""
import os
import re

TEST_NUMBER_PATTERN = re.compile(r"^test_(\d+)$", re.I)
NUMBERED_LABEL_PATTERN = re.compile(r"^(.+?)\s+(\d+)$", re.I)


def parse_test_number(name: str) -> int | None:
    """从 test_数字 名称解析序号，不匹配则返回 None。"""
    match = TEST_NUMBER_PATTERN.match(name)
    return int(match.group(1)) if match else None


def next_test_name(numbers: list[int]) -> str:
    """根据已占用序号生成下一个 test_数字 名称。"""
    return f"test_{max(numbers, default=0) + 1}"


def collect_numbers_from_filenames(
    directory: str,
    *,
    file_suffix: str = "",
    data_dir_suffix: str = "",
) -> list[int]:
    """从目录中的文件名收集 test_数字 序号。

    Args:
        directory: 扫描目录。
        file_suffix: 文件扩展名（如 ``.airvision``），匹配 ``test_N{suffix}``。
        data_dir_suffix: 目录后缀（如 ``_data``），匹配 ``test_N{suffix}`` 目录名。
    """
    numbers: list[int] = []
    if not os.path.isdir(directory):
        return numbers

    for name in os.listdir(directory):
        stem = os.path.splitext(name)[0]
        if file_suffix and name.lower().endswith(file_suffix.lower()):
            num = parse_test_number(stem)
            if num is not None:
                numbers.append(num)
        elif data_dir_suffix and name.endswith(data_dir_suffix):
            num = parse_test_number(name[: -len(data_dir_suffix)])
            if num is not None:
                numbers.append(num)

    return numbers


def next_numbered_label(
    prefix: str,
    existing_names: list[str],
    *,
    separator: str = " ",
) -> str:
    """根据已有名称生成 ``{prefix}{separator}数字``（如 ``TCP Client 2``）。"""
    prefix_norm = prefix.strip()
    prefix_lower = prefix_norm.lower()
    numbers: list[int] = []

    for raw in existing_names:
        name = raw.strip()
        if not name:
            continue
        match = NUMBERED_LABEL_PATTERN.match(name)
        if match and match.group(1).strip().lower() == prefix_lower:
            numbers.append(int(match.group(2)))

    return f"{prefix_norm}{separator}{max(numbers, default=0) + 1}"
