#!/usr/bin/env python3
"""
考试安排爬取脚本 - 并发版
使用方法: python crawl_exams.py --cookie "你的Cookie" [-w 5] [-o exams.csv]
"""

import requests
import os
import re
import csv
import json
import sys
import time
import argparse
import threading
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

# 禁用警告
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


BASE_URL = "http://zhjw.qfnu.edu.cn"
QUERY_FORM_URL = f"{BASE_URL}/jsxsd/kbxx/jsjy_query"
QUERY_URL = f"{BASE_URL}/jsxsd/kbxx/jsjy_query2"
DETAIL_URL = f"{BASE_URL}/jsxsd/kbxx/jsjy_jszyqk"

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
}

FIELDNAMES = [
    "classroom_name",
    "classroom_id",
    "exam_status",
    "course_name",
    "exam_date",
    "week_info",
    "weekday",
    "time_slot",
    "start_time",
    "end_time",
    "invigilator",
    "week_range",
]

FIELD_LABELS = [
    "教室名称",
    "教室编号",
    "考试状态",
    "课程名称",
    "考试时间",
    "周次-星期节次",
    "星期",
    "节次",
    "开始时间",
    "结束时间",
    "监考人",
    "周次",
]


class ExamRecord:
    def __init__(self):
        self.classroom_name = ""
        self.classroom_id = ""
        self.exam_status = ""
        self.exam_date = ""
        self.week_info = ""
        self.invigilator = ""
        self.course_name = ""
        self.weekday = ""
        self.time_slot = ""
        self.start_time = ""
        self.end_time = ""
        self.week_range = ""

    def to_row(self):
        return [getattr(self, fn, "") for fn in FIELDNAMES]


def record_to_json(rec):
    return {
        "classroomName": rec.classroom_name,
        "classroomId": rec.classroom_id,
        "examStatus": rec.exam_status,
        "courseName": rec.course_name,
        "examTime": rec.exam_date,
        "weekInfo": rec.week_info,
        "weekday": rec.weekday,
        "timeSlot": rec.time_slot,
        "startTime": rec.start_time,
        "endTime": rec.end_time,
        "invigilator": rec.invigilator,
        "week": rec.week_range,
    }


def upload_payload(upload_url, upload_secret, payload):
    headers = {
        "Authorization": f"Bearer {upload_secret}",
        "Content-Type": "application/json; charset=utf-8",
    }
    try:
        resp = requests.post(upload_url, headers=headers, json=payload, timeout=60)
    except requests.RequestException as e:
        print(f"[!] 上传失败: {e}")
        return False

    body = resp.text[:500]
    if resp.status_code >= 400:
        print(f"[!] 上传失败: HTTP {resp.status_code}")
        print(body)
        return False
    print(f"[+] 上传成功: HTTP {resp.status_code}")
    print(body)
    return True


class GridCell:
    def __init__(self):
        self.weekday = 0
        self.tdvalue = ""
        self.kssj = ""
        self.jssj = ""
        self.has_exam = False


class ClassroomInfo:
    def __init__(self):
        self.jsbh = ""
        self.name = ""
        self.cells = []


