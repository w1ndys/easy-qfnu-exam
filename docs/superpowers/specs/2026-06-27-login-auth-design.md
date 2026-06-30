# 登录认证改造设计：账号密码登录 + ddddocr + uv

日期：2026-06-27

## 背景

当前 `crawl_exams.py` 依赖调用者提供已登录的教务系统 Cookie。这个方式不利于长期定时同步：Cookie 容易过期，且手动复制 Cookie 容易泄露敏感信息。参考 GitHub issue `w1ndys/qfnu-courses-grabber-solo#1` 中的强智教务系统登录接口文档，本次改造将爬虫认证流程改为脚本自行登录。

用户已确认采用方案 A：本地 `ddddocr` 自动识别验证码，使用 `uv` 管理 Python 虚拟环境，账号密码通过环境变量提供，并移除直接 Cookie 使用入口。

## 目标

1. 爬虫不再接受或读取教务 Cookie。
2. 爬虫启动时使用账号密码登录强智教务系统。
3. 验证码使用本地 `ddddocr` 自动识别。
4. Python 依赖由 `uv` 管理。
5. 登录成功后复用同一会话状态完成考试安排爬取、JSON 输出和上传。
6. 通过自动化测试覆盖登录流程、凭证加密和旧 Cookie 入口移除。

## 非目标

1. 不在本次改造中提供浏览器交互登录。
2. 不实现外部 `OCR_URL` 服务调用。
3. 不在 Vercel 端保存教务账号密码。
4. 不改动前端查询页面或 Redis 数据结构。

## 外部接口依据

基础域名：`http://zhjw.qfnu.edu.cn`

登录流程来自 issue 文档：

1. `GET /` 初始化会话并获取初始 Cookie。
2. `GET /verifycode.servlet` 获取验证码图片。
3. `POST /Logon.do?method=logon&flag=sess` 获取 `scode#sxh`。
4. 构造 `encoded` 登录凭证。
5. `POST /Logon.do?method=logonLdap` 提交登录。
6. `GET /framework/main.jsp` 验证登录状态。

## 配置与运行方式

新增 `pyproject.toml`，由 `uv` 管理 Python 依赖。

主要依赖：

- `requests`
- `ddddocr`

运行方式：

```bash
uv sync
export QFNU_JW_USERNAME="学号"
export QFNU_JW_PASSWORD="密码"
export VERCEL_UPLOAD_URL="https://your-domain.vercel.app/api/upload"
export VERCEL_UPLOAD_SECRET="your-secret"
uv run python crawl_exams.py --json-output exams.json --upload
```

脚本不再支持：

- `QFNU_JW_COOKIE`
- `--cookie`
- `--cookie-env`

缺少 `QFNU_JW_USERNAME` 或 `QFNU_JW_PASSWORD` 时，脚本退出并给出明确提示。

## 模块设计

`crawl_exams.py` 保持单文件结构，但将登录逻辑拆成可测试的小函数。

### 会话创建

`make_session()` 只负责创建 `requests.Session`、设置通用 headers 和连接池，不再接收 Cookie 字符串。

### 凭证加密

新增：

```python
def encode_credentials(username, password, scode, sxh):
    ...
```

算法：

1. 明文为 `username + "%%%" + password`。
2. 只对前 20 个字符做插入处理。
3. 对第 `i` 个字符，读取 `sxh[i]` 对应数字 `n`。
4. 从 `scode` 当前偏移截取 `n` 个字符，插入到当前字符之后。
5. 第 20 个字符之后原样追加。

### 验证码识别

新增：

```python
def fetch_captcha(session):
    ...

def solve_captcha(image_bytes):
    ...
```

`fetch_captcha` 请求 `/verifycode.servlet`，响应体为空时视为失败。

`solve_captcha` 使用本地 `ddddocr.DdddOcr(show_ad=False)` 识别验证码。识别结果会去除空白字符；结果为空视为失败。

### 登录会话参数

新增：

```python
def fetch_login_sess(session):
    ...
```

请求 `/Logon.do?method=logon&flag=sess`。响应必须是 `scode#sxh` 格式。空响应、`no` 或缺少 `#` 视为失败。

### 登录提交

新增：

```python
def submit_login(session, username, password, captcha, scode, sxh):
    ...
```

提交表单：

- `userAccount=` 留空
- `userPassword=` 留空
- `RANDOMCODE=<验证码>`
- `encoded=<加密凭证>`

响应判定：

