# tk-order-sync-nouhinsho-api

Vercel 用纳品书生成 API。它接收纳品书 DOCX 模板和订单 JSON，返回生成好的 DOCX ZIP。

## API

健康检查：

```text
GET /api/nouhinsho/health
```

生成纳品书：

```text
POST /api/nouhinsho/generate
```

表单字段：

- `template`: DOCX 模板文件
- `orders`: JSON 字符串，格式为 `{ "orders": [...] }`
- `issue_date`: 発行日，例如 `2026-06-29`

如果设置了 API 密钥，请在请求头里带：

```text
X-API-Key: your-secret
```

## Vercel 部署

1. 打开 Vercel。
2. 选择 `Add New` → `Project`。
3. 导入 GitHub 仓库 `A1ice17/tk-order-sync-nouhinsho-api`。
4. Framework Preset 选择 `Other` 即可。
5. 添加环境变量：
   - `NOUHINSHO_API_KEY`: 建议设置一串内部共享密钥。
   - `ALLOWED_ORIGINS`: 建议填写 ERP 域名，例如 `https://tk-order-sync.pages.dev`。
   - `NOUHINSHO_MAX_ORDERS`: 默认 `300`。
6. 点击 Deploy。

当前已部署的生产地址：

```text
https://nouhinsho-vercel-api.vercel.app
```

把这个地址填到 ERP “纳品书”页的“生成服务地址”中。如果设置了 `NOUHINSHO_API_KEY`，也把同一个密钥填到“API 密钥”中。

## 本地测试

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install uvicorn
uvicorn app:app --host 127.0.0.1 --port 8502
```

然后在 ERP 中使用：

```text
http://localhost:8502
```
