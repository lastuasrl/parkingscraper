#!/usr/bin/env python3
"""Check label vs line overlaps in the subway map SVG."""
import math

line_y = 185

nodes = {
    'Ortisei':        (400, line_y),
    'S. Cristina':    (530, line_y),
    'Selva':          (640, line_y),
    'Seceda':         (400, line_y - 45),
    'Resciesa':       (385, line_y - 55),
    'Bulla':          (355, line_y + 50),
    'Castelrotto':    (310, line_y + 90),
    'Siusi':          (265, line_y + 125),
    'Pontives':       (290, line_y),
    'Laion':          (200, line_y - 35),
    'Ponte Gardena':  (120, line_y),
    'Chiusa':         (75, line_y - 35),
    'Funes':          (55, line_y - 60),
    'Bressanone':     (35, line_y - 85),
    'Bolzano':        (60, line_y + 55),
    'Plan de Gralba': (720, line_y - 20),
    'Passo Gardena':  (780, line_y - 50),
    'Colfosco':       (835, line_y - 75),
    'Corvara':        (885, line_y - 95),
    'Passo Sella':    (780, line_y + 15),
    'Passo Pordoi':   (850, line_y + 40),
    'S. Giacomo':     (430, line_y - 65),
    'Col Raiser':     (555, line_y - 45),
    'Monte Pana':     (505, line_y + 45),
    'Dantercepies':   (715, line_y - 40),
}

route_lines = [
    {'id': '360', 'segments': [
        ('Selva', 'S. Cristina'), ('S. Cristina', 'Ortisei'),
        ('Ortisei', 'Pontives'),
        ('Pontives', 'Laion'), ('Laion', 'Ponte Gardena'),
        ('Ponte Gardena', 'Chiusa'), ('Chiusa', 'Funes'),
        ('Funes', 'Bressanone'),
    ]},
    {'id': '350', 'segments': [
        ('Selva', 'S. Cristina'), ('S. Cristina', 'Ortisei'),
        ('Ortisei', 'Pontives'), ('Pontives', 'Ponte Gardena'),
        ('Ponte Gardena', 'Bolzano'),
    ]},
    {'id': '172', 'segments': [
        ('Selva', 'S. Cristina'), ('S. Cristina', 'Ortisei'),
        ('Ortisei', 'Castelrotto'), ('Castelrotto', 'Siusi'),
    ]},
    {'id': '473', 'segments': [
        ('Selva', 'Plan de Gralba'),
        ('Plan de Gralba', 'Passo Gardena'), ('Passo Gardena', 'Colfosco'),
        ('Colfosco', 'Corvara'),
    ]},
    {'id': '471', 'segments': [
        ('Selva', 'Plan de Gralba'),
        ('Plan de Gralba', 'Passo Sella'), ('Passo Sella', 'Passo Pordoi'),
    ]},
]

# Build segment -> list of lines
seg_lines = {}
for li, line in enumerate(route_lines):
    for a, b in line['segments']:
        key = frozenset((a, b))
        if key not in seg_lines:
            seg_lines[key] = []
        seg_lines[key].append((li, line['id']))

spacing = 5
line_w = 3.5

def _offset(x1, y1, x2, y2, off):
    dx, dy = x2 - x1, y2 - y1
    length = (dx**2 + dy**2) ** 0.5
    if length == 0:
        return x1, y1, x2, y2
    px, py = -dy / length, dx / length
    return (x1 + px*off, y1 + py*off, x2 + px*off, y2 + py*off)

# Compute ALL actual drawn line segments (with parallel offsets)
all_lines = []
drawn = set()
for line in route_lines:
    for a, b in line['segments']:
        key = frozenset((a, b))
        if key in drawn:
            continue
        drawn.add(key)
        ax, ay = nodes[a]
        bx, by = nodes[b]
        if ax > bx or (ax == bx and ay > by):
            a, b = b, a
            ax, ay, bx, by = bx, by, ax, ay
        lines_here = seg_lines[key]
        n = len(lines_here)
        for i, (li, rid) in enumerate(lines_here):
            off = (i - (n - 1) / 2) * spacing
            ox1, oy1, ox2, oy2 = _offset(ax, ay, bx, by, off)
            all_lines.append((ox1, oy1, ox2, oy2, rid, a, b))

