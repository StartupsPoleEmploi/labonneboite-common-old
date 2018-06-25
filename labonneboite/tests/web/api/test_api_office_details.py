# coding: utf8

import json
from urllib.parse import urlencode

import mock

from labonneboite.tests.web.api.test_api_base import ApiBaseTest
from labonneboite.scripts import create_index as script
from labonneboite.common.models import OfficeAdminUpdate


class ApiOfficeDetailsTest(ApiBaseTest):

    def test_query_office(self):
        """
        Test the `office_details` API route.
        """
        expected_result = {
            'siret': '00000000000001',
            'naf': '7320Z',
            'name': 'OFFICE 1',
            'raison_sociale': 'Raison sociale 1',
            'naf_text': '\xc9tudes de march\xe9 et sondages',
            'url': 'http://%s/00000000000001/details' % self.TEST_SERVER_NAME,
            'lon': 6.0,
            'headcount_text': '10 à 19 salariés',
            'stars': 4.0,
            'social_network': '',
            'address': {
                'city': 'BAYONVILLE-SUR-MAD',
                'street_name': '',
                'street_number': '',
                'city_code': '54055',
                'zipcode': '54890'
            },
            'lat': 49.0,
        }
        params = self.add_security_params({'user': 'labonneboite'})
        rv = self.app.get('/api/v1/office/%s/details?%s' % (expected_result['siret'], urlencode(params)))
        self.assertEqual(rv.status_code, 200)
        data = json.loads(rv.data)
        self.assertDictEqual(data, expected_result)

    @mock.patch('labonneboite.conf.settings.API_INTERNAL_CONSUMERS', ['labonneboite'])
    def test_query_office_with_internal_user(self):
        """
        Test that internal services of Pôle emploi can have access to sensitive information.
        """
        params = self.add_security_params({'user': 'labonneboite'})
        rv = self.app.get('/api/v1/office/%s/details?%s' % ('00000000000001', urlencode(params)))
        self.assertEqual(rv.status_code, 200)
        data = json.loads(rv.data)
        self.assertIn('email', data)
        self.assertIn('phone', data)
        self.assertIn('website', data)

    def test_query_office_with_external_user(self):
        """
        Test that external services of Pôle emploi cannot have access to sensitive information.
        """
        params = self.add_security_params({'user': 'emploi_store_dev'})
        rv = self.app.get('/api/v1/office/%s/details?%s' % ('00000000000001', urlencode(params)))
        self.assertEqual(rv.status_code, 200)
        data = json.loads(rv.data)
        self.assertNotIn('email', data)
        self.assertNotIn('phone', data)
        self.assertNotIn('website', data)


    def test_update_office_remove_alternance_details(self):
        """
        Test `update_offices` to hide it on lba
        """
        siret = '00000000000011'

        # Remove alternance for this company
        # Note : we use 00000000000011 because score>50 & score_alternance>50
        office_to_update = OfficeAdminUpdate(
            sirets=siret,
            score_alternance=0,
        )

        office_to_update.save(commit=True)
        script.update_offices()

        # Available for LBB but not for LBA
        params = self.add_security_params({'user': 'emploi_store_dev'})
        rv = self.app.get('/api/v1/office/%s/details?%s' % (siret, urlencode(params)))
        self.assertEqual(rv.status_code, 200)

        params = self.add_security_params({'user': 'emploi_store_dev', 'contract':'alternance'})
        rv = self.app.get('/api/v1/office/%s/details?%s' % (siret, urlencode(params)))
        self.assertEqual(rv.status_code, 404)


    def test_update_office_remove_lbb_details(self):
        """
        Test `update_offices` to hide it on lbb
        """
        siret = '00000000000011'

        # Remove alternance for this company
        # Note : we use 00000000000011 because score>50 & score_alternance>50
        office_to_update = OfficeAdminUpdate(
            sirets=siret,
            score=0,
        )

        office_to_update.save(commit=True)
        script.update_offices()

        # Available for LBA but not for LBB
        params = self.add_security_params({'user': 'emploi_store_dev'})
        rv = self.app.get('/api/v1/office/%s/details?%s' % (siret, urlencode(params)))
        self.assertEqual(rv.status_code, 404)

        params = self.add_security_params({'user': 'emploi_store_dev', 'contract':'alternance'})
        rv = self.app.get('/api/v1/office/%s/details?%s' % (siret, urlencode(params)))
        self.assertEqual(rv.status_code, 200)
