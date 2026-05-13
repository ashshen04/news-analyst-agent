# Daily Run — Health Check Runbook / 每日运行健康检查手册

How to verify the news-analyst-agent Lambda is actually running and sending
the daily email. / 如何确认 Lambda 每天真的执行并发出了邮件。

## Reference values / 关键参数

- **Lambda function** / 函数名: `news-analyst-agent`
- **Region** / 区域: `us-east-2`
- **Log group** / 日志组: `/aws/lambda/news-analyst-agent`
- **EventBridge schedule** / 定时任务: `daily-news-report` (group: `default`)
- **Cron**: `cron(0 7 * * ? *)` in `America/Toronto` → **07:00 Ontario time, every day** (AWS handles DST automatically) / **每天安省时间 07:00**(夏令时自动处理)

---

## 1. Quick daily check / 每日快速检查

**Goal** / 目的: did today's run succeed? / 今天那一次跑成功了吗?

```bash
aws cloudwatch get-metric-statistics --namespace AWS/Lambda \
  --metric-name Errors --dimensions Name=FunctionName,Value=news-analyst-agent \
  --start-time $(date -u -v-7d +%FT00:00:00Z) --end-time $(date -u +%FT23:59:59Z) \
  --period 86400 --statistics Sum --region us-east-2 \
  --query 'Datapoints[*].[Timestamp,Sum]' --output table

aws cloudwatch get-metric-statistics --namespace AWS/Lambda \
  --metric-name Invocations --dimensions Name=FunctionName,Value=news-analyst-agent \
  --start-time $(date -u -v-7d +%FT00:00:00Z) --end-time $(date -u +%FT23:59:59Z) \
  --period 86400 --statistics Sum --region us-east-2 \
  --query 'Datapoints[*].[Timestamp,Sum]' --output table
```

**Healthy** / 正常:
- Invocations per day = **1** / 每天 1 次调用
- Errors per day = **0** / 0 次报错

**Broken** / 异常:
- Errors == Invocations (e.g. 3 / 3) — every run died and EventBridge retried.
- Errors == Invocations(例如 3 / 3) — 每次都失败,EventBridge 在重试。

---

## 2. Read today's log / 查看今天的日志

**Goal** / 目的: see *why* it failed (or confirm it sent the email). / 看为什么挂了,或确认发邮件成功。

```bash
# Find the most recent log stream
STREAM=$(aws logs describe-log-streams \
  --log-group-name /aws/lambda/news-analyst-agent \
  --region us-east-2 --order-by LastEventTime --descending --max-items 1 \
  --query 'logStreams[0].logStreamName' --output text)

# Dump its events (last 50 lines)
aws logs get-log-events --log-group-name /aws/lambda/news-analyst-agent \
  --log-stream-name "$STREAM" --region us-east-2 \
  --query 'events[*].message' --output text | tail -50
```

**Healthy log markers** / 正常日志会看到:
- `Analyzing: <topic>` for each configured topic / 每个主题都有
- `Done: <topic> in N.Ns` / 每个主题完成
- `Run complete: N/N topics succeeded` / 全部成功
- `REPORT RequestId: ...  Status: success` at the end / 最终成功

**Broken log markers** / 异常日志:
- `Runtime.ExitError`, `terminate called`, `INIT_REPORT ... Status: error`
  → process crashed at init / 进程在 init 阶段就挂了
- `Failed to analyze topic: ...` / 单个主题失败
- `Task timed out after Ns` / 超时

---

## 3. Schedule sanity / 定时器是否启用

**Goal** / 目的: confirm EventBridge will actually fire tomorrow. / 确认明天还会触发。

```bash
aws scheduler get-schedule --name daily-news-report --group-name default \
  --region us-east-2 \
  --query '{State:State,Cron:ScheduleExpression,TZ:ScheduleExpressionTimezone}'
```

**Healthy** / 正常:
```json
{ "State": "ENABLED", "Cron": "cron(0 7 * * ? *)", "TZ": "America/Toronto" }
```

If `State != ENABLED` or the cron/TZ drifted, restore it / 如果异常,恢复成:

```bash
aws scheduler update-schedule --name daily-news-report --group-name default \
  --region us-east-2 --state ENABLED \
  --schedule-expression 'cron(0 7 * * ? *)' \
  --schedule-expression-timezone 'America/Toronto' \
  --flexible-time-window 'Mode=OFF' \
  --target 'Arn=arn:aws:lambda:us-east-2:385697366717:function:news-analyst-agent,RoleArn=arn:aws:iam::385697366717:role/news-agent-scheduler-role,RetryPolicy={MaximumEventAgeInSeconds=86400,MaximumRetryAttempts=185}'
```

---

## 4. End-to-end smoke test / 端到端冒烟测试

**Goal** / 目的: prove the whole pipeline works right now. / 立即验证整条管线。

⚠️ **This sends a real email** to the configured recipients. / **会真的发邮件给配置的收件人**。Only run after a deploy or when you suspect breakage. / 只在部署后或怀疑出问题时跑。

```bash
aws lambda invoke --function-name news-analyst-agent --region us-east-2 \
  --cli-binary-format raw-in-base64-out --payload '{}' /tmp/lambda-out.json
cat /tmp/lambda-out.json
```

**Healthy response** / 正常返回:
```json
{"statusCode": 200, "body": "{\"message\": \"Report sent for N topics\", \"date\": \"YYYY-MM-DD\"}"}
```

**Broken response** / 异常:
- HTTP 200 with `FunctionError: Unhandled` in stderr, **or**
- `/tmp/lambda-out.json` contains `errorType` / `errorMessage` / `stackTrace`.

Then jump back to **§2** to read the log. / 然后回到 §2 看日志定位。

---

## 5. Ground truth / 最终判断

The single most reliable check / 最可靠的检查: **did the daily email arrive in the inbox today?** / **今天收件箱里有没有那封日报?**

- ✅ Email present → everything works. / 收到邮件 → 一切正常。
- ❌ No email by 07:30 Ontario time → run **§1 → §2**. / 安省时间 07:30 还没收到 → 走 §1 → §2 排查。

---

## 6. Deploy / 部署

CI/CD is wired up — pushing to `master` rebuilds the image and updates Lambda. / 推到 `master` 会自动构建镜像并更新 Lambda。

```bash
git push origin master
# Then watch the workflow:
gh run watch
```

Manual deploy (bypass CI) / 手动部署(绕过 CI):

```bash
bash deploy.sh news-analyst-agent
```

After deploy, verify with **§4** + check inbox. / 部署后用 §4 验证,并查看收件箱。
