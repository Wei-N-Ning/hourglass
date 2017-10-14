
import unittest

import hourglass


class TestEncodeTag(unittest.TestCase):

    def test_single_class_name(self):
        name, port = hourglass.ServantImpl.encode_tag('SomeClass_p2222p_')
        self.assertEqual(('SomeClass', 2222), (name, port))

    def test_class_dot_path(self):
        name, port = hourglass.ServantImpl.encode_tag('package.module.SomeClass_p2222p_')
        self.assertEqual(('package.module.SomeClass', 2222), (name, port))


if __name__ == '__main__':
    unittest.main()
