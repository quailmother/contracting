from unittest import TestCase
from seneca.stdlib.env import gather
from seneca.stdlib.bridge import hashing, imports, orm


class TestGather(TestCase):
    def test_hashing_imports_work(self):
        env = gather()

        self.assertLessEqual(hashing.exports.items(), env.items())

    def test_imports_imports_work(self):
        env = gather()

        self.assertLessEqual(imports.exports.items(), env.items())

    def test_orm_imports_work(self):
        env = gather()

        self.assertLessEqual(orm.exports.items(), env.items())

    def test_arbitrary_import_doesnt_work(self):
        env = gather()

        d = {
            'BadStuff': 1
        }

        self.assertFalse(d.items() <= env.items())