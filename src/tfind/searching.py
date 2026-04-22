from __future__ import annotations

from dataclasses import dataclass, replace
import re
import unicodedata

ANSI_PATTERN = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


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


def strip_ansi(text: str) -> str:
    clean = ANSI_PATTERN.sub("", text)
    clean = clean.replace("\r\n", "\n")
    return clean.replace("\r", "\n")


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
