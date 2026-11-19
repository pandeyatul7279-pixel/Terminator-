import unittest

from tools.phone_doctor import GIB, assess, memory_info


class PhoneDoctorTests(unittest.TestCase):
    def test_virtual_ram_is_separate(self):
        result = memory_info('MemTotal: 7800000 kB\nMemAvailable: 4000000 kB\nSwapTotal: 12000000 kB\n')
        self.assertEqual(result['physicalBytes'], 7800000 * 1024)
        self.assertEqual(result['swapBytes'], 12000000 * 1024)
        self.assertNotEqual(result['physicalBytes'], 19800000 * 1024)

    def test_unavailable_memory_is_not_invented(self):
        self.assertIsNone(memory_info('')['physicalBytes'])
        self.assertIsNone(memory_info('MemTotal: blocked kB')['physicalBytes'])

    def test_supported_phone_still_does_not_certify_features(self):
        result = assess(is_termux=True, architecture='aarch64', free_bytes=12 * GIB, physical_bytes=7 * GIB, uid=10234)
        self.assertTrue(result['hostPreflightPassed'])
        self.assertEqual(result['androidParity'], 'NOT_CERTIFIED')

    def test_linux_x64_is_not_a_phone_test(self):
        result = assess(is_termux=False, architecture='x86_64', free_bytes=20 * GIB, physical_bytes=16 * GIB, uid=1000)
        self.assertFalse(result['hostPreflightPassed'])
        self.assertEqual(len(result['blockers']), 2)

    def test_low_storage_blocks_install(self):
        result = assess(is_termux=True, architecture='arm64', free_bytes=4 * GIB, physical_bytes=8 * GIB, uid=10234)
        self.assertFalse(result['hostPreflightPassed'])
        self.assertIn('8 GiB', result['blockers'][0])

    def test_no_root_is_required(self):
        result = assess(is_termux=True, architecture='arm64', free_bytes=12 * GIB, physical_bytes=8 * GIB, uid=0)
        self.assertFalse(result['hostPreflightPassed'])
        self.assertIn('never root', result['blockers'][0])


if __name__ == '__main__':
    unittest.main()
