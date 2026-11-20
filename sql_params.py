"""Translate SQLite positional markers to psycopg markers without modifying SQL literals."""

def translate_qmark(sql):
    if not isinstance(sql, str):
        raise TypeError('SQL must be a string')
    out = []
    i = 0
    n = len(sql)
    state = 'normal'
    tag = ''
    depth = 0
    while i < n:
        c = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ''
        if state == 'normal':
            if c == "'":
                state = 'single'
                out.append(c)
                i += 1
                continue
            if c == '"':
                state = 'double'
                out.append(c)
                i += 1
                continue
            if c == '-' and nxt == '-':
                state = 'line'
                out.append('--')
                i += 2
                continue
            if c == '/' and nxt == '*':
                state = 'block'
                depth = 1
                out.append('/*')
                i += 2
                continue
            if c == '$':
                j = i + 1
                while j < n and (sql[j].isalnum() or sql[j] == '_'):
                    j += 1
                if j < n and sql[j] == '$' and (
                    j == i + 1 or sql[i + 1].isalpha() or sql[i + 1] == '_'
                ):
                    tag = sql[i:j + 1]
                    state = 'dollar'
                    out.append(tag)
                    i = j + 1
                    continue
            out.append('%s' if c == '?' else c)
            i += 1
        elif state in ('single', 'double'):
            out.append(c)
            i += 1
            if c == ("'" if state == 'single' else '"'):
                if i < n and sql[i] == c:
                    out.append(c)
                    i += 1
                else:
                    state = 'normal'
        elif state == 'line':
            out.append(c)
            i += 1
            if c == '\n':
                state = 'normal'
        elif state == 'block':
            if c == '/' and nxt == '*':
                depth += 1
                out.append('/*')
                i += 2
            elif c == '*' and nxt == '/':
                depth -= 1
                out.append('*/')
                i += 2
                if depth == 0:
                    state = 'normal'
            else:
                out.append(c)
                i += 1
        else:
            if sql.startswith(tag, i):
                out.append(tag)
                i += len(tag)
                state = 'normal'
            else:
                out.append(c)
                i += 1
    return ''.join(out)
