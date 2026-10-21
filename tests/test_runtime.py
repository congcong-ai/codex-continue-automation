"""验证 Intel、Apple Silicon 和 Rosetta 下的真实架构选择。"""
from pathlib import Path
import subprocess
import unittest

RUNTIME = Path(__file__).resolve().parents[1]/'scripts/runtime.sh'


class MachineTests(unittest.TestCase):
    def classify(self, machine, arm, translated):
        return subprocess.run(
            ['bash', '-c', 'source "$1"; classify_mac "$2" "$3" "$4" || exit $?; printf "%s\\n%s\\n" "$NATIVE_ARCH" "$MACHINE_LABEL"',
             'runtime-test', str(RUNTIME), machine, arm, translated],
            text=True, capture_output=True)

    def test_intel(self):
        result = self.classify('x86_64', '0', '')
        self.assertEqual(result.returncode, 0)
        self.assertIn('x86_64\nIntel', result.stdout)
        self.assertNotIn('Rosetta', result.stdout)

    def test_native_apple_silicon(self):
        result = self.classify('arm64', '1', '0')
        self.assertEqual(result.returncode, 0)
        self.assertIn('arm64\nApple Silicon', result.stdout)
        self.assertNotIn('Rosetta', result.stdout)

    def test_rosetta_uses_arm64_even_if_process_reports_intel(self):
        result = self.classify('x86_64', '0', '1')
        self.assertEqual(result.returncode, 0)
        self.assertIn('arm64\nApple Silicon', result.stdout)
        self.assertIn('Rosetta', result.stdout)

    def test_unknown_architecture_is_rejected(self):
        result = self.classify('unknown', '0', '0')
        self.assertEqual(result.returncode, 2)
        self.assertIn('无法识别芯片架构', result.stderr)


if __name__ == '__main__':
    unittest.main()
