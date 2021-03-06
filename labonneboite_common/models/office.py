from functools import lru_cache
import logging
from typing import Any, Optional, Sequence

from babel.dates import format_date
from flask import url_for
from slugify import slugify
from sqlalchemy import PrimaryKeyConstraint, Index
from werkzeug import cached_property

from labonneboite_common import encoding as encoding_util
from labonneboite_common import hiring_type_util
from labonneboite_common import mapping as mapping_util
from labonneboite_common import scoring as scoring_util
from labonneboite_common import util
from labonneboite_common.database import Base, db_session, DATABASE
from labonneboite_common.load_data import load_city_codes, load_groupements_employeurs
from labonneboite_common.models.base import CRUDMixin
from labonneboite_common.conf import settings

from labonneboite_common.models import FinalOfficeMixin, OfficeAdminUpdate

logger = logging.getLogger('main')

CITY_NAMES = load_city_codes()


class Office(FinalOfficeMixin, CRUDMixin, Base):
    """
    An office.

    Warning: the table behind this model is regularly entirely dropped and recreated
    at the end of an importer cycle when a new dataset is deployed (once a month in theory).
    For this reason, it is very important that Office and ExportableOffice are kept 100% in
    sync, i.e. have the exact same columns.

    For example, if you want to add a new column, first be sure to give it a default value,
    as when the importer imports a new office dataset, this column will be entirely populated
    by this default value.

    Do *not* add this new column here in this model, but rather in the proper Mixin above,
    take time to read each Mixin role and choose the right one for your need.

    Then you need to add a migration to create this column in each relevant model,
    not just the Office model, see your Mixin documentation for the list of models.

    You also need to add this new column in the method:
    - importer.util.get_select_fields_for_main_db

    Then, be sure to double check that both `make run_importer_jobs` and
    `make test_all` complete successfully.
    """

    __tablename__ = settings.OFFICE_TABLE

    __table_args__ = (
        PrimaryKeyConstraint('siret'),

        # Improve performance of create_index.py parallel jobs
        # by quickly fetching all offices of any given departement.
        Index('_departement', 'departement'),

        # Improve performance of create_index.py remove_scam_emails()
        # by quickly locating offices having a given scam email.
        Index('_email', 'email'),
    )

    # You should normally *not* add any column here - see documentation above.

    def __unicode__(self):
        return "%s - %s" % (self.siret, self.name)

    def as_json(
        self,
        rome_codes: Optional[Sequence[str]] = None,
        hiring_type=None,
        distance=None,
        zipcode=None,
        extra_query_string=None,
    ):
        """
        `rome_codes`: optional parameter, used only in case of being in the context
        of a search by ROME codes (single rome or multi rome).
        Without the context of ROME codes, the general purpose score of the office
        is returned.
        With the context of ROME codes, the score returned is adjusted to the ROME code,
        and the URL of the company page is also adjusted to keep the same context.
        Main case is results returned by an API search. The scores and URLs embedded
        in the company objects should be adjusted to the ROME code context.

        `hiring_type`: is needed along rome_codes to compute the right corresponding score,
        possible values are hiring_type_util.VALUES

        `distance` and `zipcode`: needed for potential multi geolocation logic.

        `extra_query_string` (dict): extra query string to be added to the API
        urls for each office. Typically some Google Analytics trackers.
        """
        rome_code = self.get_matched_rome(rome_codes)

        alternance = hiring_type == hiring_type_util.ALTERNANCE

        extra_query_string = extra_query_string or {}
        json = dict(
            address=self.address_as_text,
            city=self.city,
            headcount_text=self.headcount_text,
            lat=self.y,
            lon=self.x,
            naf=self.naf,
            naf_text=self.naf_text,
            name=self.name,
            siret=self.siret,
            stars=self.get_stars_for_rome_code(rome_code, hiring_type),
            url=self.get_url_for_rome_code(rome_code, alternance, **extra_query_string),
            contact_mode=util.get_contact_mode_for_rome_and_office(rome_code, self),
            social_network=self.social_network or '',
            alternance=False,
        )

        # Warning: the `distance`, `boost` and `matched_rome` fields are added by `get_offices_from_es_and_db`,
        # they are NOT model fields or properties!
        if rome_code:
            json['matched_rome_code'] = rome_code
            json['matched_rome_label'] = settings.ROME_DESCRIPTIONS[rome_code]
            json['matched_rome_slug'] = slugify(settings.ROME_DESCRIPTIONS[rome_code])

        # offers* fields are added by VisibleMarketFetcher.get_offices,
        # they are NOT model fields or properties
        # This message should concern only a small number of companies who explicitly requested
        # to appear in extra geolocations.
        if any([distance, zipcode]) and json['address'] and self.show_multi_geolocations_msg(distance, zipcode):
            json['address'] += ", Cette entreprise recrute aussi dans votre r??gion."
        return json

    def get_matched_rome(self, rome_codes: Sequence[str]):
        if rome_codes is None:  # no rome search context
            rome_code = None
        elif len(rome_codes) == 1:  # single rome search context
            rome_code = rome_codes[0]
        else:
            raise NotImplementedError()
        return rome_code

    @property
    def address_fields(self):
        result = []
        if not self.is_small:
            result.append("Service des ressources humaines")
        if self.street_name:
            result.append('%s %s' % (self.street_number, self.street_name))
        result.append('%s %s' % (self.zipcode, self.city))
        return result

    @property
    def address_as_text(self):
        if self.address_fields:
            return ", ".join([f for f in self.address_fields if f is not None])
        return None

    @property
    def phone(self):
        has_phone = self.tel and not self.tel.isspace()
        if has_phone:
            # not sure why, the import botched the phone number...
            if self.tel[-2] == '.':
                s = '0%s' % self.tel[:-2]
                return " ".join(s[i:i + 2] for i in range(0, len(s), 2))
            return self.tel
        return None

    @property
    def name(self):
        if self.office_name:
            result = self.office_name.upper()
        elif self.company_name:
            result = self.company_name.upper()
        else:
            result = 'sans nom'
        return encoding_util.sanitize_string(result)

    @property
    def google_url(self):
        google_search = "%s+%s" % (self.name.replace(' ', '+'), self.city.replace(' ', '+'))
        return "https://www.google.fr/search?q=%s" % google_search

    @property
    def kompass_url(self):
        return "http://fr.kompass.com/searchCompanies?text=%s" % self.siret

    @property
    def is_groupement_employeurs(self):
        """
        A "groupement d'employeurs" is a French-only juridical entity
        which is basically a collection of offices.
        """
        return self.siret in load_groupements_employeurs()

    @property
    def is_removed_from_lba(self):
        """
        Returns True if the company has explicitly asked via SAVE
        to be removed from LBA.
        """
        if self.score_alternance > 0:
            return False
        # office.score_alternance == 0 does not guarantee the office has
        # been removed via SAVE from LBA as many offices "naturally" have
        # such a score.
        # We still have to check that there actually is a SAVE record
        # specifically asking for this removal.
        office_admin_update = OfficeAdminUpdate.query.filter(OfficeAdminUpdate.sirets.like("%{}%".format(
            self.siret))).filter_by(score_alternance=0).first()
        return bool(office_admin_update)

    @property
    def headcount_text(self):
        try:
            return settings.HEADCOUNT_INSEE[self.headcount]
        except KeyError:
            return ''

    @property
    def is_small(self):
        try:
            return int(self.headcount) < settings.HEADCOUNT_SMALL_ONLY_MAXIMUM
        except (ValueError, TypeError):
            return True

    def has_city(self):
        try:
            city = bool(CITY_NAMES[self.city_code])
        except KeyError:
            if self.city_code.startswith('75'):
                city = True
            else:
                city = None
        return city

    @property
    def city(self):
        try:
            return CITY_NAMES[self.city_code]
        except KeyError:
            if self.city_code.startswith('75'):
                return 'Paris'
            else:
                raise

    @property
    def naf_text(self):
        return settings.NAF_CODES[self.naf]

    @property
    def stars(self):
        return self.get_stars_for_rome_code(None)

    @cached_property
    def romes_for_naf_mapping(self):
        """
        Returns a list of named tuples for ROME codes matching the company's NAF code.
        """
        return mapping_util.romes_for_naf(self.naf)

    @cached_property
    def romes_codes(self):
        """
        Returns the default set of ROME codes for the current company.
        """
        return set([rome.code for rome in self.romes_for_naf_mapping])

    def get_score_for_rome_code(self, rome_code: Optional[str], hiring_type: Optional[str] = None):
        hiring_type = hiring_type or hiring_type_util.DEFAULT
        if hiring_type not in hiring_type_util.VALUES:
            raise ValueError("Unknown hiring_type")
        raw_score = self.score if hiring_type == hiring_type_util.DPAE else self.score_alternance
        return scoring_util.get_score_adjusted_to_rome_code_and_naf_code(score=raw_score,
                                                                         rome_code=rome_code,
                                                                         naf_code=self.naf)

    def get_stars_for_rome_code(self, rome_code: Optional[str], hiring_type: Optional[str] = None):
        score = self.get_score_for_rome_code(rome_code, hiring_type)
        return scoring_util.get_stars_from_score(score)

    def get_stars_for_rome_code_as_percentage(self, rome_code: Optional[str]):
        """
        Converts the number of stars adjusted to given rome_code to a percentage.
        """
        return (100 * self.get_stars_for_rome_code(rome_code)) / 5

    @property
    def url(self):
        """
        Returns the URL of the `details` page or `None` if we are outside of a Flask's application context.
        """
        return self.get_url_for_rome_code(None)

    def get_url_for_rome_code(self, rome_code: Optional[str], alternance=False, **query_string):
        try:
            if rome_code:
                return url_for('office.details',
                               siret=self.siret,
                               rome_code=rome_code,
                               _external=True,
                               contract='alternance' if alternance else None,
                               **query_string)
            return url_for('office.details',
                           siret=self.siret,
                           contract='alternance' if alternance else None,
                           _external=True,
                           **query_string)
        except RuntimeError:
            # RuntimeError is raised when we are outside of a Flask's application context.
            # Here, we cannot properly generate an URL via url_for.
            return None

    def show_multi_geolocations_msg(self, distance: Optional[int] = None, zipcode: Optional[str] = None):
        """
        Returns True if a message that indicates that the current office recruits beyond
        the boundaries of its own departement should be displayed, False otherwise.

        This message should concern only a small number of companies who explicitly requested
        to appear in extra geolocations.
        """
        if self.has_multi_geolocations:
            # If the given `zipcode` is in the same departement: the message is unnecessary.
            if zipcode and zipcode.startswith(self.zipcode[:2]):
                return False
            return True
        return False

    @classmethod
    @lru_cache(maxsize=None)
    def get_date_of_last_data_deploy(cls):
        """
        Get date of when the 'etablissements' table was (re)created by the deploy_data process.

        Returns None if the information is not available.
        """
        query = """
            SELECT CREATE_TIME
                FROM information_schema.tables
                WHERE TABLE_SCHEMA = '%s'
                    AND TABLE_NAME = '%s';
        """ % (DATABASE['NAME'], settings.OFFICE_TABLE)

        last_data_deploy_date = db_session.execute(query).first()

        if last_data_deploy_date is None:
            return None

        last_data_deploy_date = last_data_deploy_date[0]

        # Formatting date in french format using locale.setlocale is strongly discouraged.
        # Using babel instead is the recommended way.
        # See https://stackoverflow.com/questions/985505/locale-date-formatting-in-python
        last_data_deploy_date_formated_as_french = format_date(last_data_deploy_date, locale='fr', format='long')
        return last_data_deploy_date_formated_as_french


