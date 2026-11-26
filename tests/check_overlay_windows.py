import win32gui, win32process

hwnds = []
def enum_cb(hwnd, extra):
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    if pid in [13972, 31460]:
        rect = win32gui.GetWindowRect(hwnd)
        visible = win32gui.IsWindowVisible(hwnd)
        title = win32gui.GetWindowText(hwnd)
        cls = win32gui.GetClassName(hwnd)
        print(f"HWND: {hwnd}, PID: {pid}, Class: {cls}, Visible: {visible}, Rect: {rect}, Title: '{title}'")
        hwnds.append(hwnd)
    return True

win32gui.EnumWindows(enum_cb, None)
print(f"Total windows found: {len(hwnds)}")
