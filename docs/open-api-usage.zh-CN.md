# SQLBot 统一对外 API 调用说明

本文档说明如何调用 SQLBot 新增的统一对外接口：

- `POST /api/v1/open/datasources`
- `POST /api/v1/open/ask`

适用场景：

- 你的业务系统只想接入一个“问数入口”，不想自己维护 `mcp_start -> mcp_question` 的链路。
- 希望复用 SQLBot 现有权限与问答能力。

---

## 1. 基础信息

- 基础地址（示例）：`http://127.0.0.1:8000`
- API 前缀：`/api/v1/open`
- Content-Type：`application/json`

接口文件位置：

- `/Users/cjlee/Desktop/Project/SQLbot/backend/apps/open/api/open_api.py`

---

## 2. 鉴权模型

统一 API 使用两层鉴权，可按需启用：

1. 网关密钥（可选）
2. SQLBot 账号密码（必需，但可配置默认值）

### 2.1 网关密钥（可选）

当你在服务端配置了环境变量 `OPEN_API_KEY` 后，请求必须带 Header：

```http
X-SQLBOT-OPEN-KEY: <你的密钥>
```

未配置 `OPEN_API_KEY` 时，接口不会校验该 Header。

### 2.2 SQLBot 用户身份

接口需要拿到 SQLBot 用户身份，用于数据权限与会话归属判断：

- 方式 A：每次请求 body 传 `username` + `password`
- 方式 B：服务端配置默认账号（推荐）
  - `OPEN_API_USERNAME`
  - `OPEN_API_PASSWORD`

如果两者都没有提供，会返回 `400`。

---

## 3. 环境变量配置

在 SQLBot 服务环境（`.env` 或容器环境变量）中增加：

```env
OPEN_API_KEY=your-open-key
OPEN_API_USERNAME=admin
OPEN_API_PASSWORD=123
```

说明：

- `OPEN_API_KEY` 可空，空则不启用网关密钥校验。
- 建议生产环境一定设置 `OPEN_API_KEY`，并通过 HTTPS 传输。

---

## 4. 接口一：获取可用数据源

### 4.1 请求

- 方法：`POST`
- URL：`/api/v1/open/datasources`

请求体：

```json
{
  "username": "admin",
  "password": "123"
}
```

如果已配置 `OPEN_API_USERNAME/OPEN_API_PASSWORD`，可传空对象：

```json
{}
```

### 4.2 响应

HTTP `200`：

```json
{
  "datasources": [
    {
      "id": 1,
      "name": "Zcgl",
      "type": "mysql",
      "type_name": "MySQL",
      "num": "120/120",
      "status": "Success",
      "oid": 1
    }
  ]
}
```

说明：

- 返回的数据源列表已经按该用户权限过滤。
- `id` 是后续问数时常用的 `datasource_id`。

---

## 5. 接口二：统一问数

### 5.1 请求

- 方法：`POST`
- URL：`/api/v1/open/ask`

请求体字段：

- `question`：必填，用户自然语言问题
- `datasource_id`：选填，数据源 ID（整数或数字字符串）
- `chat_id`：选填，会话 ID。传入后会在该会话内继续提问
- `stream`：选填，默认 `false`
- `username/password`：同前文鉴权说明

示例（非流式）：

```json
{
  "username": "admin",
  "password": "123",
  "question": "查询最近30天订单总额",
  "datasource_id": 1,
  "stream": false
}
```

### 5.2 非流式响应（`stream=false`）

HTTP `200` 或 `500`：

```json
{
  "chat_id": 12,
  "answer": {
    "success": true,
    "record_id": 123,
    "title": "查询最近30天订单总额",
    "message": "...",
    "sql": "...",
    "chart": "...",
    "data": "..."
  }
}
```

说明：

- `chat_id` 用于多轮对话续聊。
- `answer` 为 SQLBot 内核返回对象，字段会随能力演进变化，建议按“取值存在即用”方式解析。

### 5.3 流式响应（`stream=true`）

- 返回 `text/event-stream`
- 响应头附带：`X-SQLBOT-CHAT-ID: <chat_id>`

请求示例：

```bash
curl -N -X POST "http://127.0.0.1:8000/api/v1/open/ask" \
  -H "Content-Type: application/json" \
  -H "X-SQLBOT-OPEN-KEY: your-open-key" \
  -d '{
    "question":"查询最近30天订单总额",
    "datasource_id":1,
    "stream":true
  }'
```

