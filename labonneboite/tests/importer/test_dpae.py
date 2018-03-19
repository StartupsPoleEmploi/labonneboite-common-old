from labonneboite.importer.jobs import check_dpae
from labonneboite.importer.jobs import extract_dpae
from labonneboite.importer.models.computing import Hiring
from labonneboite.importer.util import get_departement_from_zipcode
from .test_base import DatabaseTest


class TestDpae(DatabaseTest):

    def test_check_dpae(self):
        filename = self.get_data_file_path("LBB_XDPDPA_DPAE_20151010_20161110_20161110_174915.csv")
        check_dpae.check_file(filename)
        self.assertEquals(Hiring.query.count(), 0)

    def test_extract_dpae(self):
        self.assertEquals(Hiring.query.count(), 0)
        filename = self.get_data_file_path("LBB_XDPDPA_DPAE_20151010_20161110_20161110_174915.csv")
        task = extract_dpae.DpaeExtractJob(filename)
        task.run()
        self.assertEquals(Hiring.query.count(), 6)

    def test_extract_dpae_two_files_diff(self):
        # Second file contains duplicated records and one record from the future and only 2 really new valid records.
        filename_first_month = self.get_data_file_path("LBB_XDPDPA_DPAE_20151010_20161110_20161110_174915.csv")
        filename_second_month = self.get_data_file_path("LBB_XDPDPA_DPAE_20151110_20161210_20161210_094110.csv")
        task = extract_dpae.DpaeExtractJob(filename_first_month)
        task.run()
        self.assertEquals(Hiring.query.count(), 6)
        task = extract_dpae.DpaeExtractJob(filename_second_month)
        task.run()
        self.assertEquals(Hiring.query.count(), 6+2)

    def test_extract_departement(self):
        departement = get_departement_from_zipcode("6600")
        self.assertEqual(departement, "06")

    def test_extract_gz_format(self):
        filename = self.get_data_file_path("LBB_XDPDPA_DPAE_20151010_20161110_20161110_174915.csv.gz")
        task = extract_dpae.DpaeExtractJob(filename)
        task.run()
        self.assertEquals(Hiring.query.count(), 6)

    def test_extract_bz2_format(self):
        filename = self.get_data_file_path("LBB_XDPDPA_DPAE_20151010_20161110_20161110_174915.csv.bz2")
        task = extract_dpae.DpaeExtractJob(filename)
        task.run()
        self.assertEquals(Hiring.query.count(), 6)
