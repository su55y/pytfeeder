from pathlib import Path
import unittest

from pytfeeder.storage import DBHooks, Storage
from .mocks import sample_channel, sample_entries


class StorageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_file = Path("/tmp/test.db")
        if cls.db_file.exists():
            cls.db_file.unlink()
        cls.db_hooks = DBHooks(cls.db_file)
        if err := cls.db_hooks.init_db():
            raise err
        cls.stor = Storage(cls.db_file)

    @classmethod
    def tearDownClass(cls):
        if err := cls.db_hooks.drop_db():
            raise err

    def test1_insert(self):
        self.assertEqual(self.stor.add_channels([sample_channel]), 1)
        self.assertEqual(
            self.stor.add_entries(sample_entries, sample_channel.channel_id),
            len(sample_entries),
        )

    def test2_select_channel(self):
        channel = self.stor.select_channel(sample_channel.channel_id)
        self.assertIsNotNone(channel)
        self.assertEqual(channel, sample_channel)

    def test2_select_entries(self):
        entries = self.stor.select_entries(sample_channel.channel_id)
        self.assertEqual(entries, sample_entries)

    def test2_select_not_found(self):
        self.assertIsNone(self.stor.select_channel(""))
        entries = self.stor.select_entries(channel_id="-")
        self.assertEqual(len(entries), 0)

    def test3_insert_duplicate(self):
        count = self.stor.add_entries(sample_entries, sample_channel.channel_id)
        self.assertEqual(count, 0)

    def test4_delete(self):
        self.stor.delete_all_entries()
        self.stor.update_active_channels([])
        self.stor.delete_inactive_channels()
        self.assertIsNone(self.stor.select_channel(sample_channel.channel_id))
        self.assertEqual(len(self.stor.select_entries()), 0)