class ResultWriter:
    """线程安全的结果写入器，支持实时保存"""

    def __init__(self, output_path, fmt="csv"):
        self.output_path = output_path
        self.fmt = fmt
        self.lock = threading.Lock()
        self.count = 0
        self.json_records = []
        self._init_file()

    def _init_file(self):
        if self.fmt == "csv":
            with open(self.output_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(FIELD_LABELS)
        elif self.fmt == "json":
            with open(self.output_path, "w", encoding="utf-8") as f:
                f.write("[\n")

    def write(self, records):
        """追加写入记录"""
        if not records:
            return
        with self.lock:
            for rec in records:
                self.json_records.append(record_to_json(rec))
            if self.fmt == "csv":
                with open(self.output_path, "a", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    for rec in records:
                        writer.writerow(rec.to_row())
                        self.count += 1
            elif self.fmt == "json":
                with open(self.output_path, "a", encoding="utf-8") as f:
                    for i, rec in enumerate(records):
                        if self.count > 0 or i > 0:
                            f.write(",\n")
                        row = {
                            label: getattr(rec, fn, "")
                            for fn, label in zip(FIELDNAMES, FIELD_LABELS)
                        }
                        json.dump(row, f, ensure_ascii=False)
                        self.count += 1

    def finalize(self):
        if self.fmt == "json":
            with open(self.output_path, "a", encoding="utf-8") as f:
                f.write("\n]\n")

    def get_count(self):
        with self.lock:
            return self.count

    def get_json_records(self):
        with self.lock:
            return list(self.json_records)


# 全局速率限制器
class RateLimiter:
    def __init__(self, rate):
        self.rate = rate  # 每秒请求数
        self.lock = threading.Lock()
        self.last = 0

    def wait(self):
        with self.lock:
            now = time.time()
            gap = 1.0 / self.rate
            wait = self.last + gap - now
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()


_limiter = None  # 全局速率限制器


def make_session(cookie_str):
    session = requests.Session()
    session.headers.update(HEADERS)
    if cookie_str:
        session.headers["Cookie"] = cookie_str.strip()
    # 使用 HTTPAdapter 配置连接池
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=5, pool_maxsize=5, max_retries=0
    )
    session.mount("http://", adapter)
    return session


def is_login_page(html):
    return ("登录" in html or "login" in html.lower()) and (
        "Form1" in html or "userAccount" in html or "password" in html.lower()
    )


def get_kbjcmsid(session):
    print("[*] 正在获取查询表单页...")
    try:
        session.get(f"{BASE_URL}/jsxsd/", timeout=15)
    except Exception:
        pass

    resp = session.get(QUERY_FORM_URL, timeout=30)
    resp.encoding = "utf-8"
    html = resp.text

    if is_login_page(html):
        print("[!] Cookie无效或已过期，服务器返回了登录页面")
        return None

    for pattern in [
        r'name="kbjcmsid"[^>]*value="([^"]+)"',
        r'id="kbjcmsid"[^>]*value="([^"]+)"',
    ]:
        match = re.search(pattern, html)
        if match:
            kbjcmsid = match.group(1)
            print(f"[+] kbjcmsid: {kbjcmsid}")
            return kbjcmsid

    print("[!] 未找到kbjcmsid，使用空值尝试...")
    return ""


def parse_grid_html(html):
    jc_cells = {}
    jc_pattern = re.findall(
        r'<td[^>]*id="jc(\d+)"[^>]*tdvalue="([^"]*)"[^>]*tdKssj="([^"]*)"[^>]*tdJssj="([^"]*)"[^>]*>',
        html,
    )
    for jc_id, tdvalue, kssj, jssj in jc_pattern:
        jc_cells[int(jc_id)] = {"tdvalue": tdvalue, "kssj": kssj, "jssj": jssj}
    print(f"[+] 找到 {len(jc_cells)} 个时间槽定义")

    table_match = re.search(
        r'<table[^>]*name="kbDataTable"[^>]*>(.*?)</table>', html, re.DOTALL
    )
    if not table_match:
        print("[!] 未找到教室数据表")
        return [], jc_cells

    table_html = table_match.group(1)
    classrooms = []

    for tr_match in re.finditer(
        r'<tr[^>]*jsbh="([^"]+)"[^>]*>(.*?)</tr>', table_html, re.DOTALL
    ):
        jsbh = tr_match.group(1)
        row_html = tr_match.group(2)

        name_match = re.search(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
        if not name_match:
            continue

        name_clean = re.sub(r"<[^>]+>", "", name_match.group(1)).strip()
        name_clean = re.sub(r"\s+", "", name_clean)
        if not name_clean:
            continue

        cinfo = ClassroomInfo()
        cinfo.jsbh = jsbh
        cinfo.name = name_clean

        for ci, cell_match in enumerate(
            re.finditer(
                r'<td[^>]*ondblclick="clickTd\(this\)"[^>]*>(.*?)</td>',
                row_html,
                re.DOTALL,
            )
        ):
            cell_content = cell_match.group(1)
            gcell = GridCell()
            gcell.has_exam = "font color" in cell_content or "考试" in cell_content
            gcell.weekday = ci // 5 + 1
            jc_id = ci
            if jc_id in jc_cells:
                gcell.tdvalue = jc_cells[jc_id]["tdvalue"]
                gcell.kssj = jc_cells[jc_id]["kssj"]
                gcell.jssj = jc_cells[jc_id]["jssj"]
            cinfo.cells.append(gcell)

        classrooms.append(cinfo)

    print(f"[+] 找到 {len(classrooms)} 个教室")
    return classrooms, jc_cells


def _extract_field(html, label):
    """提取表格中的字段值：标签在第一个td，值在第三个td"""
    pattern = (
        re.escape(label) + r"\s*</td>\s*<td[^>]*>\s*</td>\s*<td[^>]*>\s*(.*?)\s*</td>"
    )
    m = re.search(pattern, html, re.DOTALL)
    if m:
        return re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return ""


def parse_detail_html(html, cinfo, gcell):
    if not html:
        return []

    records = []

    # 每个考试记录以"教室状态："开头，提取每个记录块
    # 用教室状态作为锚点分割
    blocks = re.split(r"(教室状态：)", html)

    for i in range(1, len(blocks) - 1, 2):
        label = blocks[i]  # "教室状态："
        chunk = blocks[i + 1]  # 后续内容直到下一个"教室状态："或结束
        block = label + chunk

        # 找到这个block的结束位置（下一个</table>之后的</table>，即外层table结束）
        # 简化：提取到下一个教室状态或form结束
        rec = ExamRecord()
        rec.classroom_id = cinfo.jsbh

        rec.exam_status = _extract_field(block, "教室状态：")
        rec.classroom_name = _extract_field(block, "教室：")
        rec.exam_date = _extract_field(block, "时间：")
        rec.week_info = _extract_field(block, "周次-星期节次：")
        rec.invigilator = _extract_field(block, "监 考 人：")
        rec.course_name = _extract_field(block, "课程：")

        rec.weekday = str(gcell.weekday)
        rec.time_slot = gcell.tdvalue
        rec.start_time = gcell.kssj
        rec.end_time = gcell.jssj

        if rec.week_info:
            week_match = re.match(r"(\d+)-", rec.week_info)
            if week_match:
                rec.week_range = week_match.group(1)

        if rec.exam_status or rec.course_name or rec.exam_date:
            records.append(rec)

    return records


def fetch_detail(
    session,
    jsbh,
    kcsj,
    xnxqh,
    start_zc,
    end_zc,
    start_xq,
    end_xq,
    jszt,
    kbjcmsid,
    xq,
    kssj,
    jssj,
    retries=2,
):
    """获取详情页，支持重试和速率限制"""
    global _limiter
    params = {
        "xnxqh": xnxqh,
        "jsbh": jsbh,
        "kcsj": kcsj,
        "typewhere": "jszq",
        "startZc": start_zc,
        "endZc": end_zc,
        "startJc": "",
        "endJc": "",
        "startXq": start_xq,
        "endXq": end_xq,
        "jszt": jszt,
        "type": "add",
        "kbjcmsid": kbjcmsid,
        "xq": xq,
        "kssj": kssj,
        "jssj": jssj,
        "tktime": str(int(time.time() * 1000)),
    }
    for attempt in range(retries + 1):
        if _limiter:
            _limiter.wait()
        try:
            resp = session.get(DETAIL_URL, params=params, timeout=15)
            resp.encoding = "utf-8"
            return resp.status_code, resp.text
        except Exception as e:
            if attempt < retries:
                time.sleep(1 * (attempt + 1))
            else:
                return 0, str(e)
    return 0, ""


def process_task(
    task,
    session,
    xnxqh,
    start_zc,
    end_zc,
    start_xq,
    end_xq,
    jszt,
    kbjcmsid,
    writer,
    stats,
    verbose,
):
    """处理单个考试单元格的任务，返回 (cell_index, records_count, status_code, error)"""
    idx, total, cinfo, gcell = task
    kcsj = str(gcell.weekday) + gcell.tdvalue
    xq = gcell.weekday

    status, html = fetch_detail(
        session,
        cinfo.jsbh,
        kcsj,
        xnxqh,
        start_zc,
        end_zc,
        start_xq,
        end_xq,
        jszt,
        kbjcmsid,
        xq,
        gcell.kssj,
        gcell.jssj,
    )

    if status == 200:
        records = parse_detail_html(html, cinfo, gcell)
        if records:
            writer.write(records)
            with stats["lock"]:
                stats["ok"] += 1
                stats["records"] += len(records)
            if verbose:
                for r in records:
                    print(
                        f"  [{stats['records']}] {r.course_name or '?'} | "
                        f"{r.exam_date or r.week_info} | {r.classroom_name or cinfo.name}"
                    )
            return idx, len(records), 200, ""
        else:
            with stats["lock"]:
                stats["empty"] += 1
            if verbose:
                print(
                    f"  [{idx}/{total}] {cinfo.name} 星期{gcell.weekday} "
                    f"{gcell.kssj}-{gcell.jssj} -> 无记录"
                )
            return idx, 0, 200, "empty"
    else:
        with stats["lock"]:
            stats["fail"] += 1
        err_msg = html if isinstance(html, str) else str(status)
        if verbose:
            print(
                f"  [{idx}/{total}] {cinfo.name} 星期{gcell.weekday} "
                f"{gcell.kssj}-{gcell.jssj} -> HTTP {status} {err_msg[:80]}"
            )
        return idx, 0, status, err_msg


def build_payload(args, records):
    return {
        "source": "local-cron",
        "semester": args.semester,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "records": records,
    }


def crawl(args):
    session = make_session(args.cookie)
    xnxqh, start_zc, end_zc = args.semester, args.start_week, args.end_week
    start_xq, end_xq, jszt = args.start_xq, args.end_xq, args.jszt

    # 1. 获取kbjcmsid
    kbjcmsid = get_kbjcmsid(session)
    if kbjcmsid is None:
        print("[!] Cookie无效，无法继续")
        return 1

    # 2. POST查询教室状态
    print(f"[*] 正在查询教室状态 (第{start_zc}-{end_zc}周)...")
    post_data = {
        "typewhere": "jszq",
        "xnxqh": xnxqh,
        "gnq_mh": "",
        "jsmc_mh": "",
        "syjs0601id": "",
        "xqbh": "",
        "jxqbh": "",
        "jslx": "",
        "jxlbh": "",
        "jsbh": "",
        "bjfh": "%3D",
        "rnrs": "",
        "jszt": jszt,
        "zc": start_zc,
        "zc2": end_zc,
        "xq": "",
        "xq2": "",
        "jc": "",
        "jc2": "",
        "kbjcmsid": kbjcmsid,
        "ssdw": "",
    }

    resp = session.post(
        QUERY_URL,
        data=post_data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": QUERY_FORM_URL,
            "Origin": BASE_URL,
        },
        timeout=60,
    )
    resp.encoding = "utf-8"
    grid_html = resp.text
    print(f"[+] 查询响应: {len(grid_html)} bytes")

    if is_login_page(grid_html):
        print("[!] Cookie无效，服务器返回了登录页面")
        return 1

    # 3. 解析教室网格
    classrooms, jc_cells = parse_grid_html(grid_html)
    if not classrooms:
        print("[!] 未找到教室数据")
        return 1

    # 4. 收集所有考试单元格
    exam_tasks = []
    for cinfo in classrooms:
        for gcell in cinfo.cells:
            if gcell.has_exam:
                exam_tasks.append((cinfo, gcell))

    total_cells = sum(len(c.cells) for c in classrooms)
    print(
        f"[+] {len(classrooms)} 教室, {total_cells} 时间槽, "
        f"{len(exam_tasks)} 个考试标记"
    )
    print(f"[*] 并发数: {args.workers}, 开始获取详情...")

    if not exam_tasks:
        print("[!] 没有找到考试安排")
        return 0

    # 5. 并发获取详情 + 实时保存
    writer = ResultWriter(args.output, args.format)

    # 设置全局速率限制
    global _limiter
    _limiter = RateLimiter(args.rate)

    stats = {
        "lock": threading.Lock(),
        "ok": 0,  # 有记录的单元格
        "empty": 0,  # 有考试标记但详情无记录
        "fail": 0,  # HTTP请求失败
        "records": 0,  # 总记录数
    }

    tasks = [
        (i, len(exam_tasks), cinfo, gcell)
        for i, (cinfo, gcell) in enumerate(exam_tasks, 1)
    ]

    # 线程本地 session
    thread_local = threading.local()

    def get_thread_session():
        if not hasattr(thread_local, "session"):
            thread_local.session = make_session(args.cookie)
        return thread_local.session

    def task_wrapper(task):
        session = get_thread_session()
        return process_task(
            task,
            session,
            xnxqh,
            start_zc,
            end_zc,
            start_xq,
            end_xq,
            jszt,
            kbjcmsid,
            writer,
            stats,
            args.verbose,
        )

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(task_wrapper, t): t for t in tasks}

        for f in as_completed(futures):
            task = futures[f]
            idx = task[0]
            try:
                f.result()
            except Exception as e:
                with stats["lock"]:
                    stats["fail"] += 1
                print(f"  [!] 任务 {idx} 异常: {e}")

            if not args.verbose:
                done = stats["ok"] + stats["empty"] + stats["fail"]
                if done % 100 == 0 or done == len(exam_tasks):
                    print(
                        f"  进度: {done}/{len(exam_tasks)} "
                        f"({done * 100 // len(exam_tasks)}%), "
                        f"成功={stats['ok']}, 空={stats['empty']}, "
                        f"失败={stats['fail']}, 记录={stats['records']}"
                    )

    writer.finalize()
    if stats["fail"] > 0:
        print(
            f"[!] 存在 {stats['fail']} 个失败任务，跳过JSON输出和上传，避免发布不完整数据"
        )
        return 1

    payload = build_payload(args, writer.get_json_records())

    if args.json_output:
        with open(args.json_output, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"[+] JSON结果已保存到: {args.json_output}")

    if args.upload_url or args.upload:
        upload_url = args.upload_url or os.getenv("VERCEL_UPLOAD_URL")
        upload_secret = os.getenv("VERCEL_UPLOAD_SECRET")
        if not upload_url or not upload_secret:
            print("[!] 上传失败: 缺少 VERCEL_UPLOAD_URL 或 VERCEL_UPLOAD_SECRET")
            return 1
        if not upload_payload(upload_url, upload_secret, payload):
            return 1

    print(
        f"\n[+] 完成! 单元格: {stats['ok']}+{stats['empty']}+{stats['fail']} "
        f"(有记录+空+失败) = {len(exam_tasks)}"
    )
    print(f"[+] 共爬取 {stats['records']} 条考试记录")
    print(f"[+] 结果已保存到: {args.output}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="曲阜师范大学教务系统 - 考试安排爬取脚本 (并发版)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python crawl_exams.py -c "JSESSIONID=xxx"
  python crawl_exams.py -c "xxx" -s 2025-2026-2 --start-week 19 --end-week 20
  python crawl_exams.py -c "xxx" -o exams.json -f json -w 20
  python crawl_exams.py -c "xxx" -v -w 10
        """,
    )
    parser.add_argument("--cookie", "-c", required=True, help="登录后的Cookie字符串")
    parser.add_argument(
        "--semester", "-s", default="2025-2026-2", help="学年学期 (默认: 2025-2026-2)"
    )
    parser.add_argument(
        "--start-week", type=str, default="19", help="开始周次 (默认: 19)"
    )
    parser.add_argument(
        "--end-week", type=str, default="20", help="结束周次 (默认: 20)"
    )
    parser.add_argument("--start-xq", type=str, default="1", help="开始星期 (默认: 1)")
    parser.add_argument("--end-xq", type=str, default="7", help="结束星期 (默认: 7)")
    parser.add_argument(
        "--jszt", type=str, default="4", help="教室状态类型 (默认: 4=考试)"
    )
    parser.add_argument(
        "--output", "-o", default="exams.csv", help="输出文件路径 (默认: exams.csv)"
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["csv", "json", "text"],
        default="csv",
        help="输出格式 (默认: csv)",
    )
    parser.add_argument(
        "--workers", "-w", type=int, default=5, help="并发线程数 (默认: 5, 建议 3-10)"
    )
    parser.add_argument(
        "--rate", "-r", type=float, default=10.0, help="每秒最大请求数 (默认: 10)"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="显示每条记录详情")
    parser.add_argument("--json-output", default="", help="输出JSON上传载荷路径 (可选)")
    parser.add_argument(
        "--upload", action="store_true", help="爬取完成后上传到Vercel接口"
    )
    parser.add_argument(
        "--upload-url", default="", help="Vercel上传接口URL，默认读取VERCEL_UPLOAD_URL"
    )

    args = parser.parse_args()
    print("=" * 60)
    print("曲阜师范大学教务系统 - 考试安排爬取 (并发版)")
    print("=" * 60)
    print(f"学期: {args.semester}, 周次: {args.start_week}-{args.end_week}")
    print(
        f"并发: {args.workers} 线程, 速率: {args.rate} req/s, 输出: {args.output} ({args.format})"
    )
    print()

    return crawl(args)


if __name__ == "__main__":
    sys.exit(main())
