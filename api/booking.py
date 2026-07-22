import json, time, urllib.request, ssl

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
    body = {
        'fields': {
            '称呼': (data.get('name') or '').strip(),
            '电话': (data.get('phone') or '').strip(),
            '项目': (data.get('roomName') or '').strip(),
            '日期': (data.get('date') or '').strip(),
            '时间': (data.get('time') or '').strip(),
            '人数': _to_int(data.get('people')),
            '备注': (data.get('remark') or '').strip()
        }
    }
    url = f'https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_ID}/tables/{TABLE_ID}/records'
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json; charset=utf-8'
        }
    )
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read())


def _to_int(v):
    try:
        return int(v)
    except (ValueError, TypeError):
        return 0


class Handler:
    """Vercel Python Serverless 入口"""

    def __init__(self):
        pass

    def __call__(self, request, response):
        return self.handler(request, response)

    def handler(self, request, response):
        # CORS
        response.headers.update({
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'POST, OPTIONS'
        })

        if request.method == 'OPTIONS':
            response.status = 204
            response.body = ''
            return response

        try:
            body = json.loads(request.body.decode('utf-8'))
        except Exception:
            response.status = 400
            response.body = json.dumps({'code': -1, 'msg': '数据格式错误'})
            return response

        phone = (body.get('phone') or '').strip()
        room = (body.get('roomName') or '').strip()
        if not phone or not room:
            response.status = 400
            response.body = json.dumps({'code': -1, 'msg': '电话和项目不能为空'})
            return response

        try:
            write_feishu(body)
            response.status = 200
            response.body = json.dumps({'code': 0, 'msg': '预约成功'}, ensure_ascii=False)
        except Exception as e:
            response.status = 500
            response.body = json.dumps({'code': -1, 'msg': str(e)}, ensure_ascii=False)

        return response


# Vercel 自动查找并注册 handler
handler = Handler()
