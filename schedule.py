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
    print(f"\n[{record['时间']}] {event}", flush=True)
    for key, value in fields.items():
        if isinstance(value, (tuple, list)):
            value = '、'.join(str(item) for item in value)
        print(f'  {key}：{value}', flush=True)
    directory = BASE / 'logs'
    directory.mkdir(exist_ok=True, mode=0o700)
    with (directory / '预约.jsonl').open('a') as handle:
        handle.write(line + '\n')

def native_command(*arguments):
    executable = str(BASE/'bin/codex-continue')
    architecture = os.environ.get('CODEX_CONTINUE_NATIVE_ARCH')
    prefix = ['/usr/bin/arch', f'-{architecture}'] if architecture in ('arm64', 'x86_64') else []
    return [*prefix, executable, *arguments]


def recovery_hint(reason):
    if '权限' in reason and ('辅助功能' in reason or '授权' in reason):
        terminal = os.environ.get('TERM_PROGRAM', '实际运行命令的终端')
        return f'在系统设置 → 隐私与安全性 → 辅助功能中开启 {terminal} 或系统列出的 codex-continue，然后回到同一个终端重新运行。'
    if '锁屏' in reason or '控制台' in reason:
        return '解锁这台 Mac，登录本机桌面后再运行；SSH、锁屏或退出登录时无法操作桌面。'
    if '实例' in reason:
        return '等待正在操作界面的实例结束，再重新运行；不要同时启动多个执行任务。'
    if '不可写' in reason:
        return f'检查项目和 logs 目录的所有者及写入权限：{BASE}。'
    if '进程' in reason:
        return '先打开包含 Codex 模式的桌面应用（某些版本名为 ChatGPT）并登录，保留一个目标应用实例，再重新运行。'
    if '窗口' in reason or '前台' in reason or '焦点' in reason:
        return '打开 Codex 主窗口，关闭弹出菜单，保持应用在前台，检查期间不要切换窗口。'
    if '草稿' in reason:
        return '在这个会话的输入框只写「继续」，不要发送；聊天历史中的继续或输入框占位文字不算草稿。其它内容请自行保留，不会自动覆盖。'
    if '运行中' in reason or '正在执行' in reason or '排队' in reason or '禁用' in reason or '按钮不可用' in reason:
        return '等当前任务结束或解除排队，查看应用的额度与登录提示，确认发送按钮恢复可用后再检查。'
    if '基线' in reason or '历史' in reason:
        return '等待会话历史加载完成后重试；仍失败时提供脱敏检查日志，不要反复执行发送。'
    if '置顶' in reason or '侧边栏' in reason or '会话' in reason or '身份' in reason:
        return '展开侧边栏和置顶分组；将目标保存并置顶，使用唯一标题，在输入框写好「继续」后重新运行。'
    if '发送按钮' in reason or 'composer' in reason or '输入框' in reason:
        return '等待界面加载完成，关闭遮挡面板，确认消息输入框和发送按钮可见；检查是否需要登录或处理额度提示。'
    return '按上面的原因处理后重新运行。若仍失败，请附上脱敏日志与 macOS、芯片和应用版本。'


