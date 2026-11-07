"""Loopback-only HTTP, optional SSE, idle socket timeout and enforced total deadline."""
import http.client
import json
import math
import socket
import threading
import time
import urllib.parse


def timeouts(config):
    values = [config.get('connect_timeout_seconds', 10),
              config.get('read_timeout_seconds', config.get('timeout_seconds', 180)),
              config.get('total_timeout_seconds', 900)]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError('連線、閒置讀取與總逾時都必須是有限正數。')
    return values


def read_sse(response, on_delta=None):
    chunks, finish, usage, data_lines = [], None, None, []
    size, content_size = 0, 0
    while True:
        line = response.readline(2 * 1024 * 1024 + 1)
        if not line:
            raise ValueError('串流在 [DONE] 前中斷；預覽不是完整結果。')
        size += len(line)
        if size > 2 * 1024 * 1024:
            raise ValueError('SSE 事件過大或未分隔。')
        line = line.decode('utf-8').rstrip('\r\n')
        if line:
            if line.startswith('data:'):
                data_lines.append(line[5:].removeprefix(' '))
            continue
        size = 0
        if not data_lines:
            continue
        data = '\n'.join(data_lines)
        data_lines = []
        if data == '[DONE]':
            content = ''.join(chunks)
            if finish != 'stop' or not content.strip():
                raise ValueError('串流沒有正常 stop 或沒有文字。')
            return {'choices': [{'finish_reason': finish, 'message': {'content': content}}], 'usage': usage}
        packet = json.loads(data)
        if not isinstance(packet, dict) or packet.get('error'):
            raise ValueError('本地服務回傳串流錯誤。')
        if packet.get('usage') is not None:
            usage = packet['usage']
        choices = packet.get('choices', [])
        if not isinstance(choices, list):
            raise ValueError('串流 choices 格式錯誤。')
        for choice in choices:
            if not isinstance(choice, dict):
                raise ValueError('串流 choice 格式錯誤。')
            if choice.get('index', 0) != 0:
                continue
            delta = choice.get('delta') or {}
            if not isinstance(delta, dict):
                raise ValueError('串流 delta 格式錯誤。')
            text = delta.get('content')
            if text is not None:
                if not isinstance(text, str) or (finish is not None and text):
                    raise ValueError('串流文字格式錯誤或在結束後繼續生成。')
                chunks.append(text)
                content_size += len(text)
                if content_size > 64 * 1024 * 1024:
                    raise ValueError('串流文字過大。')
                if text and on_delta:
                    on_delta(text)
            reason = choice.get('finish_reason')
            if reason is not None:
                if reason != 'stop':
                    raise ValueError('串流未正常結束，可能截斷；不保存為成功。')
                finish = reason


def request(config, route, payload=None, on_delta=None):
    url = urllib.parse.urlsplit(config['base_url'].rstrip('/'))
    if url.scheme != 'http' or url.hostname not in {'127.0.0.1', 'localhost', '::1'} or url.username or url.password or url.query or url.fragment:
        raise ValueError('僅允許本機 HTTP 端點。')
    if not route.startswith('/') or '?' in route or '#' in route:
        raise ValueError('無效的本地 API 路徑。')
    connect, idle, total = timeouts(config)
    expired = threading.Event()
    active_socket = []
    connection = http.client.HTTPConnection(url.hostname, url.port, timeout=min(connect, total))
    deadline = time.monotonic() + total
    def expire():
        expired.set()
        if active_socket:
            try:
                active_socket[0].shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
    timer = threading.Timer(total, expire)
    timer.daemon = True
    timer.start()
    try:
        connection.connect()
        active_socket.append(connection.sock)
        if expired.is_set():
            raise TimeoutError('本地請求超過總時間限制。')
        connection.sock.settimeout(min(idle, max(0.001, deadline - time.monotonic())))
        data = None if payload is None else json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
        connection.request('GET' if payload is None else 'POST', url.path.rstrip('/') + route,
                           body=data, headers={'Content-Type': 'application/json',
                                              'Accept': 'text/event-stream' if payload and payload.get('stream') else 'application/json'})
        response = connection.getresponse()
        with response:
            if response.status != 200:
                raise ValueError(f'本地服務 HTTP {response.status}；不跟隨重新導向或回退其他供應者。')
            if payload and payload.get('stream'):
                if 'text/event-stream' not in response.getheader('Content-Type', '').lower():
                    raise ValueError('服務未提供 SSE；請明確關閉 stream 後再試。')
                value = read_sse(response, on_delta)
            else:
                parts, size = [], 0
                while True:
                    part = response.read1(65536)
                    if not part:
                        break
                    size += len(part)
                    if size > 64 * 1024 * 1024:
                        raise ValueError('本地 JSON 回應過大。')
                    parts.append(part)
                if response.length not in (None, 0):
                    raise ValueError('本地 HTTP 回應未完整接收。')
                value = json.loads(b''.join(parts).decode('utf-8'))
            if expired.is_set() or time.monotonic() >= deadline:
                raise TimeoutError('本地請求超過總時間限制。')
            return value
    except (OSError, ValueError, http.client.HTTPException) as exc:
        if expired.is_set():
            raise TimeoutError('本地請求超過總時間限制；部分預覽不視為成功。') from exc
        if isinstance(exc, socket.timeout):
            raise TimeoutError('本地連線或閒置讀取逾時；部分預覽不視為成功。') from exc
        if isinstance(exc, http.client.HTTPException):
            raise ValueError('本地 HTTP 回應不完整或格式錯誤。') from exc
        raise
    finally:
        timer.cancel()
        connection.close()
