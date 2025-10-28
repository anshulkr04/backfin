import re

SEP_CELL_RE = re.compile(r'^\s*:?-{1,}\s*:?\s*$')

def split_pipe_row(line):
    if '|' not in line:
        return []
    return [p.strip() for p in line.split('|')]

def normalize_cell_count(cells):
    parts = list(cells)
    while parts and parts[0] == '':
        parts.pop(0)
    while parts and parts[-1] == '':
        parts.pop(-1)
    return len(parts)

def is_separator_row(line):
    parts = split_pipe_row(line)
    while parts and parts[0] == '':
        parts.pop(0)
    while parts and parts[-1] == '':
        parts.pop(-1)
    return bool(parts) and all(SEP_CELL_RE.match(p) for p in parts)

def check_markdown_tables(md):
    lines = md.splitlines()
    results = []
    i = 0
    n = len(lines)

    while i < n:
        if '|' not in lines[i]:
            i += 1
            continue

        start = i
        block = []
        while i < n and lines[i].strip() and '|' in lines[i]:
            block.append(lines[i])
            i += 1

        if len(block) < 2:
            continue

        header, separator = block[0], block[1]
        header_cols = normalize_cell_count(split_pipe_row(header))
        sep_cols = normalize_cell_count(split_pipe_row(separator))

        ok = True
        if not is_separator_row(separator):
            ok = False
        if header_cols == 0 or header_cols != sep_cols:
            ok = False

        for row in block[2:]:
            data_cols = normalize_cell_count(split_pipe_row(row))
            if data_cols != header_cols:
                ok = False

        results.append({"ok": ok})

    return all(r['ok'] for r in results)



