"""Lift the rounded-square icon out of design/folio-icon.png.

The source sits on a rectangular white field. Settings and the popup use only
the icon, including the shadow already drawn around it. The field outside that
shadow becomes transparent. Toolbar sizes stay on the full canvas.
"""
from collections import deque
from pathlib import Path
from PIL import Image

root = Path(__file__).resolve().parents[1]
source = Image.open(root / 'design' / 'folio-icon.png').convert('RGB')
width, height = source.size
pixels = source.load()

def is_face(color):
    red, green, blue = color
    level = (red * 299 + green * 587 + blue * 114) // 1000
    warmth = (red + green) // 2 - blue
    return warmth >= 5 and level >= 232

face = bytearray(width * height)
queue = deque([(400, 500)])
face[500 * width + 400] = 1
while queue:
    x, y = queue.popleft()
    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
        if nx < 0 or ny < 0 or nx >= width or ny >= height:
            continue
        index = ny * width + nx
        if not face[index] and is_face(pixels[nx, ny]):
            face[index] = 1
            queue.append((nx, ny))

outside = bytearray(width * height)
queue = deque([(0, 0)])
outside[0] = 1
while queue:
    x, y = queue.popleft()
    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
        if nx < 0 or ny < 0 or nx >= width or ny >= height:
            continue
        index = ny * width + nx
        if not outside[index] and not face[index]:
            outside[index] = 1
            queue.append((nx, ny))

background = (253, 253, 253)
mark = Image.new('RGBA', (width, height), (0, 0, 0, 0))
output = mark.load()
bounds = [width, height, 0, 0]
for y in range(height):
    for x in range(width):
        index = y * width + x
        red, green, blue = pixels[x, y]
        if face[index] or not outside[index]:
            output[x, y] = (red, green, blue, 255)
        else:
            deficit = max(background[0] - red, background[1] - green, background[2] - blue, 0)
            if deficit <= 3:
                continue
            output[x, y] = (0, 0, 0, min(255, deficit * 255 // 253))
        bounds[0] = min(bounds[0], x)
        bounds[1] = min(bounds[1], y)
        bounds[2] = max(bounds[2], x)
        bounds[3] = max(bounds[3], y)

pad = 8
cropped = mark.crop((
    max(0, bounds[0] - pad),
    max(0, bounds[1] - pad),
    min(width, bounds[2] + 1 + pad),
    min(height, bounds[3] + 1 + pad),
))
cropped.save(root / 'icons' / 'mark.png', 'PNG')
