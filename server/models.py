from sqlalchemy import INTEGER, Column, ForeignKey, String
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class BaseModel(Base):
    __abstract__ = True
    id = Column(INTEGER(), primary_key=True)

student = BaseModel

class Category(BaseModel):
    __table__name = "category"
    name = Column(String())
    brand = relationship("Brand")

class Brand(BaseModel):
    __table__name = "brand"
    name = Column(String())
    item = relationship("Item")

class Item(BaseModel):
    __table__name = "item"
    name = Column(String())
