"""测试资源命名工具：test_数字 序号生成。"""
import os
import re

TEST_NUMBER_PATTERN = re.compile(r"^test_(\d+)$", re.I)


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
