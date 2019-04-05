from unittest import TestCase
from seneca.loaders.loader import *
import types


class TestDatabase(TestCase):
    def setUp(self):
        self.d = ContractDriver(host='localhost', port=6379, db=10)
        self.d.flush()

    def tearDown(self):
        self.d.flush()

    def test_init(self):
        self.assertEqual(self.d.delimiter, ':', 'Delimiter default not :.')
        self.assertEqual(self.d.code_key, '__code__', 'Code Key default not "code"')

    def test_dynamic_init(self):
        d = ContractDriver(host='localhost', port=6379, delimiter='*', db=9, code_key='jam')

        self.assertEqual(d.delimiter, '*', 'self.delimiter is not being set')
        self.assertEqual(d.code_key, 'jam', 'self.code_key is not being set')

    def test_push_and_get_contract(self):
        code = 'a = 123'
        name = 'test'

        self.d.push_contract(name, code)
        _code = self.d.get_contract(name)

        self.assertEqual(code, _code.decode(), 'Pushing and getting contracts is not working.')

    def test_flush(self):
        code = 'a = 123'
        name = 'test'

        self.d.push_contract(name, code)
        self.d.flush()

        self.assertIsNone(self.d.get_contract(name))


class TestDatabaseLoader(TestCase):
    def setUp(self):
        self.dl = DatabaseLoader()

    def test_init(self):
        self.assertTrue(isinstance(self.dl.d, ContractDriver), 'self.d is not a Database object.')

    def test_create_module(self):
        self.assertEqual(self.dl.create_module(None), None, 'self.create_module should return None')

    def test_exec_module(self):
        module = types.ModuleType('test')

        self.dl.d.push_contract('test', 'b = 1337')
        self.dl.exec_module(module)
        self.dl.d.flush()

        self.assertEqual(module.b, 1337)

    def test_exec_non_existance_module(self):
        module = types.ModuleType('test')

        with self.assertRaises(TypeError):
            self.dl.exec_module(module)

    def test_exec_module_nonattribute(self):
        module = types.ModuleType('test')

        self.dl.d.push_contract('test', 'b = 1337')
        self.dl.exec_module(module)
        self.dl.d.flush()

        with self.assertRaises(AttributeError):
            module.a

    def test_module_representation(self):
        module = types.ModuleType('howdy')

        self.assertEqual(self.dl.module_repr(module), "<module 'howdy' (smart contract)>")


class TestDatabaseFinder(TestCase):
    def test_find_module(self):
        d = DatabaseFinder()
        self.assertTrue(isinstance(d.find_module(None, None), DatabaseLoader), 'Database Finder does not return \
            a Database Loader')


class TestInstallLoader(TestCase):
    def test_install_loader(self):
        self.assertNotIn(DatabaseFinder, sys.meta_path)

        install_database_loader()

        self.assertIn(DatabaseFinder, sys.meta_path)

        uninstall_database_loader()

        self.assertNotIn(DatabaseFinder, sys.meta_path)

    def test_integration_and_importing(self):
        dl = DatabaseLoader()
        dl.d.push_contract('testing', 'a = 1234567890')

        install_database_loader()

        import testing

        #dl.d.flush()

        self.assertEqual(testing.a, 1234567890)