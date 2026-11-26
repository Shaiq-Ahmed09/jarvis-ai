import re

with open(r'c:\Users\lucky\Downloads\jarvis\jarvis\static\index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract script
scripts = re.findall(r'<script>(.*?)</script>', content, re.DOTALL)
print(f"Found {len(scripts)} inline script blocks.")

for idx, s in enumerate(scripts):
    lines = s.split('\n')
    stack = []
    in_string = None
    escaped = False
    in_line_comment = False
    in_block_comment = False

    for line_no, line in enumerate(lines, 1):
        i = 0
        in_line_comment = False
        while i < len(line):
            ch = line[i]
            if in_block_comment:
                if ch == '*' and i + 1 < len(line) and line[i+1] == '/':
                    in_block_comment = False
                    i += 2
                    continue
                i += 1
                continue
            if in_line_comment:
                break
            if in_string:
                if escaped:
                    escaped = False
                elif ch == '\\':
                    escaped = True
                elif ch == in_string:
                    in_string = None
                i += 1
                continue
            
            # Not in string or comment
            if ch == '/' and i + 1 < len(line):
                if line[i+1] == '/':
                    in_line_comment = True
                    break
                elif line[i+1] == '*':
                    in_block_comment = True
                    i += 2
                    continue

            if ch in ["'", '"', '`']:
                in_string = ch
                escaped = False
                i += 1
                continue

            if ch in '({[':
                stack.append((ch, line_no, i + 1))
            elif ch in ')}]':
                if not stack:
                    print(f"ERROR: Unmatched closing '{ch}' at line {line_no}:{i+1}")
                else:
                    top, t_line, t_col = stack.pop()
                    matching = {'(': ')', '{': '}', '[': ']'}[top]
                    if ch != matching:
                        print(f"ERROR: Mismatched bracket '{ch}' at line {line_no}:{i+1}, expected '{matching}' opened at line {t_line}:{t_col}")
            i += 1

    if stack:
        print(f"ERROR: {len(stack)} unclosed brackets remaining:")
        for top, t_line, t_col in stack[-5:]:
            print(f"  Unclosed '{top}' opened at line {t_line}:{t_col}")
    else:
        print(f"Script block {idx}: All brackets perfectly balanced!")