- 包含账号密码错误文案：返回账号密码错误，终止登录。
- 包含验证码错误文案：返回验证码错误，允许重新识别并重试。
- body 为空，或包含 `正在登录`、`location`、`教学一体化服务平台`：视为提交成功。
- 其他响应：返回未知登录错误。

### 登录状态验证

新增：

```python
def verify_login(session):
    ...
```

请求 `/framework/main.jsp`，不自动跟随重定向。HTTP 301/302 视为未登录；HTTP 非 200 视为失败；响应体必须包含 `教学一体化服务平台` 或 `glyphicon-class`。

### 登录总控

新增：

```python
def login(session, username, password):
    ...
```

行为：

1. 初始化会话。
2. 最多尝试 3 轮验证码。
3. 每轮获取验证码、识别验证码、获取 `scode/sxh`、提交登录。
4. 验证码错误时继续下一轮。
5. 账号密码错误时立即终止。
6. 提交成功后最多验证登录状态 2 次。
7. 登录成功返回 `True`，失败返回 `False`。

## 爬虫流程调整

主流程从：

```text
读取 Cookie → make_session(cookie) → crawl(args)
```

改为：

```text
读取 QFNU_JW_USERNAME / QFNU_JW_PASSWORD → make_session() → login(session, username, password) → crawl(args, session)
```

`crawl` 接收已经登录的主 session。获取 `kbjcmsid`、查询教室网格使用主 session。

并发详情请求继续使用每线程一个 session，但不重新登录。实现方式：

1. 登录成功后保留主 session 的 cookie jar。
2. 每个线程创建 session。
3. 将主 session 的 cookies 复制到线程 session。
4. 线程 session 调用详情接口。

这样避免共享同一个 session 的线程安全问题，也避免每个线程重复登录。

## 错误处理

- 缺少账号密码：退出码 1，提示设置 `QFNU_JW_USERNAME` / `QFNU_JW_PASSWORD`。
- 缺少 `ddddocr`：退出码 1，提示执行 `uv sync`。
- 验证码图片为空：当前登录轮失败，进入下一轮。
- OCR 结果为空：当前登录轮失败，进入下一轮。
- 验证码错误：进入下一轮，最多 3 次。
- 账号密码错误：立即退出，不继续重试。
- 登录状态验证失败：退出，不开始爬取。
- 爬取过程中返回登录页：保留现有检测，提示会话失效或登录失败。
- 详情任务失败时：保留现有行为，跳过 JSON 输出和上传，避免发布不完整数据。

## 测试设计

采用 TDD。每个行为先写失败测试，再写最小实现。

需要新增或调整 Python 测试：

1. `encode_credentials` 按 `scode/sxh` 插入规则生成 encoded。
2. `solve_captcha` 去除 OCR 结果空白。
3. `fetch_login_sess` 拒绝空响应、`no` 和缺少 `#` 的响应。
4. `login` 在验证码错误后重试。
5. `login` 遇到账号密码错误时不重试。
6. `main` 缺少账号密码时退出并提示新环境变量。
7. `main` 从 `QFNU_JW_USERNAME` / `QFNU_JW_PASSWORD` 读取凭证。
8. help 文案不再出现 `QFNU_JW_COOKIE`、`--cookie` 或 `--cookie-env`。
9. `crawl` 使用已登录 session，不再调用 `make_session(args.cookie)`。
10. 线程 session 从已登录主 session 复制 cookies。

现有上传安全测试继续保留，确保登录改造不影响 JSON 输出和 Vercel 上传逻辑。

## 文档更新

README 更新为账号密码登录方式，删除 Cookie 推荐和 `--cookie` 说明。

需要说明：

- `QFNU_JW_USERNAME`、`QFNU_JW_PASSWORD`、`VERCEL_UPLOAD_SECRET` 都是敏感信息。
- 推荐使用环境变量，不要提交到仓库或粘贴到共享日志。
- 使用 `uv sync` 安装 Python 环境。
- 使用 `uv run python crawl_exams.py ...` 运行爬虫。

## 验收标准

1. `python3 -m unittest test_crawl_exams_upload.py` 通过。
2. 新增登录相关 Python 测试通过。
3. `npm test` 和 `npm run typecheck` 仍通过。
4. README 不再指导用户直接使用 Cookie。
5. `crawl_exams.py --help` 不再展示 Cookie 参数。
6. 在模拟登录成功的测试中，爬虫能使用登录后的 session 继续执行现有查询流程。
