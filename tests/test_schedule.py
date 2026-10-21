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
        self.assertEqual(dt.datetime.fromtimestamp(epoch), dt.datetime(2026,10,21,13,40))
        self.assertFalse(rollover)
    def test_rollover(self):
        epoch, rollover = m.parse_time('01:40', self.now)
        self.assertEqual(dt.datetime.fromtimestamp(epoch),dt.datetime(2026,10,22,1,40))
        self.assertTrue(rollover)
    def test_full(self):
        epoch, rollover=m.parse_time('2026-10-22 01:40',self.now)
        self.assertEqual(dt.datetime.fromtimestamp(epoch),dt.datetime(2026,10,22,1,40))
        self.assertFalse(rollover)
    def test_invalid(self):
        for value in ['2026-10-20 01:40','2026-02-30 01:40','25:00','12:60','继续','2026-10-21 12:00']:
            with self.subTest(value=value), self.assertRaises(ValueError):m.parse_time(value,self.now)
    def test_new_year(self):
        epoch, _=m.parse_time('01:00',dt.datetime(2026,12,31,23,59))
        self.assertEqual(dt.datetime.fromtimestamp(epoch),dt.datetime(2027,1,1,1))

class ExecutionTests(unittest.TestCase):
    def run_main(self, late=False):
        from unittest.mock import patch, Mock
        now=1000.0
        clock=iter([1000.0,1000.0,1001.0,1202.0 if late else 1001.0])
        with patch.object(m.sys,'argv',['schedule.py','--inspect']), patch('builtins.input',return_value='13:40'), patch.object(m,'parse_time',return_value=(1001.0,False)), patch.object(m.time,'time',side_effect=lambda: next(clock)), patch.object(m.time,'sleep'), patch.object(m,'log') as logger, patch.object(m.subprocess,'run',return_value=Mock(returncode=0)) as run:
            result=m.main()
            return result,run,logger
    def test_execute_exactly_once_readonly(self):
        result,run,_=self.run_main()
        self.assertEqual(result,0)
        self.assertEqual(run.call_count,2)
        self.assertEqual(run.call_args_list[0].args[0][-1],'--request-permissions')
        self.assertEqual(run.call_args_list[1].args[0][-1],'--inspect')
    def test_late_skip(self):
        result,run,_=self.run_main(late=True)
        self.assertEqual(result,2)
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0][-1],'--request-permissions')

    def test_permission_denied_never_prompts_or_schedules(self):
        from unittest.mock import patch, Mock
        with patch.object(m.sys,'argv',['schedule.py']), patch('builtins.input') as prompt, patch.object(m,'log') as logger, patch.object(m.time,'sleep') as sleep, patch.object(m.subprocess,'run',return_value=Mock(returncode=2)) as run:
            self.assertEqual(m.main(),2)
        prompt.assert_not_called()
        sleep.assert_not_called()
        run.assert_called_once_with([str(m.BASE/'bin/codex-continue'),'--request-permissions'],check=False)
        self.assertEqual(logger.call_args.args[0],'预约未建立')

    def test_permission_checked_before_time_input(self):
        from unittest.mock import patch, Mock
        events=[]
        def execute(command, **kwargs):
            events.append(command[-1])
            return Mock(returncode=0)
        def cancel_input(_):
            events.append('输入时间')
            raise EOFError()
        with patch.object(m.sys,'argv',['schedule.py']), patch('builtins.input',side_effect=cancel_input), patch.object(m.subprocess,'run',side_effect=execute):
            with self.assertRaises(EOFError):
                m.main()
        self.assertEqual(events,['--request-permissions','输入时间'])

    def test_formal_execution_preflights_and_sends_once(self):
        from unittest.mock import patch, Mock
        with patch.object(m.sys,'argv',['schedule.py']), patch('builtins.input',return_value='13:40'), patch.object(m,'parse_time',return_value=(1001.0,False)), patch.object(m.time,'time',return_value=1001.0), patch.object(m,'log'), patch.object(m.subprocess,'run',return_value=Mock(returncode=0)) as run:
            self.assertEqual(m.main(),0)
        self.assertEqual([call.args[0][-1] for call in run.call_args_list],['--request-permissions','--run-now'])

    def test_no_submission_and_uncertain_results_propagate(self):
        from unittest.mock import patch, Mock
        for code, expected in [(3,'没有目标满足条件，未提交任何消息'),(4,'结果不确定，请人工核对，勿重发')]:
            with self.subTest(code=code), patch.object(m.sys,'argv',['schedule.py']), patch('builtins.input',return_value='13:40'), patch.object(m,'parse_time',return_value=(1001.0,False)), patch.object(m.time,'time',return_value=1001.0), patch.object(m,'log') as logger, patch.object(m.subprocess,'run',side_effect=[Mock(returncode=0),Mock(returncode=code)]) as run:
                self.assertEqual(m.main(),code)
                self.assertEqual(run.call_count,2)
                logger.assert_called_with('一次预约结束',返回码=code,结果=expected)

if __name__=='__main__':unittest.main()