# Local connections
local_conns = [
    ('Ortisei', 'Seceda'), ('Seceda', 'Resciesa'),
    ('Resciesa', 'Ortisei'), ('Ortisei', 'Bulla'),
    ('Ortisei', 'S. Giacomo'),
    ('S. Cristina', 'Col Raiser'), ('S. Cristina', 'Monte Pana'),
    ('Selva', 'Dantercepies'),
]
for a, b in local_conns:
    ax, ay = nodes[a]
    bx, by = nodes[b]
    all_lines.append((ax, ay, bx, by, 'local', a, b))

# Siusi->Bolzano arrow
sx, sy = nodes['Siusi']
bx, by = nodes['Bolzano']
angle = math.atan2(by - sy, bx - sx)
arr_len = 60
ax2 = sx + arr_len * math.cos(angle)
ay2 = sy + arr_len * math.sin(angle)
all_lines.append((sx, sy, ax2, ay2, 'arrow', 'Siusi', 'Bolzano'))

# Funes Valley stub
fx, fy = nodes['Funes']
all_lines.append((fx, fy, fx + 80, fy, 'funes_stub', 'Funes', 'FunesValley'))

# Compute ALL label positions (current code)
labels = {}
valley_nodes_set = {'Ortisei', 'S. Cristina', 'Selva'}

for place in set(nodes.keys()) - valley_nodes_set:
    x, y = nodes[place]
    label_pos_map = {
        'Seceda':        (x + 10, y + 4, 'start'),
        'Resciesa':      (x - 10, y - 8, 'end'),
        'Bulla':         (x + 12, y + 5, 'start'),
        'Pontives':      (x, y - 20, 'middle'),
        'Ponte Gardena': (x + 12, y + 16, 'start'),
        'Laion':         (x + 12, y - 8, 'start'),
        'Bolzano':       (x + 12, y + 5, 'start'),
        'Chiusa':        (x - 12, y + 14, 'end'),
        'Funes':         (x - 12, y + 14, 'end'),
        'Bressanone':    (x, y - 14, 'middle'),
        'Plan de Gralba': (x - 10, y - 14, 'end'),
        'Passo Gardena':  (x + 10, y + 16, 'start'),
        'Colfosco':      (x + 10, y + 14, 'start'),
        'Passo Sella':   (x - 10, y + 18, 'end'),
        'S. Giacomo':    (x + 10, y + 4, 'start'),
        'Col Raiser':    (x + 10, y - 8, 'start'),
        'Monte Pana':    (x + 10, y + 14, 'start'),
        'Dantercepies':  (x, y - 18, 'middle'),
    }
    if place in label_pos_map:
        lx, ly, anchor = label_pos_map[place]
    elif y > line_y:
        lx, ly, anchor = x + 10, y + 16, 'start'
    else:
        lx, ly, anchor = x + 10, y - 10, 'start'
    labels[place] = (lx, ly, anchor)

# Valley node labels
labels['Ortisei'] = (400, 185 - 22, 'middle')
labels['S. Cristina'] = (530, 185 + 28, 'middle')
labels['Selva'] = (640, 185 + 28, 'middle')

# Funes Valley text labels
labels['_FunesValley'] = (fx + 85, fy - 2, 'start')
labels['_333summer'] = (fx + 85, fy + 10, 'start')
labels['_BolzanoArrow'] = (ax2 + 8, ay2 + 4, 'start')

# Estimate text bounding boxes
char_w = 6.5  # approx char width for bold font-size 10
font_h = 12   # total height including ascenders/descenders