说明：

- 该流式内容与 SQLBot 内核输出一致，建议按“增量文本流”处理，而不是强依赖固定 JSON 事件结构。
- 对于生产系统，如果你希望结果稳定可机读，优先使用 `stream=false`。

---

## 6. 多轮对话（续聊）流程

推荐流程：

1. 第一次调用 `/open/ask` 不传 `chat_id`
2. 从响应里拿到 `chat_id`
3. 后续问题都传同一个 `chat_id`

示例：

第一次：

```json
{
  "question": "本月销售额是多少",
  "datasource_id": 1,
  "stream": false
}
```

后续：

```json
{
  "chat_id": 12,
  "question": "按地区分组",
  "stream": false
}
```

注意：

- `chat_id` 必须属于当前认证用户，否则返回 `404 Chat not found`。

---

## 7. 错误码说明

常见状态码：

- `400`
  - 用户名密码错误
  - 未提供可用账号信息
  - `datasource_id` 非法
- `401`
  - `X-SQLBOT-OPEN-KEY` 校验失败
- `404`
  - `chat_id` 不存在或不属于当前用户
- `500`
  - SQLBot 内部问答执行失败（模型、SQL、数据源或权限导致）

---

## 8. 最小可用示例（Python）

```python
import requests

BASE = "http://127.0.0.1:8000"
HEADERS = {
    "Content-Type": "application/json",
    "X-SQLBOT-OPEN-KEY": "your-open-key",
}

# 1) 查数据源
resp = requests.post(
    f"{BASE}/api/v1/open/datasources",
    headers=HEADERS,
    json={"username": "admin", "password": "123"},
    timeout=30,
)
resp.raise_for_status()
datasources = resp.json()["datasources"]
ds_id = datasources[0]["id"]

# 2) 问第一个问题
resp = requests.post(
    f"{BASE}/api/v1/open/ask",
    headers=HEADERS,
    json={
        "username": "admin",
        "password": "123",
        "question": "查询前5行数据",
        "datasource_id": ds_id,
        "stream": False,
    },
    timeout=120,
)
resp.raise_for_status()
data = resp.json()
chat_id = data["chat_id"]
print("Q1:", data)

# 3) 续聊
resp = requests.post(
    f"{BASE}/api/v1/open/ask",
    headers=HEADERS,
    json={
        "username": "admin",
        "password": "123",
        "chat_id": chat_id,
        "question": "按日期统计",
        "stream": False,
    },
    timeout=120,
)
resp.raise_for_status()
print("Q2:", resp.json())
```

---

## 9. 最小可用示例（Node.js）

```javascript
const base = "http://127.0.0.1:8000";
const headers = {
  "Content-Type": "application/json",
  "X-SQLBOT-OPEN-KEY": "your-open-key",
};

async function post(path, body) {
  const resp = await fetch(`${base}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    throw new Error(`${resp.status} ${await resp.text()}`);
  }
  return await resp.json();
}

async function main() {
  const dsRes = await post("/api/v1/open/datasources", {
    username: "admin",
    password: "123",
  });
  const dsId = dsRes.datasources[0].id;

  const q1 = await post("/api/v1/open/ask", {
    question: "查询前5行数据",
    datasource_id: dsId,
    username: "admin",
    password: "123",
    stream: false,
  });
  console.log("q1", q1);

  const q2 = await post("/api/v1/open/ask", {
    chat_id: q1.chat_id,
    question: "按地区分组",
    username: "admin",
    password: "123",
    stream: false,
  });
  console.log("q2", q2);
}

main().catch(console.error);
```

---

## 10. 生产使用建议

1. 必须开启 `OPEN_API_KEY`，并只走内网或 HTTPS。
2. 不要在前端明文暴露 SQLBot 管理员密码，建议由业务后端代调本接口。
3. 建议给集成系统创建专用 SQLBot 用户，避免使用 `admin`。
4. 对 `/open/ask` 增加网关层限流与超时控制。
5. 建议把 `chat_id` 与你自己业务会话 ID 做映射，方便多轮跟踪。

---

## 11. 变更与兼容性

当前接口基于 SQLBot 内核实时问答结果封装。若后续 SQLBot 内核返回字段增加或精简，`answer` 对象可能变化。建议：

- 只依赖稳定字段（如 `success`、`message`、`sql`、`data`、`chart`、`record_id`）
- 对未知字段做透传和容错解析
