from src.core.nspawn_manager import NspawnManager
import unittest

class TestNspawnManager(unittest.TestCase):
    def setUp(self):
        self.manager = NspawnManager()

    def test_create_container(self):
        result = self.manager.create_container("test-container")
        self.assertTrue(result)

    def test_start_container(self):
        self.manager.create_container("test-container")
        result = self.manager.start_container("test-container")
        self.assertTrue(result)

    def test_stop_container(self):
        self.manager.create_container("test-container")
        self.manager.start_container("test-container")
        result = self.manager.stop_container("test-container")
        self.assertTrue(result)

    def test_remove_container(self):
        self.manager.create_container("test-container")
        self.manager.start_container("test-container")
        self.manager.stop_container("test-container")
        result = self.manager.remove_container("test-container")
        self.assertTrue(result)

    def test_network_configuration(self):
        self.manager.create_container("test-container")
        result = self.manager.configure_network("test-container", "192.168.1.2", "255.255.255.0")
        self.assertTrue(result)

    def test_nested_container(self):
        self.manager.create_container("parent-container")
        result = self.manager.create_container("nested-container", parent="parent-container")
        self.assertTrue(result)

    def test_ssh_setup(self):
        self.manager.create_container("test-container")
        result = self.manager.setup_ssh("test-container")
        self.assertTrue(result)

if __name__ == '__main__':
    unittest.main()