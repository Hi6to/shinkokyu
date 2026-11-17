# minimal S-expression parser/serializer for KiCad files
import re
TOK = re.compile(r'\s*(?:(\()|(\))|("(?:[^"\\]|\\.)*")|([^\s()"]+))')
BS = chr(92)


class Sym(str):
    pass


def parse(s):
    pos = 0
    stack = [[]]
    while True:
        m = TOK.match(s, pos)
        if not m or m.end() == pos:
            break
        pos = m.end()
        o, c, qq, a = m.groups()
        if o:
            stack.append([])
        elif c:
            x = stack.pop()
            stack[-1].append(x)
        elif qq is not None:
            stack[-1].append(qq[1:-1].replace(BS + '"', '"').replace(BS + BS, BS))
        else:
            stack[-1].append(Sym(a))
    return stack[0][0]


def q(x):
    return '"' + x.replace(BS, BS + BS).replace('"', BS + '"').replace('\n', BS + 'n') + '"'


def dump(e, ind=0):
    if isinstance(e, list):
        if not e:
            return '()'
        simple = all(not isinstance(x, list) for x in e)
        if simple:
            return '(' + ' '.join(dump(x) for x in e) + ')'
        out = '(' + dump(e[0])
        for x in e[1:]:
            if isinstance(x, list):
                out += '\n' + '\t' * (ind + 1) + dump(x, ind + 1)
            else:
                out += ' ' + dump(x)
        return out + '\n' + '\t' * ind + ')'
    if isinstance(e, Sym):
        return str(e)
    if isinstance(e, bool):
        return 'yes' if e else 'no'
    if isinstance(e, (int, float)):
        v = round(float(e), 4)
        if v == int(v):
            return '%d' % v
        return ('%.4f' % v).rstrip('0').rstrip('.')
    return q(e)


def find(e, key):
    return [x for x in e if isinstance(x, list) and x and x[0] == key]


def find1(e, key):
    r = find(e, key)
    return r[0] if r else None
