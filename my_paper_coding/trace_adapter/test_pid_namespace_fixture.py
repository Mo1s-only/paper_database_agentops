import unittest

from pid_namespace_fixture import parse_nspid


class PidNamespaceFixtureTests(unittest.TestCase):
    def test_parse_nested_namespace_vector(self):
        self.assertEqual(parse_nspid("Name:\tsh\nNSpid:\t1758\t81\n"), [1758, 81])

    def test_missing_vector_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "absent"):
            parse_nspid("Name:\tsh\nPid:\t10\n")

    def test_nonpositive_vector_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Invalid"):
            parse_nspid("NSpid:\t10\t0\n")


if __name__ == "__main__":
    unittest.main()
