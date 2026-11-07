"""Deterministic checks of explicitly supplied track, via and outline constraints."""
import json
import math
import re

import schema_checks


def parse_board(text):
    stack, roots = [], []
    position = 0
    for match in re.finditer(r'"(?:\\.|[^"\\])*"|[()]|[^\s()"]+', text):
        if text[position:match.start()].strip():
            raise ValueError('PCB 含無法解析的字串。')
        position = match.end()
        token = match.group()
        if token == '(':
            node = []
            (stack[-1] if stack else roots).append(node)
            stack.append(node)
        elif token == ')':
            if not stack:
                raise ValueError('PCB 括號不匹配。')
            stack.pop()
        else:
            if not stack:
                raise ValueError('PCB 根節點外出現內容。')
            stack[-1].append(json.loads(token) if token.startswith('"') else token)
    if text[position:].strip():
        raise ValueError('PCB 結尾含不完整字串。')
    if stack or len(roots) != 1 or not roots[0] or roots[0][0] != 'kicad_pcb':
        raise ValueError('不是完整的 KiCad PCB 內容。')
    return roots[0]


def children(node, name):
    return [item for item in node[1:] if isinstance(item, list) and item and item[0] == name]


def field(node, name):
    values = children(node, name)
    if not values:
        raise ValueError(f'PCB 物件缺少 {name}。')
    return values[0][1:]


def audit(board_path, rules):
    schema_checks.validate_rules(rules)
    per_net = rules.get('per_net_min_width_mm') or {}
    size = rules.get('outline_size_mm')
    if not any(value is not None and value != {} for value in rules.values()):
        return {'status': 'not_run', 'reason': '尚未指定專案幾何門檻。'}
    board = parse_board(board_path.read_text(encoding='utf-8-sig'))
    nets = {str(n[1]): str(n[2]) for n in children(board, 'net')}
    tracks = children(board, 'segment') + children(board, 'arc')
    failures, pending, measurements = [], [], []
    seen_nets = set()
    for index, track in enumerate(tracks):
        width = float(field(track, 'width')[0])
        if not math.isfinite(width) or width <= 0:
            raise ValueError('走線寬度不是有效正數。')
        layer = field(track, 'layer')[0]
        net = nets.get(str(field(track, 'net')[0]), str(field(track, 'net')[0]))
        seen_nets.add(net)
        minimum = per_net.get(net, rules.get('min_track_width_mm'))
        if minimum is not None and width + 1e-9 < minimum:
            failures.append(f'track {index} / {net}: 線寬 {width} < {minimum} mm')
        if rules.get('allowed_track_layers') and layer not in rules['allowed_track_layers']:
            failures.append(f'track {index}: 銅層 {layer} 不允許')
        measurement = {'index': index, 'net': net, 'width_mm': width, 'layer': layer}
        if rules.get('allowed_segment_headings_deg'):
            if track[0] == 'arc':
                pending.append(f'track {index}: 圓弧不能以直線角度門檻自動放行')
            else:
                start, end = field(track, 'start'), field(track, 'end')
                dx, dy = float(end[0]) - float(start[0]), float(end[1]) - float(start[1])
                if not all(math.isfinite(v) for v in (dx, dy)):
                    raise ValueError('走線座標不是有限數值。')
                heading = math.degrees(math.atan2(dy, dx)) % 180
                measurement['heading_deg'] = heading
                if math.hypot(dx, dy) < 1e-9 or not any(abs((heading - h + 90) % 180 - 90) < 1e-6 for h in rules['allowed_segment_headings_deg']):
                    failures.append(f'track {index}: 方向 {heading}° 不符門檻或線段長度為零')
        measurements.append(measurement)
    if not tracks and any(rules.get(k) for k in ('min_track_width_mm', 'per_net_min_width_mm', 'allowed_track_layers', 'allowed_segment_headings_deg')):
        pending.append('沒有走線，無法以空集合通過走線門檻。')
    for net in set(per_net) - seen_nets:
        pending.append(f'{net}: 找不到走線，無法驗證該網路線寬。')
    vias = len(children(board, 'via'))
    if rules.get('max_vias') is not None and vias > rules['max_vias']:
        failures.append(f'過孔數 {vias} 超過 {rules["max_vias"]}')
    measured_size = None
    if size:
        edges = [n for n in board[1:] if isinstance(n, list) and n and n[0].startswith('gr_') and children(n, 'layer') and field(n, 'layer')[0] == 'Edge.Cuts']
        if len(edges) == 1 and edges[0][0] == 'gr_rect':
            start, end = field(edges[0], 'start'), field(edges[0], 'end')
            measured_size = [abs(float(end[i]) - float(start[i])) for i in range(2)]
            if not all(math.isfinite(v) for v in measured_size):
                raise ValueError('板框座標不是有限數值。')
            if any(abs(a - b) > 1e-6 for a, b in zip(measured_size, size)):
                failures.append(f'矩形板框尺寸 {measured_size} 不符 {size} mm')
        else:
            pending.append('板框不是單一 gr_rect；本版不自動判定其尺寸與閉合。')
    return {'status': 'fail' if failures else 'needs_review' if pending else 'pass',
            'failures': failures, 'pending': pending, 'tracks': measurements, 'via_count': vias,
            'rectangular_outline_size_mm': measured_size,
            'scope': '只查指定的線寬、直線方向、走線銅層、過孔數與單一矩形板框尺寸；不查連續轉彎、courtyard、完整實體銅層或 DFM。'}
