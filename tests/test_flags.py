import unittest
from flagpole import Flags


class TestFlags(unittest.TestCase):

    def test_flags(self):
        FLAGS_1 = Flags('BASE')
        self.assertEqual(FLAGS_1.BASE, 1)
        self.assertEqual(FLAGS_1.ALL, 1)

        FLAGS_2 = Flags('BASE', 'FEATURE_ONE')
        self.assertEqual(FLAGS_2.BASE, 1)
        self.assertEqual(FLAGS_2.FEATURE_ONE, 2)
        self.assertEqual(FLAGS_2.ALL, 3)

        FLAGS_3 = Flags('BASE', 'FEATURE_ONE', 'FEATURE_TWO')
        self.assertEqual(FLAGS_3.BASE, 1)
        self.assertEqual(FLAGS_3.FEATURE_ONE, 2)
        self.assertEqual(FLAGS_3.FEATURE_TWO, 4)
        self.assertEqual(FLAGS_3.ALL, 7)
        self.assertEqual(str(FLAGS_3), "OrderedDict([('BASE', 1), ('FEATURE_ONE', 2), ('FEATURE_TWO', 4), ('ALL', 7), ('None', 0), ('NONE', 0)])")
