import datetime

from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy import desc
from sqlalchemy import BigInteger, String, DateTime
from sqlalchemy.orm import relationship

from labonneboite_common.database import Base
from labonneboite_common.database import db_session
from labonneboite_common.models.base import CRUDMixin
from labonneboite_common.env import get_current_env, ENV_BONAPARTE


class HistoryBlacklist(CRUDMixin, Base):
    __tablename__ = 'history_blacklist'

    id = Column("id", BigInteger, primary_key=True)
    email = Column(String(191), default='', nullable=False)
    datetime_removal = Column("datetime_removal", DateTime, nullable=False)
