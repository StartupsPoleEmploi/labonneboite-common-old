import re
import datetime
from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy import Column, ForeignKey
from sqlalchemy import desc
from sqlalchemy.orm import relationship
from sqlalchemy.dialects import mysql

from labonneboite_common.models.base import CRUDMixin
from labonneboite_common.database import Base
from labonneboite_common.models import OfficeAdminUpdate, OfficeUpdateMixin


class OfficeThirdPartyUpdate(OfficeUpdateMixin, CRUDMixin, Base):

    __tablename__ = 'etablissements_third_party_update'
    id = Column(Integer, primary_key=True)
