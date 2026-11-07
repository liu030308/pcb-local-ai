import contextlib
import io
import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import local_http


def event(text=None,reason=None):
    delta={} if text is None else {'content':text}
    return ('data: '+json.dumps({'choices':[{'index':0,'delta':delta,'finish_reason':reason}]},ensure_ascii=False)+'\n\n').encode('utf-8')


class SSETests(unittest.TestCase):
    def test_unicode_heartbeat_and_complete_response(self):
        preview=[]
        data=b': heartbeat\n\n'+event('繁體')+event('中文')+event(reason='stop')+b'data: [DONE]\n\n'
        result=local_http.read_sse(io.BytesIO(data),preview.append)
        self.assertEqual(result['choices'][0]['message']['content'],'繁體中文')
        self.assertEqual(preview,['繁體','中文'])

    def test_missing_done_missing_stop_and_truncation_are_rejected(self):
        for data in [event('partial'),event('partial')+event(reason='stop'),
                     event('partial')+b'data: [DONE]\n\n',event('partial',reason='length')]:
            with self.subTest(data=data),self.assertRaises(ValueError):
                local_http.read_sse(io.BytesIO(data))

    def test_error_packet_and_content_after_stop_are_rejected(self):
        for data in [b'data: {"error":{"message":"bad"}}\n\n',
                     event('partial')+event(reason='stop')+event('extra')]:
            with self.subTest(data=data),self.assertRaises(ValueError):
                local_http.read_sse(io.BytesIO(data))

    def test_multiline_data_and_usage_event(self):
        data=b'data: {"choices":\ndata: [{"index":0,"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\n'
        data+=b'data: {"choices":[],"usage":{"completion_tokens":1}}\n\ndata: [DONE]\n\n'
        self.assertEqual(local_http.read_sse(io.BytesIO(data))['usage']['completion_tokens'],1)

    def test_invalid_timeouts_are_rejected(self):
        for value in [0,-1,True,float('nan')]:
            with self.subTest(value=value),self.assertRaises(ValueError):
                local_http.timeouts({'total_timeout_seconds':value})


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def do_GET(self):
        if self.path.endswith('/models'):
            body=b'{"data":[{"id":"local"}]}'
            self.send_response(200)
            self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path=='/redirect':
            self.send_response(302)
            self.send_header('Location','https://example.com/')
            self.end_headers()
        else:
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length','100')
            self.end_headers()
            self.wfile.write(b'{}')

    def do_POST(self):
        payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.send_response(200)
        self.send_header('Content-Type','application/json' if self.path=='/wrong-type' else 'text/event-stream')
        self.end_headers()
        try:
            if self.path=='/idle':
                self.wfile.flush()
                time.sleep(0.5)
            elif self.path=='/slow':
                for _ in range(20):
                    self.wfile.write(b': heartbeat\n\n')
                    self.wfile.flush()
                    time.sleep(0.05)
            self.wfile.write(event('草稿'))
            if not self.path.startswith('/broken'):
                self.wfile.write(event(reason='stop')+b'data: [DONE]\n\n')
            self.wfile.flush()
        except (OSError,ConnectionError):
            pass


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base='http://127.0.0.1:'+str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def config(self,**extra):
        return dict({'base_url':self.base,'connect_timeout_seconds':2,
                     'read_timeout_seconds':2,'total_timeout_seconds':5},**extra)

    def test_plain_json_and_real_stream(self):
        self.assertEqual(local_http.request(self.config(),'/models')['data'][0]['id'],'local')
        result=local_http.request(self.config(),'/chat/completions',{'stream':True})
        self.assertEqual(result['choices'][0]['message']['content'],'草稿')

    def test_idle_timeout_and_total_deadline_are_separate(self):
        start=time.monotonic()
        with self.assertRaises(TimeoutError):
            local_http.request(self.config(read_timeout_seconds=0.1),'/idle',{'stream':True})
        self.assertLess(time.monotonic()-start,2)
        start=time.monotonic()
        with self.assertRaises(TimeoutError):
            local_http.request(self.config(total_timeout_seconds=0.3),'/slow',{'stream':True})
        self.assertLess(time.monotonic()-start,2)

    def test_redirect_incomplete_body_and_wrong_stream_type_are_rejected(self):
        for route,payload in [('/redirect',None),('/truncated',None),('/wrong-type',{'stream':True})]:
            with self.subTest(route=route),self.assertRaises(ValueError):
                local_http.request(self.config(),route,payload)

    def test_remote_endpoint_is_rejected_before_connection(self):
        with patch.object(local_http.http.client,'HTTPConnection') as connection:
            with self.assertRaises(ValueError):
                local_http.request({'base_url':'https://example.com'},'/models')
            connection.assert_not_called()

    def test_cli_stream_keeps_stdout_json_and_does_not_save_partial_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            config,task,output=root/'config.json',root/'task.txt',root/'result.json'
            task.write_text('task')
            script=Path(__file__).resolve().parent/'local_worker.py'
            command=[sys.executable,'-B',str(script),'work','--config',str(config),'--task-file',str(task),'--output',str(output),'--stream']
            config.write_text(json.dumps(dict(self.config(),model='local',routine_work_provider='local')))
            result=subprocess.run(command,text=True,capture_output=True,encoding='utf-8',timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['content'],'草稿')
            self.assertIn('草稿',result.stderr)
            output.unlink()
            config.write_text(json.dumps(dict(self.config(),base_url=self.base+'/broken',model='local')))
            result=subprocess.run(command,text=True,capture_output=True,encoding='utf-8',timeout=10)
            self.assertEqual(result.returncode,1)
            self.assertFalse(output.exists())


if __name__=='__main__':
    unittest.main()
