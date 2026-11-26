with open(r'c:\Users\lucky\Downloads\jarvis\jarvis\static\index.html', 'r', encoding='utf-8') as f:
    text = f.read()

import re
js = re.findall(r'<script>(.*?)</script>', text, re.DOTALL)[0]

# Simple parser using tokenizer or basic state machine
state = 'code'
stack = []
i = 0
n = len(js)
line = 1

while i < n:
    c = js[i]
    if c == '\n':
        line += 1

    if state == 'code':
        if c == '/' and i + 1 < n and js[i+1] == '/':
            state = 'line_comment'
            i += 2
            continue
        elif c == '/' and i + 1 < n and js[i+1] == '*':
            state = 'block_comment'
            i += 2
            continue
        elif c == "'" or c == '"':
            state = 'string_' + c
            i += 1
            continue
        elif c == '`':
            state = 'template'
            i += 1
            continue
        elif c == '/' and i + 1 < n and js[i+1] not in ['/', '*', '=']:
            # possible regex literal if preceded by punctuation/operator/keyword
            prev = js[:i].rstrip()
            if prev and prev[-1] in '=(,[{:;!&|?~^+-*%':
                state = 'regex'
                i += 1
                continue
        if c in '([{':
            stack.append((c, line))
        elif c in ')]}':
            if not stack:
                print(f"Error: unmatched {c} at line {line}")
            else:
                top, l = stack.pop()
    elif state == 'line_comment':
        if c == '\n':
            state = 'code'
    elif state == 'block_comment':
        if c == '*' and i + 1 < n and js[i+1] == '/':
            state = 'code'
            i += 1
    elif state.startswith('string_'):
        q = state[-1]
        if c == '\\':
            i += 2
            continue
        elif c == q:
            state = 'code'
    elif state == 'template':
        if c == '\\':
            i += 2
            continue
        elif c == '`':
            state = 'code'
    elif state == 'regex':
        if c == '\\':
            i += 2
            continue
        elif c == '/':
            state = 'code'

    i += 1

print(f"Result: stack size = {len(stack)}")
if stack:
    for item in stack:
        print("Unclosed:", item)
else:
    print("SUCCESS: 0 syntax errors, 0 unclosed brackets in JS!")
