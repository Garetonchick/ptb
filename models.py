from sqlalchemy import String, DateTime
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column

class Base(DeclarativeBase):
    pass    

class Mirror(Base):
    __tablename__ = "mirror"

    id : Mapped[int] = mapped_column(primary_key=True)
    tg_mirror_id = mapped_column(String(66))
    vk_group_id = mapped_column(String(66))
    vk_group_name = mapped_column(String(66)) 
    start_datetime = mapped_column(DateTime())
    
    def __repr__(self):
        return f"""
            Mirror(
                id={self.id}, 
                tg_mirror_id={self.tg_mirror_id},
                vk_group_id={self.vk_group_id},
                vk_group_name={self.vk_group_name},
                start_datetime={self.start_datetime}
            )
        """

engine = create_engine("sqlite+pysqlite:///:memory:", echo=True)
Base.metadata.create_all(engine)
