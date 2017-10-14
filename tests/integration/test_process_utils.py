
import unittest

import hourglass

from utilities import ProcessHelper


class TestFindPidByTag(unittest.TestCase):

    def setUp(self):
        self.ph = ProcessHelper()

    def tearDown(self):
        self.ph.clear()

    def _create_process(self, tag):
        return self.ph.create_process(tag)

    def test_expect_process_found(self):
        tag = 'thereiscow=1337'
        self._create_process(tag)
        pid = hourglass.ProcessUtils.find_pid_by_tag(tag)
        self.assertTrue(pid > 0)

    def test_expect_process_not_found(self):
        tag = 'whereisthespoon=1'
        self._create_process(tag)
        pid = hourglass.ProcessUtils.find_pid_by_tag('dododo=1')
        self.assertEqual(-1, pid)


class TestFindPidsByRegex(unittest.TestCase):

    def setUp(self):
        self.ph = ProcessHelper()

    def tearDown(self):
        self.ph.clear()

    def _create_process(self, tag):
        return self.ph.create_process(tag)

    def test_expect_pid_by_tag(self):
        self._create_process('KJQ789=service1_p8080p_')
        self._create_process('KJQ789=service2_p8080p_')
        pid_by_tag = hourglass.ProcessUtils.find_pids_by_regex('KJQ789=\w+')
        self.assertEqual({'KJQ789=service1_p8080p_', 'KJQ789=service2_p8080p_'}, set(pid_by_tag))

    def test_expect_no_processes_found(self):
        self._create_process('something=service3')
        pid_by_tag = hourglass.ProcessUtils.find_pids_by_regex('KJQ=\w+')
        self.assertFalse(pid_by_tag)


if __name__ == '__main__':
    unittest.main()