class OfficeResult(Office):
    __abstract__ = True

    matched_rome: Optional[str] = None
    distance: Optional[float] = None
    boost: Optional[bool] = False
    offers_count: int
    position: int
    offers: Optional[Sequence[Any]]

    def __init__(self,
                 office: Office = None,
                 *,
                 offers_count: int = None,
                 position: int = None,
                 matched_rome: Optional[str] = None,
                 distance: Optional[float] = None,
                 boost: Optional[bool] = False,
                 offers: Optional[Sequence[Any]] = None,
                 **kwargs):
        # set office props in kwargs (to __init__ the super class)
        office_props = {}
        if office is not None:
            office_props = dict(office.__dict__)
            office_props.pop('_sa_instance_state', None)  # added by : self.__dict__
        office_props.update(kwargs)
        super(OfficeResult, self).__init__(**office_props)
        self.matched_rome = matched_rome
        self.distance = distance
        self.boost = boost
        self.offers_count = offers_count
        self.position = position
        self.offers = offers

    def as_json(self, *args, **kwargs):
        json = super().as_json(*args, **kwargs)
        if self.distance is not None:
            json['distance'] = self.distance

        json['boosted'] = self.boost
        if self.offers_count is not None:
            json['offers_count'] = self.offers_count

        if self.offers is not None:
            json['offers'] = self.offers

        return json

    def get_matched_rome(self, rome_codes: Sequence[str]):
        if rome_codes is None:  # no rome search context
            rome_code = None
        elif len(rome_codes) == 1:  # single rome search context
            rome_code = rome_codes[0]
        else:  # multi rome search context
            rome_code = self.matched_rome
        return rome_code
