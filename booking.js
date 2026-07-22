// Vercel Node.js Serverless Function
// 自动服务在 /api/booking

const FEISHU = {
  appId: 'cli_aaeacecbf47a9bc0',
  appSecret: 'UmiNOo8IHbFIb1iLwEaa8gNreIem2nVD',
  baseId: 'QXazbngDbamnwGsMjEbc58TGnDh',
  tableId: 'tblRD66BfFKmKQQl'
};

let cachedToken = null;
let tokenExpire = 0;

async function getToken() {
  if (cachedToken && Date.now() < tokenExpire - 60000) {
    return cachedToken;
  }
  const resp = await fetch('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify({ app_id: FEISHU.appId, app_secret: FEISHU.appSecret })
  });
  const data = await resp.json();
  cachedToken = data.tenant_access_token;
  tokenExpire = Date.now() + (data.expire || 7200) * 1000;
  return cachedToken;
}

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Access-Control-Allow-Methods': 'POST, OPTIONS, GET',
  'Content-Type': 'application/json; charset=utf-8'
};

module.exports = async (req, res) => {
  // CORS
  if (req.method === 'OPTIONS') {
    res.statusCode = 204;
    Object.entries(corsHeaders).forEach(([k, v]) => res.setHeader(k, v));
    return res.end();
  }

  if (req.method === 'GET') {
    Object.entries(corsHeaders).forEach(([k, v]) => res.setHeader(k, v));
    res.statusCode = 200;
    return res.end(JSON.stringify({ status: 'ok' }));
  }

  if (req.method !== 'POST') {
    res.statusCode = 405;
    return res.end(JSON.stringify({ error: 'Method not allowed' }));
  }

  // 读取 POST body
  let body = '';
  for await (const chunk of req) body += chunk;
  let data;
  try {
    data = JSON.parse(body || '{}');
  } catch (e) {
    Object.entries(corsHeaders).forEach(([k, v]) => res.setHeader(k, v));
    res.statusCode = 400;
    return res.end(JSON.stringify({ code: -1, msg: '数据格式错误' }));
  }

  const phone = (data.phone || '').trim();
  const room = (data.roomName || '').trim();
  if (!phone || !room) {
    Object.entries(corsHeaders).forEach(([k, v]) => res.setHeader(k, v));
    res.statusCode = 400;
    return res.end(JSON.stringify({ code: -1, msg: '电话和项目不能为空' }));
  }

  try {
    const token = await getToken();
    const url = `https://open.feishu.cn/open-apis/bitable/v1/apps/${FEISHU.baseId}/tables/${FEISHU.tableId}/records`;
    const writeResp = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json; charset=utf-8'
      },
      body: JSON.stringify({
        fields: {
          '称呼': (data.name || '').trim(),
          '电话': phone,
          '项目': room,
          '日期': (data.date || '').trim(),
          '时间': (data.time || '').trim(),
          '人数': parseInt(data.people, 10) || 0,
          '备注': (data.remark || '').trim()
        }
      })
    });
    const writeData = await writeResp.json();
    if (writeData.code !== 0) {
      Object.entries(corsHeaders).forEach(([k, v]) => res.setHeader(k, v));
      res.statusCode = 500;
      return res.end(JSON.stringify({ code: -1, msg: '飞书写入失败: ' + writeData.msg }));
    }

    Object.entries(corsHeaders).forEach(([k, v]) => res.setHeader(k, v));
    res.statusCode = 200;
    return res.end(JSON.stringify({ code: 0, msg: '预约成功' }));
  } catch (e) {
    Object.entries(corsHeaders).forEach(([k, v]) => res.setHeader(k, v));
    res.statusCode = 500;
    return res.end(JSON.stringify({ code: -1, msg: e.message || String(e) }));
  }
};
