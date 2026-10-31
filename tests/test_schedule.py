import datetime as dt
import importlib.util
from pathlib import Path
import unittest
spec = importlib.util.spec_from_file_location('schedule', Path(__file__).resolve().parents[1]/'schedule.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
class ScheduleTests(unittest.TestCase):
    now = dt.datetime(2026, 10, 21, 12, 0)
    def test_future(self):
        epoch, rollover = m.parse_time('13:40', self.now)
        self.assertEqual(dt.datetime.fromtimestamp(epoch, m.BEIJING).replace(tzinfo=None), dt.datetime(2026,10,21,13,40))
        self.assertFalse(rollover)
    def test_rollover(self):
        epoch, rollover = m.parse_time('01:40', self.now)
        self.assertEqual(dt.datetime.fromtimestamp(epoch, m.BEIJING).replace(tzinfo=None),dt.datetime(2026,10,22,1,40))
        self.assertTrue(rollover)
    def test_full(self):
        epoch, rollover=m.parse_time('2026-10-22 01:40',self.now)
        self.assertEqual(dt.datetime.fromtimestamp(epoch, m.BEIJING).replace(tzinfo=None),dt.datetime(2026,10,22,1,40))
        self.assertFalse(rollover)
    def test_invalid(self):
        for value in ['2026-10-20 01:40','2026-02-30 01:40','25:00','12:60','继续','2026-10-21 12:00']:
            with self.subTest(value=value), self.assertRaises(ValueError):m.parse_time(value,self.now)
    def test_new_year(self):
        epoch, _=m.parse_time('01:00',dt.datetime(2026,12,31,23,59))
        self.assertEqual(dt.datetime.fromtimestamp(epoch, m.BEIJING).replace(tzinfo=None),dt.datetime(2027,1,1,1))

    def test_morning_input_noon_stays_today(self):
        epoch, rollover=m.parse_time('12:40',dt.datetime(2026,10,25,8,57))
        self.assertEqual(m.format_beijing(epoch),'2026-10-25 12:40')
        self.assertFalse(rollover)
        self.assertEqual(epoch,dt.datetime(2026,10,25,4,40,tzinfo=dt.timezone.utc).timestamp())

    def test_midnight_and_noon_are_twelve_hours_apart(self):
        now=dt.datetime(2026,10,25,0,10)
        midnight,rollover=m.parse_time('0:40',now)
        noon,_=m.parse_time('12:40',now)
        self.assertFalse(rollover)
        self.assertEqual(m.format_beijing(midnight),'2026-10-25 00:40')
        self.assertEqual(noon-midnight,12*60*60)

    def test_timezone_aware_now_is_converted_to_beijing(self):
        epoch,rollover=m.parse_time('12:40',dt.datetime(2026,10,25,0,57,tzinfo=dt.timezone.utc))
        self.assertFalse(rollover)
        self.assertEqual(m.format_beijing(epoch),'2026-10-25 12:40')

    def test_system_timezone_cannot_change_beijing_schedule(self):
        import os,time
        from unittest.mock import patch
        try:
            for timezone in ['UTC','America/Los_Angeles','Asia/Shanghai']:
                with self.subTest(timezone=timezone),patch.dict(os.environ,{'TZ':timezone}):
                    time.tzset()
                    epoch,rollover=m.parse_time('12:40',dt.datetime(2026,10,25,8,57))
                    self.assertFalse(rollover)
                    self.assertEqual(m.format_beijing(epoch),'2026-10-25 12:40')
        finally:
            time.tzset()

    def test_log_uses_simple_beijing_time(self):
        import contextlib,io,json,tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(prefix='codex-beijing-log-') as folder:
            output=io.StringIO()
            with patch.object(m,'BASE',Path(folder)),contextlib.redirect_stdout(output):
                m.log('已预约一次执行',输入时间='12:40',预约时间='2026-10-25 12:40（北京时间）')
            row=json.loads((Path(folder)/'logs/预约.jsonl').read_text())
            self.assertRegex(row['时间'],r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')
            self.assertIn('2026-10-25 12:40（北京时间）',output.getvalue())
            self.assertNotIn('+08:00',output.getvalue())
            self.assertNotIn('CST',output.getvalue())

class ExecutionTests(unittest.TestCase):
    def run_main(self, *, inspect=False, late=False, code=0):
        from unittest.mock import patch, Mock
        clock=iter([1000.0,1000.0,1001.0,1202.0 if late else 1001.0])
        argv=['schedule.py','--inspect'] if inspect else ['schedule.py']
        with patch.object(m.sys,'argv',argv), patch('builtins.input',return_value='13:40'), patch.object(m,'preflight',return_value=(0,['目标甲','目标乙'])) as check, patch.object(m,'wait_for_desktop',return_value=True), patch.object(m,'parse_time',return_value=(1001.0,False)), patch.object(m.time,'time',side_effect=lambda:next(clock)), patch.object(m.time,'sleep'), patch.object(m,'log') as logger, patch.object(m.subprocess,'run',return_value=Mock(returncode=code)) as run, patch.dict(m.os.environ,{},clear=True):
            result=m.main()
            return result,run,logger,check

    def test_targets_are_frozen_and_submitted_once(self):
        result,run,_,check=self.run_main()
        self.assertEqual(result,0)
        check.assert_called_once_with(False)
        run.assert_called_once_with([str(m.BASE/'bin/codex-continue'),'--run-now','--pinned-title','目标甲','--pinned-title','目标乙'],check=False)

    def test_readonly_schedule_does_not_submit(self):
        result,run,_,check=self.run_main(inspect=True)
        self.assertEqual(result,0)
        check.assert_called_once_with(True)
        run.assert_called_once_with([str(m.BASE/'bin/codex-continue'),'--inspect'],check=False)

    def test_late_schedule_never_executes(self):
        result,run,_,_=self.run_main(late=True)
        self.assertEqual(result,2)
        run.assert_not_called()

    def test_desktop_timeout_never_calls_send(self):
        from unittest.mock import patch
        with patch.object(m.sys,'argv',['schedule.py']), patch.object(m,'preflight',return_value=(0,['目标甲'])), patch('builtins.input',return_value='13:40'), patch.object(m,'parse_time',return_value=(1000,False)), patch.object(m.time,'time',return_value=1001), patch.object(m,'wait_for_desktop',return_value=False), patch.object(m,'log'), patch.object(m.subprocess,'run') as send:
            self.assertEqual(m.main(),2)
            send.assert_not_called()

    def test_failed_check_never_prompts_or_waits(self):
        from unittest.mock import patch
        for code in (2,3):
            with self.subTest(code=code), patch.object(m.sys,'argv',['schedule.py']), patch.object(m,'preflight',return_value=(code,[])), patch('builtins.input') as prompt, patch.object(m.time,'sleep') as sleep, patch.object(m.subprocess,'run') as run:
                self.assertEqual(m.main(),code)
                prompt.assert_not_called()
                sleep.assert_not_called()
                run.assert_not_called()

    def test_preflight_only_never_prompts_or_schedules(self):
        from unittest.mock import patch
        with patch.object(m.sys,'argv',['schedule.py','--preflight']), patch.object(m,'preflight',return_value=(0,['目标甲'])), patch('builtins.input') as prompt, patch.object(m.subprocess,'run') as run:
            self.assertEqual(m.main(),0)
            prompt.assert_not_called()
            run.assert_not_called()

    def test_failure_and_uncertainty_are_propagated_without_retry(self):
        for code,expected in [(3,'没有目标满足条件，未提交任何消息'),(4,'结果不确定，请人工核对，勿重发')]:
            with self.subTest(code=code):
                result,run,logger,_=self.run_main(code=code)
                self.assertEqual(result,code)
                run.assert_called_once()
                logger.assert_called_with('一次预约结束',返回码=code,结果=expected)

    def test_preflight_happens_before_time_input(self):
        from unittest.mock import patch
        events=[]
        def check(_):
            events.append('检查')
            return 0,['目标甲']
        def cancel(_):
            events.append('输入时间')
            raise EOFError()
        with patch.object(m.sys,'argv',['schedule.py']), patch.object(m,'preflight',side_effect=check), patch('builtins.input',side_effect=cancel):
            with self.assertRaises(EOFError):m.main()
        self.assertEqual(events,['检查','输入时间'])


class PreflightTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from unittest.mock import patch
        self.temp=tempfile.TemporaryDirectory(prefix='codex-preflight-test-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        patcher=patch.object(m,'BASE',self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def check(self,rows,code=0,inspect=False):
        import io,json
        from contextlib import redirect_stdout
        from unittest.mock import patch,Mock
        output=io.StringIO()
        payload='\n'.join(json.dumps(row,ensure_ascii=False) for row in rows)
        with patch.object(m.subprocess,'run',return_value=Mock(returncode=code,stdout=payload)) as run, redirect_stdout(output):
            result=m.preflight(inspect)
        self.assertEqual((self.root/'logs/preflight.log').read_text(),payload)
        return result,output.getvalue(),run

    def test_ready_targets_are_unique_and_unready_targets_excluded(self):
        result,output,_=self.check([
            {'事件':'检查通过','项目':'桌面状态','详情':'未锁屏'},
            {'事件':'目标识别通过，未发送','会话':'目标甲'},
            {'事件':'跳过','会话':'目标乙','原因':'composer 草稿不是恰好为继续'},
            {'事件':'目标识别通过，未发送','会话':'目标甲'},
        ])
        self.assertEqual(result,(0,['目标甲']))
        self.assertIn('可预约目标 1 个',output)
        self.assertNotIn('不参与本次预约',output)
        self.assertNotIn('目标乙',output)
        self.assertNotIn('composer 草稿不是恰好为继续',output)

    def test_permissions_failure_explains_actual_terminal(self):
        from unittest.mock import patch
        with patch.dict(m.os.environ,{'TERM_PROGRAM':'iTerm.app'}):
            result,output,_=self.check([{'事件':'失败','原因':'缺少辅助功能权限'}],code=2)
        self.assertEqual(result,(2,[]))
        self.assertIn('iTerm.app',output)
        self.assertIn('预约未建立',output)

    def test_zero_eligible_targets_blocks_scheduling(self):
        result,output,_=self.check([{'事件':'跳过','会话':'目标甲','原因':'composer 草稿不是恰好为继续'}],code=3)
        self.assertEqual(result,(3,[]))
        self.assertIn('没有可预约目标',output)
        self.assertNotIn('目标甲',output)
        self.assertIn('已检查 1 个会话，均未检测到',output)
        self.assertIn('聊天历史中的「继续」不算草稿',output)
        self.assertNotIn('启动检查未通过',output)

    def test_other_failures_remain_visible(self):
        result,output,_=self.check([
            {'事件':'跳过','会话':'异常目标','原因':'切换后会话身份不符，禁止操作'},
            {'事件':'返回启动应用','成功':False},
        ],code=3)
        self.assertEqual(result,(3,[]))
        self.assertIn('异常目标',output)
        self.assertIn('切换后会话身份不符',output)
        self.assertIn('请手动切回终端',output)
        self.assertIn('请先处理上方异常',output)
        self.assertNotIn('均未检测到',output)

    def test_disabled_send_button_still_allows_scheduling(self):
        result,output,_=self.check([
            {'事件':'目标识别通过，未发送','会话':'额度耗尽目标','发送按钮可用':False},
        ])
        self.assertEqual(result,(0,['额度耗尽目标']))
        self.assertIn('发送按钮暂不可用，仍允许预约',output)
        self.assertIn('恢复可用后才发送',output)
        self.assertNotIn('预约未建立',output)

    def test_success_exit_without_evidence_is_rejected(self):
        result,_,_=self.check([])
        self.assertEqual(result,(2,[]))

    def test_readonly_checks_do_not_require_ready_draft(self):
        result,output,_=self.check([{'事件':'检查通过','项目':'只读诊断目标','详情':'会话可靠'}],inspect=True)
        self.assertEqual(result,(0,[]))
        self.assertIn('不要求草稿',output)

    def test_native_architecture_invocation(self):
        from unittest.mock import patch
        with patch.dict(m.os.environ,{'CODEX_CONTINUE_NATIVE_ARCH':'arm64'}):
            self.assertEqual(m.native_command('--preflight'),['/usr/bin/arch','-arm64',str(self.root/'bin/codex-continue'),'--preflight'])
        with patch.dict(m.os.environ,{'CODEX_CONTINUE_NATIVE_ARCH':'invalid'}):
            self.assertEqual(m.native_command('--preflight'),[str(self.root/'bin/codex-continue'),'--preflight'])

    def test_timeout_stops_check_and_explains_failure(self):
        import io,subprocess
        from contextlib import redirect_stdout
        from unittest.mock import patch
        output=io.StringIO()
        with patch.object(m.subprocess,'run',side_effect=subprocess.TimeoutExpired(['native'],180,output=b'')), redirect_stdout(output):
            self.assertEqual(m.preflight(),(2,[]))
        self.assertIn('启动检查超时',output.getvalue())
        self.assertIn('预约未建立',output.getvalue())

    def test_human_output_and_structured_log(self):
        import io,json
        from contextlib import redirect_stdout
        output=io.StringIO()
        with redirect_stdout(output):m.log('已预约一次执行',目标=['目标甲'],返回码=0)
        self.assertIn('目标：目标甲',output.getvalue())
        self.assertFalse(output.getvalue().lstrip().startswith('{'))
        record=json.loads((self.root/'logs/预约.jsonl').read_text())
        self.assertEqual(record['目标'],['目标甲'])


class StartupProcessTests(unittest.TestCase):
    def test_successful_preflight_only_process_does_not_schedule_or_send(self):
        import tempfile,shutil,subprocess,sys,os,json,shlex
        with tempfile.TemporaryDirectory(prefix='codex-ready-startup-') as directory:
            root=Path(directory)
            shutil.copyfile(m.__file__,root/'schedule.py')
            (root/'bin').mkdir()
            helper=root/'bin/codex-continue'
            payload=json.dumps({'事件':'目标识别通过，未发送','会话':'隔离测试目标'},ensure_ascii=False)
            helper.write_text("#!/bin/sh\n[ \"$1\" = \"--preflight\" ] || exit 99\nprintf '%s\\n' " + shlex.quote(payload) + "\n")
            helper.chmod(0o700)
            env=os.environ.copy()
            env.pop('CODEX_CONTINUE_NATIVE_ARCH',None)
            result=subprocess.run([sys.executable,'-B',str(root/'schedule.py'),'--preflight'],input='',text=True,capture_output=True,env=env,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('可预约目标 1 个',result.stdout)
            self.assertIn('未建立预约、未发送消息',result.stdout)
            self.assertNotIn('请输入执行时间',result.stdout)
            self.assertFalse((root/'logs/预约.jsonl').exists())

    def test_denied_preflight_stops_real_process_before_time_input(self):
        import tempfile,shutil,subprocess,sys,os,json,shlex
        with tempfile.TemporaryDirectory(prefix='codex-denied-startup-') as directory:
            root=Path(directory)
            shutil.copyfile(m.__file__,root/'schedule.py')
            (root/'bin').mkdir()
            helper=root/'bin/codex-continue'
            helper.write_text("#!/bin/sh\nprintf '%s\\n' '{\"事件\":\"失败\",\"原因\":\"缺少辅助功能权限\"}'\nexit 2\n")
            helper.chmod(0o700)
            env=os.environ.copy()
            env.pop('CODEX_CONTINUE_NATIVE_ARCH',None)
            result=subprocess.run([sys.executable,'-B',str(root/'schedule.py')],input='23:59\n',text=True,capture_output=True,env=env,timeout=10)
            self.assertEqual(result.returncode,2,result.stdout+result.stderr)
            self.assertNotIn('请输入执行时间',result.stdout)
            self.assertNotIn('已预约一次执行',result.stdout)
            self.assertIn('系统设置',result.stdout)
            records=[json.loads(line) for line in (root/'logs/预约.jsonl').read_text().splitlines()]
            self.assertEqual([row['事件'] for row in records],['预约未建立'])


if __name__=='__main__':unittest.main()


class DesktopWaitTests(unittest.TestCase):
    def simulate(self, codes, *, start=1000, step=5):
        from unittest.mock import patch, Mock
        clock=[start]
        def sleep(seconds): clock[0]+=max(seconds,step)
        with patch.object(m.time,'time',side_effect=lambda:clock[0]), patch.object(m.time,'monotonic',side_effect=lambda:clock[0]), patch.object(m.time,'sleep',side_effect=sleep), patch.object(m,'log') as logger, patch.object(m.subprocess,'run',side_effect=[Mock(returncode=c,stdout='桌面已锁屏') for c in codes]) as run:
            result=m.wait_for_desktop(1000)
            self.assertTrue(all(call.args[0][-1]=='--check-desktop' for call in run.call_args_list))
            return result, run.call_count, logger

    def test_unlocked_immediately(self):
        result,count,_=self.simulate([0])
        self.assertTrue(result)
        self.assertEqual(count,1)

    def test_unlock_then_continue(self):
        result,count,logger=self.simulate([5,5,0])
        self.assertTrue(result)
        self.assertEqual(count,3)
        self.assertEqual(logger.call_args_list[0].args[0],'等待桌面解锁')
        self.assertEqual(logger.call_args_list[-1].args[0],'桌面已恢复')

    def test_locked_until_deadline_cancels(self):
        result,count,_=self.simulate([5]*25)
        self.assertFalse(result)
        self.assertEqual(count,25)

    def test_already_late_does_not_probe(self):
        result,count,_=self.simulate([],start=1121)
        self.assertFalse(result)
        self.assertEqual(count,0)

    def test_probe_error_does_not_retry(self):
        result,count,_=self.simulate([2])
        self.assertFalse(result)
        self.assertEqual(count,1)
