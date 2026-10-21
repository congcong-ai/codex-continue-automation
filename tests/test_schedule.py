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
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0][-1],'--inspect')
    def test_late_skip(self):
        result,run,_=self.run_main(late=True)
        self.assertEqual(result,2)
        run.assert_not_called()

if __name__=='__main__':unittest.main()