def preflight(inspect=False):
    print('\n开始检查桌面应用与会话；不会发送消息。普通预约会切换置顶会话进行检查。', flush=True)
    try:
        result = subprocess.run(native_command('--preflight-inspect' if inspect else '--preflight'),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                check=False, timeout=180)
    except subprocess.TimeoutExpired as error:
        captured = error.stdout or ''
        if isinstance(captured, bytes):
            captured = captured.decode('utf-8', errors='replace')
        failure = json.dumps({'事件': '失败', '原因': '启动检查超时（180 秒）。请等待应用响应，减少不需要的置顶目标后重试'}, ensure_ascii=False)
        result = subprocess.CompletedProcess(error.cmd, 2, stdout=captured+'\n'+failure)
    targets = []
    records = []
    for line in result.stdout.splitlines():
        try:
            record = json.loads(line)
            if not isinstance(record, dict) or '事件' not in record:
                raise ValueError()
        except (ValueError, TypeError):
            print(line, flush=True)
            continue
        records.append(record)
        event = record['事件']
        if event == '辅助功能权限检查':
            state = '通过' if record.get('已授权') else '未通过'
            print(f"[{state}] 辅助功能权限：启动终端 {record.get('启动终端', '未知')}", flush=True)
        elif event == '检查通过':
            print(f"[通过] {record.get('项目')}：{record.get('详情')}", flush=True)
        elif event == '运行环境':
            print(f"[信息] 应用运行环境：{record.get('架构')}，可读窗口 {record.get('窗口数')} 个", flush=True)
        elif event == '目标识别通过，未发送':
            title = record.get('会话')
            if isinstance(title, str) and title and title not in targets:
                targets.append(title)
            print(f"[可预约] {title}\n  目标身份、继续草稿、发送区域、运行状态及消息历史校验通过。", flush=True)
            if record.get('发送按钮可用') is False:
                print('  发送按钮暂不可用，仍允许预约；到时会重新检查，恢复可用后才发送。', flush=True)
        elif event in ('跳过', '失败'):
            reason = str(record.get('原因', '未知原因'))
            if event == '跳过' and reason == 'composer 草稿不是恰好为继续':
                continue
            label = '不参与本次预约' if event == '跳过' else '未通过'
            print(f"[{label}] {record.get('会话', '启动检查')}\n  原因：{reason}\n  处理：{recovery_hint(reason)}", flush=True)
        elif event == '返回启动应用' and record.get('成功') is False:
            print('[提示] 无法自动返回启动终端，请手动切回终端查看检查结果。', flush=True)
        elif inspect and event == '当前活动会话':
            print(f"[通过] 当前只读目标：{record.get('标题')}", flush=True)
    # 启动检查日志保存在本地；不要求用户从原始 JSON 中自行定位错误。
    directory = BASE/'logs'
    directory.mkdir(exist_ok=True, mode=0o700)
    (directory/'preflight.log').write_text(result.stdout)
    passed = (result.returncode == 0 and bool(records)
              and (bool(targets) if not inspect else any(row.get('项目') == '只读诊断目标' for row in records)))
    if not passed:
        code = result.returncode if result.returncode != 0 else 2
        reason = '启动检查未通过；请按上方提示处理后重新运行，不会等待或发送消息'
        if not inspect and code == 3 and not targets:
            skipped = [row for row in records if row.get('事件') == '跳过']
            missing_drafts = sum(row.get('原因') == 'composer 草稿不是恰好为继续' for row in skipped)
            if skipped and missing_drafts == len(skipped):
                reason = f'已检查 {missing_drafts} 个会话，均未检测到恰好为「继续」的未发送草稿；未建立预约'
                print(f'[提示] 没有可预约目标。{reason}。', flush=True)
                print('请在目标置顶会话底部的输入框中填写「继续」，保留在输入框里，不要点击发送，然后重新运行。聊天历史中的「继续」不算草稿。', flush=True)
            else:
                print('[提示] 没有可预约目标，请先处理上方异常。需要参与预约的会话还须预填「继续」，不要发送。', flush=True)
        log('预约未建立', 原因=reason,
            返回码=code, 检查日志=str(directory/'preflight.log'))
        return code, []
    if inspect:
        print('\n[通过] 只读预约所需检查已通过；不要求草稿或发送条件。', flush=True)
    else:
        print(f'\n[通过] 必需检查完成，可预约目标 {len(targets)} 个。只处理本次通过检查的目标，其它会话不参与。', flush=True)
        print('到时仍会重新检查权限、目标和发送条件；现在通过不能保证届时额度、网络或界面状态不变。', flush=True)
    return 0, targets


def main():
    if sys.argv[1:] not in ([], ['--inspect'], ['--preflight']):
        raise ValueError('预约器参数错误。')
    inspect = sys.argv[1:] == ['--inspect']
    print('一次性 Codex 自动继续' + ('（预约只读诊断）' if inspect else ''), flush=True)
    code, targets = preflight(inspect)
    if code != 0:
        return code
    if sys.argv[1:] == ['--preflight']:
        print('检查结束：未建立预约、未发送消息。', flush=True)
        return 0
    value = input('请输入执行时间（例如 01:40，或 2026-10-22 01:40）：')
    epoch, rollover = parse_time(value)
    if rollover:
        print('该时分今天已经过去，明确解释为次日执行。')
    target = dt.datetime.fromtimestamp(epoch).astimezone().isoformat()
    log('已预约一次执行', 预约时间=target, 时区=time.tzname, 目标=targets if not inspect else ['当前只读窗口'])
    print('请保持本终端进程运行；关闭终端或 Ctrl+C 会取消预约。')
    print('已尽可能防止空闲睡眠；合盖、锁屏、退出登录可能导致 GUI 执行失败。', flush=True)
    while time.time() < epoch:
        time.sleep(min(5, max(0, epoch-time.time())))
    if time.time()-epoch > 120:
        log('预约已取消', 原因='超过预约时间两分钟，可能经历睡眠')
        return 2
    log('实际开始执行', 预约时间=target)
    arguments = ['--inspect'] if inspect else ['--run-now']
    if not inspect:
        for title in targets:
            arguments.extend(['--pinned-title', title])
    result = subprocess.run(native_command(*arguments), check=False)
    status = {0: '只读诊断完成' if inspect else '已确认新增界面历史消息',
              2: '执行失败', 3: '没有目标满足条件，未提交任何消息',
              4: '结果不确定，请人工核对，勿重发'}.get(result.returncode, '执行异常')
    log('一次预约结束', 返回码=result.returncode, 结果=status)
    return result.returncode

if __name__ == '__main__':
    os.umask(0o077)
    try:
        sys.exit(main())
    except EOFError:
        log('预约已取消', 原因='未输入执行时间，输入已结束；没有建立预约，也不会发送消息')
        sys.exit(2)
    except (ValueError, OSError) as error:
        log('预约失败', 原因=str(error))
        sys.exit(2)
    except KeyboardInterrupt:
        log('用户取消预约')
        sys.exit(130)
