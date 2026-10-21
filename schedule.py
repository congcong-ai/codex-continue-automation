#!/usr/bin/env python3
"""使用 Mac 本地时区的一次性终端预约。"""
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parent

def parse_time(value, now=None):
    now = now or dt.datetime.now()
    value = value.strip()
    rollover = False
    if re.fullmatch(r'(?:[01]?\d|2[0-3]):[0-5]\d', value):
        hour, minute = map(int, value.split(':'))
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += dt.timedelta(days=1)
            rollover = True
    elif re.fullmatch(r'\d{4}-\d{2}-\d{2} (?:[01]\d|2[0-3]):[0-5]\d', value):
        target = dt.datetime.strptime(value, '%Y-%m-%d %H:%M')
        if target <= now:
            raise ValueError('完整日期时间已经过去，请输入未来时间。')
    else:
        raise ValueError('格式错误，请输入 HH:MM 或 YYYY-MM-DD HH:MM。')
    epoch = time.mktime(target.timetuple())
    if dt.datetime.fromtimestamp(epoch) != target:
        raise ValueError('该本地时间不存在，可能处于夏令时切换区间。')
    # 夏令时回拨重复时刻不做猜测。
    possibilities = set()
    for isdst in (0, 1):
        candidate = time.mktime((*target.timetuple()[:8], isdst))
        if dt.datetime.fromtimestamp(candidate) == target:
            possibilities.add(candidate)
    if len(possibilities) > 1:
        raise ValueError('该本地时间有夏令时歧义，请选择其它时刻。')
    return epoch, rollover

def log(event, **fields):
    record = {'时间': dt.datetime.now().astimezone().isoformat(), '事件': event, **fields}
    line = json.dumps(record, ensure_ascii=False)
    print(line, flush=True)
    directory = BASE / 'logs'
    directory.mkdir(exist_ok=True, mode=0o700)
    with (directory / '预约.jsonl').open('a') as handle:
        handle.write(line + '\n')

def main():
    if sys.argv[1:] not in ([], ['--inspect']):
        raise ValueError('预约器参数错误。')
    inspect = sys.argv[1:] == ['--inspect']
    print('一次性 Codex 自动继续' + ('（预约只读诊断）' if inspect else ''))
    print('预约前检查辅助功能权限（不会发送消息）……', flush=True)
    preflight = subprocess.run([str(BASE/'bin/codex-continue'), '--request-permissions'], check=False)
    if preflight.returncode != 0:
        log('预约未建立', 原因='辅助功能权限预检未通过，请授权后在同一个终端重新预约', 返回码=preflight.returncode)
        return preflight.returncode
    value = input('请输入执行时间（例如 01:40，或 2026-10-22 01:40）：')
    epoch, rollover = parse_time(value)
    if rollover:
        print('该时分今天已经过去，明确解释为次日执行。')
    target = dt.datetime.fromtimestamp(epoch).astimezone().isoformat()
    log('已预约一次执行', 预约时间=target, 时区=time.tzname)
    print('请保持本终端进程运行；关闭终端或 Ctrl+C 会取消预约。')
    print('已尽可能防止空闲睡眠；合盖、锁屏、退出登录可能导致 GUI 执行失败。', flush=True)
    while time.time() < epoch:
        time.sleep(min(5, max(0, epoch-time.time())))
    if time.time()-epoch > 120:
        log('预约已取消', 原因='超过预约时间两分钟，可能经历睡眠')
        return 2
    log('实际开始执行', 预约时间=target)
    result = subprocess.run([str(BASE/'bin/codex-continue'), '--inspect' if inspect else '--run-now'], check=False)
    log('一次预约结束', 返回码=result.returncode)
    return result.returncode

if __name__ == '__main__':
    os.umask(0o077)
    try:
        sys.exit(main())
    except (ValueError, EOFError) as error:
        log('预约失败', 原因=str(error))
        sys.exit(2)
    except KeyboardInterrupt:
        log('用户取消预约')
        sys.exit(130)
