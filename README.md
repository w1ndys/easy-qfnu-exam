# easy-qfnu-exam

qfnu 考试安排自助查询，支持本地爬虫定时同步到 Vercel Redis，并通过公开网页查询。

## Vercel 环境变量

在 Vercel 项目中配置以下环境变量：

- `UPSTASH_REDIS_REST_URL`: Vercel Marketplace Upstash Redis REST URL
- `UPSTASH_REDIS_REST_TOKEN`: Vercel Marketplace Upstash Redis REST Token
- `UPLOAD_SECRET`: upload route secret

## 本地爬虫上传

推荐通过环境变量提供教务 Cookie 和上传密钥，不应提交到仓库，也不应粘贴到共享日志中。`QFNU_JW_COOKIE` 和 `VERCEL_UPLOAD_SECRET` 都是敏感信息。

```bash
export QFNU_JW_COOKIE="JSESSIONID=xxx"
export VERCEL_UPLOAD_URL="https://your-domain.vercel.app/api/upload"
export VERCEL_UPLOAD_SECRET="your-secret"
python3 crawl_exams.py --json-output exams.json --upload
```

当本次爬取没有考试记录时，上传的空数据集会更新线上数据并清空当前可查询记录。

`-c/--cookie` 可用于手动一次性指定教务 Cookie，但不推荐使用，因为命令行中的敏感信息可能出现在 shell 历史记录或进程列表中。

## 查询使用

部署完成后，打开 Vercel 首页，在查询表单中输入教室、课程、周次、星期、时间段等条件，即可查询已同步的考试安排。
