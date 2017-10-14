
import unittest

import hourglass

from utilities import ProcessHelper


class TestServantImplGetter(unittest.TestCase):

    def setUp(self):
        self.ph = ProcessHelper()

    def tearDown(self):
        self.ph.clear()

    def _create_process(self, tag):
        return self.ph.create_process(tag)

    def test_expect_num_servant_impls(self):
        self.ph.create_process(hourglass.TAG_TEMPLATE.format(
            'fumoffu_p8080p_'))
        self.ph.create_process(hourglass.TAG_TEMPLATE.format(
            'doom_p8081p_'))
        p = hourglass.ServantImplGetter()
        result = p.get_servant_impls()
        self.assertEqual(2, len(result))
        p.terminate()


class TestServant(unittest.TestCase):

    def setUp(self):
        hourglass.ServantImplGetter().terminate()

    def test_create_expect_process_created(self):
        s = hourglass.Servant.create('DemoService')
        self.assertTrue(hourglass.ProcessUtils.process_exists(s.impl.pid))

    def test_create_expect_health(self):
        s = hourglass.Servant.create('DemoService')
        result = s.service_health()
        self.assertTrue(result['is_running'])

    def test_create_then_call_service(self):
        s = hourglass.Servant.create('DemoService')
        result = s.call_service('foo')
        self.assertTrue(result)
        self.assertTrue(result['demo'])

    def test_create_expect_process_reused(self):
        s1 = hourglass.Servant.create('DemoService')
        s2 = hourglass.Servant.create('DemoService')
        self.assertEqual(s1.impl, s2.impl)

    def test_create_expect_process_recreated(self):
        s1 = hourglass.Servant.create('DemoService')
        s1.terminate()
        self.assertFalse(s1.is_alive())
        s2 = hourglass.Servant.create('DemoService')
        self.assertNotEqual(s1.impl, s2.impl)

    def tearDown(self):
        hourglass.ServantImplGetter().terminate()


if __name__ == '__main__':
    unittest.main()
