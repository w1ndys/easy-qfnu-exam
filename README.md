# easy-qfnu-exam

qfnu 考试安排自助查询，支持本地爬虫定时同步到 Vercel Redis，并通过公开网页查询。

## Vercel 环境变量

在 Vercel 项目中配置以下环境变量：

- `UPSTASH_REDIS_REST_URL`: Vercel Marketplace Upstash Redis REST URL
- `UPSTASH_REDIS_REST_TOKEN`: Vercel Marketplace Upstash Redis REST Token
- `UPLOAD_SECRET`: upload route secret

## 本地爬虫上传

上传密钥只从环境变量读取，不应提交到仓库，也不应直接写在命令参数中以免留在 shell 历史记录里。

```bash
export VERCEL_UPLOAD_URL="https://your-domain.vercel.app/api/upload"
export VERCEL_UPLOAD_SECRET="your-secret"
python3 crawl_exams.py -c "JSESSIONID=xxx" --json-output exams.json --upload
```

## 查询使用

部署完成后，打开 Vercel 首页，在查询表单中输入教室、课程、周次、星期、时间段等条件，即可查询已同步的考试安排。
