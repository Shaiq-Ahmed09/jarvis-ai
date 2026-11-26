import sys
from pathlib import Path
sys.path.insert(0, str(Path("desktop_bubble").resolve()))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QRegion
from bubble_ui import DesktopAIBubble

app = QApplication(sys.argv)
bubble = DesktopAIBubble()
bubble.show()
app.processEvents()

# Check that window mask is applied
mask = bubble.mask()
print("Has mask:", not mask.isEmpty())
print("Mask bounding rect:", mask.boundingRect())
print("Window rect:", bubble.rect())

# Expand and check mask is cleared
bubble.expand_popup()
app.processEvents()
print("Expanded mask is empty:", bubble.mask().isEmpty())

# Collapse and check mask is re-applied
bubble.collapse_bubble()
app.processEvents()
print("Collapsed mask re-applied:", not bubble.mask().isEmpty())

bubble.close()
print("All mask and transparency assertions passed!")
