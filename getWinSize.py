import pygetwindow as gw

window_title = "陰陽師Onmyoji" 

# Find windows that match the title
matches = [w for w in gw.getWindowsWithTitle(window_title) if w.title]

if not matches:
    print(f"No active window found matching title: '{window_title}'")
else:
    window = matches[0]  # Take the first match
    if window.isMinimized:
        print(f"Window '{window.title}' is minimized.")
    else:
        left, top, width, height = window.left, window.top, window.width, window.height
        print(f"Window title: {window.title}")
        print(f"Position: ({left}, {top})")
        print(f"Size: {width}x{height}")
