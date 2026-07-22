import json, time, urllib.request

FEISHU_APP_ID = 'cli_aaeacecbf47a9bc0'
FEISHU_APP_SECRET = 'UmiNOo8IHbFIb1iLwEaa8gNreIem2nVD'
BASE_ID = 'QXazbngDbamnwGsMjEbc58TGnDh'
TABLE_ID = 'tblRD66BfFKmKQQl'

_token = None
_token_expire = 0


def get_token():
    global _token, _token_expire
    now = time.time()
    if _token and now < _token_expire - 60:
        return _token
    data = json.dumps({'app_id': FEISHU_APP_ID, 'app_secret': FEISHU_APP_SECRET}).encode()
    req = urllib.request.Request(
        'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
        data=data,
        headers={'Content-Type': 'application/json; charset=utf-8'}
    )
    resp = urllib.request.urlopen(req, timeout=10)
    body = json.loads(resp.read())
    _token = body['tenant_access_token']
    _token_expire = now + body.get('expire', 7200)
    return _token


def write_feishu(data):
    token = get_token()
    body = json.dumps({
        'fields': {
            '称呼': (data.get('name') or '').strip(),
            '电话': (data.get('phone') or '').strip(),
            '项目': (data.get('roomName') or '').strip(),
            '日期': (data.get('date') or '').strip(),
            '时间': (data.get('time') or '').strip(),
            '人数': _to_int(data.get('people')),
            '备注': (data.get('remark') or '').strip()
        }
    }).encode('utf-8')
    url = f'https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_ID}/tables/{TABLE_ID}/records'
    req = urllib.request.Request(url, data=body, headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json; charset=utf-8'
    })
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read())


def _to_int(v):
    try:
        return int(v)
    except (ValueError, TypeError):
        return 0


# Vercel Python Serverless 入口
# 同时支持 Vercel 新版 (BaseHTTPRequestHandler) 和旧版 (request/response)
try:
    # 新版: 继承 BaseHTTPRequestHandler
    from http.server import BaseHTTPRequestHandler

    class handler(BaseHTTPRequestHandler):
        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS, GET')
            self.end_headers()

        def do_POST(self):
            length = int(self.headers.get('Content-Length', 0))
            try:
                body_str = self.rfile.read(length).decode('utf-8')
                data = json.loads(body_str)
            except Exception as e:
                self._respond(400, {'code': -1, 'msg': f'数据格式错误: {e}'})
                return

            self._process(data)

        def do_GET(self):
            self._respond(200, {'status': 'ok'})

        def _process(self, data):
            phone = (data.get('phone') or '').strip()
            room = (data.get('roomName') or '').strip()
            if not phone or not room:
                self._respond(400, {'code': -1, 'msg': '电话和项目不能为空'})
                return
            try:
                write_feishu(data)
                self._respond(200, {'code': 0, 'msg': '预约成功'})
            except Exception as e:
                self._respond(500, {'code': -1, 'msg': str(e)})

        def _respond(self, status, body):
            data = json.dumps(body, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

except ImportError:
    # 旧版: 函数式 handler
    def handler(request, response):
        response.set_header('Access-Control-Allow-Origin', '*')
        if request.method == 'OPTIONS':
            response.status = 204
            return ''
        try:
            data = json.loads(request.body or '{}')
        except Exception:
            response.status = 400
            return json.dumps({'code': -1, 'msg': '数据格式错误'})
        phone = (data.get('phone') or '').strip()
        room = (data.get('roomName') or '').strip()
        if not phone or not room:
            response.status = 400
            return json.dumps({'code': -1, 'msg': '电话和项目不能为空'})
        try:
            write_feishu(data)
            return json.dumps({'code': 0, 'msg': '预约成功'}, ensure_ascii=False)
        except Exception as e:
            response.status = 500
            return json.dumps({'code': -1, 'msg': str(e)}, ensure_ascii=False)
