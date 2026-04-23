from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import re
import unicodedata

BASH_PROMPT_PATTERN = re.compile(r"^(?:\([^)]*\)\s+)?[^\s$#][^\s]*[$#](?:\s.*)?$")
INTERNAL_BASH_LINES = {
    '$ local command_text="${BASH_COMMAND:-}"',
    '$ builtin fc -ln -1 -1',
    '$ builtin fc -ln -0 -0',
}
RAW_BASH_EDIT_TOKENS = ("\b", "\x07", "\x1b[A", "\x1b[B", "\x1b[C", "\x1b[D", "\x1b[K", "\x1b[P")


@dataclass(frozen=True, slots=True)
class SearchOptions:
    highlight_all: bool = True
    case_sensitive: bool = False
    match_accents: bool = False
    whole_word: bool = False

    def toggled(self, index: int) -> "SearchOptions":
        if index == 1:
            return replace(self, highlight_all=not self.highlight_all)
        if index == 2:
            return replace(self, case_sensitive=not self.case_sensitive)
        if index == 3:
            return replace(self, match_accents=not self.match_accents)
        if index == 4:
            return replace(self, whole_word=not self.whole_word)
        return self


@dataclass(frozen=True, slots=True)
class Match:
    line_index: int
    start_col: int
    end_col: int
    ordinal: int = -1


def _apply_csi(line: list[str], cursor: int, parameters: str, final: str) -> int:
    first_parameter = parameters.split(";", 1)[0]
    count = int(first_parameter) if first_parameter.isdigit() else 1

    if final == "C":
        return cursor + count
    if final == "D":
        return max(0, cursor - count)
    if final == "G":
        return max(0, count - 1)
    if final == "K":
        del line[cursor:]
        return cursor
    if final == "P":
        del line[cursor : cursor + count]
        return cursor
    return cursor


def _strip_terminal_controls(text: str) -> str:
    lines: list[str] = []
    line: list[str] = []
    cursor = 0
    index = 0

    def write_char(char: str) -> None:
        nonlocal cursor
        if cursor > len(line):
            line.extend(" " * (cursor - len(line)))
        if cursor == len(line):
            line.append(char)
        else:
            line[cursor] = char
        cursor += 1

    while index < len(text):
        char = text[index]

        if char == "\n":
            lines.append("".join(line))
            line = []
            cursor = 0
            index += 1
            continue

        if char == "\r":
            cursor = 0
            index += 1
            continue

        if char == "\b":
            cursor = max(0, cursor - 1)
            index += 1
            continue

        if char in {"\a", "\x00"}:
            index += 1
            continue

        if char == "\x1b":
            if index + 1 >= len(text):
                break

            next_char = text[index + 1]
            if next_char == "]":
                index += 2
                while index < len(text):
                    if text[index] == "\a":
                        index += 1
                        break
                    if text[index] == "\x1b" and index + 1 < len(text) and text[index + 1] == "\\":
                        index += 2
                        break
                    index += 1
                continue

            if next_char == "[":
                sequence_end = index + 2
                while sequence_end < len(text) and not (0x40 <= ord(text[sequence_end]) <= 0x7E):
                    sequence_end += 1

                if sequence_end >= len(text):
                    break

                cursor = _apply_csi(
                    line=line,
                    cursor=cursor,
                    parameters=text[index + 2 : sequence_end],
                    final=text[sequence_end],
                )
                index = sequence_end + 1
                continue

            index += 2
            continue

        if char == "\t":
            tab_width = 4 - (cursor % 4)
            for _ in range(tab_width):
                write_char(" ")
            index += 1
            continue

        if ord(char) < 32 or ord(char) == 127:
            index += 1
            continue

        write_char(char)
        index += 1

    if line:
        lines.append("".join(line))

    return "\n".join(lines)


def strip_ansi(text: str) -> str:
    return _strip_terminal_controls(text.replace("\r\n", "\n"))


def _clean_bash_lines(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    last_command: str | None = None
    for line in lines:
        if line in INTERNAL_BASH_LINES:
            continue

        if BASH_PROMPT_PATTERN.match(line):
            continue

        if line.startswith("$ "):
            if line == last_command:
                continue
            last_command = line
        elif line:
            last_command = None

        cleaned.append(line)
    return cleaned


def prepare_transcript_lines(text: str, source: Path | None = None) -> list[str]:
    if source is not None and source.name.startswith("bash-"):
        raw_lines = text.replace("\r\n", "\n").split("\n")
        cleaned: list[str] = []
        for raw_line in raw_lines:
            normalized_parts = strip_ansi(raw_line).splitlines() or [""]
            normalized = normalized_parts[0]

            if normalized in INTERNAL_BASH_LINES:
                continue

            if BASH_PROMPT_PATTERN.match(normalized):
                continue

            if any(token in raw_line for token in RAW_BASH_EDIT_TOKENS) and not normalized.startswith("$ "):
                continue

            cleaned.extend(normalized_parts)

        filtered = _clean_bash_lines(cleaned)
        return [line for line in filtered if line]

    return strip_ansi(text).splitlines()


def _normalize_fragment(fragment: str, options: SearchOptions) -> str:
    result = fragment
    if not options.match_accents:
        result = "".join(
            char
            for char in unicodedata.normalize("NFD", result)
            if unicodedata.category(char) != "Mn"
        )
    if not options.case_sensitive:
        result = result.casefold()
    return result


def _build_searchable(text: str, options: SearchOptions) -> tuple[str, list[int]]:
    searchable: list[str] = []
    index_map: list[int] = []
    for original_index, char in enumerate(text):
        normalized = _normalize_fragment(char, options)
        if not normalized:
            continue
        for normalized_char in normalized:
            searchable.append(normalized_char)
            index_map.append(original_index)
    return "".join(searchable), index_map


def _is_word_char(char: str) -> bool:
    return char.isalnum() or char == "_"


def _whole_word_ok(line: str, start_col: int, end_col: int) -> bool:
    left_ok = start_col == 0 or not _is_word_char(line[start_col - 1])
    right_ok = end_col >= len(line) or not _is_word_char(line[end_col])
    return left_ok and right_ok


def find_matches_in_line(
    line: str,
    query: str,
    options: SearchOptions,
    line_index: int,
) -> list[Match]:
    searchable_query = _normalize_fragment(query, options)
    if not searchable_query:
        return []

    searchable_line, index_map = _build_searchable(line, options)
    if not searchable_line:
        return []

    matches: list[Match] = []
    cursor = 0
    query_length = len(searchable_query)
    step = max(1, query_length)

    while cursor < len(searchable_line):
        found_at = searchable_line.find(searchable_query, cursor)
        if found_at == -1:
            break

        start_col = index_map[found_at]
        end_col = index_map[found_at + query_length - 1] + 1

        if not options.whole_word or _whole_word_ok(line, start_col, end_col):
            matches.append(Match(line_index=line_index, start_col=start_col, end_col=end_col))

        cursor = found_at + step

    return matches


def search_lines(lines: list[str], query: str, options: SearchOptions) -> list[Match]:
    matches: list[Match] = []
    for line_index, line in enumerate(lines):
        matches.extend(find_matches_in_line(line=line, query=query, options=options, line_index=line_index))

    return [replace(match, ordinal=ordinal) for ordinal, match in enumerate(matches)]