text_widths = {}
for place in labels:
    clean = place.lstrip('_')
    text_widths[place] = len(clean) * char_w

def get_bbox(place):
    lx, ly, anchor = labels[place]
    w = text_widths.get(place, 8 * char_w)
    # SVG text y = baseline. Ascent ~80% of font size, descent ~20%
    top = ly - font_h * 0.75
    bottom = ly + font_h * 0.25
    if anchor == 'start':
        left, right = lx, lx + w
    elif anchor == 'end':
        left, right = lx - w, lx
    else:  # middle
        left, right = lx - w / 2, lx + w / 2
    return left, top, right, bottom

def segments_intersect(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2):
    def cross(ox, oy, ax, ay, bx, by):
        return (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)
    d1 = cross(bx1, by1, bx2, by2, ax1, ay1)
    d2 = cross(bx1, by1, bx2, by2, ax2, ay2)
    d3 = cross(ax1, ay1, ax2, ay2, bx1, by1)
    d4 = cross(ax1, ay1, ax2, ay2, bx2, by2)
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True
    return False

def line_intersects_bbox(x1, y1, x2, y2, left, top, right, bottom, margin=2):
    left -= margin
    top -= margin
    right += margin
    bottom += margin
    if max(x1, x2) < left or min(x1, x2) > right:
        return False
    if max(y1, y2) < top or min(y1, y2) > bottom:
        return False
    def point_in_box(px, py):
        return left <= px <= right and top <= py <= bottom
    if point_in_box(x1, y1) or point_in_box(x2, y2):
        return True
    edges = [
        (left, top, right, top),
        (right, top, right, bottom),
        (right, bottom, left, bottom),
        (left, bottom, left, top),
    ]
    for ex1, ey1, ex2, ey2 in edges:
        if segments_intersect(x1, y1, x2, y2, ex1, ey1, ex2, ey2):
            return True
    return False

print("=" * 80)
print("LABEL vs LINE OVERLAP CHECK (margin=2px)")
print("=" * 80)

any_overlap = False
for place in sorted(labels.keys()):
    bbox = get_bbox(place)
    left, top, right, bottom = bbox
    lx, ly, anchor = labels[place]

    overlaps = []
    for lx1, ly1, lx2, ly2, rid, seg_a, seg_b in all_lines:
        if line_intersects_bbox(lx1, ly1, lx2, ly2, left, top, right, bottom):
            overlaps.append(
                f"    route {rid}: {seg_a}->{seg_b} "
                f"({lx1:.0f},{ly1:.0f})->({lx2:.0f},{ly2:.0f})"
            )

    if overlaps:
        any_overlap = True
        print(f"\n*** {place}: label=({lx:.0f},{ly:.0f},{anchor}) "
              f"bbox=[{left:.0f},{top:.0f}]-[{right:.0f},{bottom:.0f}]")
        for o in overlaps:
            print(o)

if not any_overlap:
    print("\nNo label-line overlaps found!")

print("\n" + "=" * 80)
print("LABEL vs LABEL OVERLAP CHECK")
print("=" * 80)

all_places = sorted(labels.keys())
any_label_overlap = False
for i, p1 in enumerate(all_places):
    b1 = get_bbox(p1)
    for p2 in all_places[i + 1:]:
        b2 = get_bbox(p2)
        if b1[0] < b2[2] and b1[2] > b2[0] and b1[1] < b2[3] and b1[3] > b2[1]:
            any_label_overlap = True
            print(f"  {p1} vs {p2}")
            print(f"    {p1}: [{b1[0]:.0f},{b1[1]:.0f}]-[{b1[2]:.0f},{b1[3]:.0f}]")
            print(f"    {p2}: [{b2[0]:.0f},{b2[1]:.0f}]-[{b2[2]:.0f},{b2[3]:.0f}]")

if not any_label_overlap:
    print("\nNo label-label overlaps found!")
