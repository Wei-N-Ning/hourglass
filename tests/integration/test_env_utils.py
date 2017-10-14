
import unittest

import hourglass


class TestRegistry(unittest.TestCase):

    def test_expect_vendor_class_registered(self):
        hourglass.EnvUtils.register_generators(['vendor.wtEnvGenerators'])
        self.assertTrue(hourglass.EnvUtils.get_generator_names())


if __name__ == '__main__':
    unittest.main()
