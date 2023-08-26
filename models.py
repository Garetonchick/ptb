from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    Table,
    Column,
    create_engine
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship
)
from sqlalchemy.engine import URL


class Base(DeclarativeBase):
    pass


channel_user_mtm_table = Table(
    "association_table",
    Base.metadata,
    Column("left_id", ForeignKey("channel.id"), primary_key=True),
    Column("right_id", ForeignKey("user.id"), primary_key=True),
)


class Mirror(Base):
    __tablename__ = "mirror"

    id: Mapped[int] = mapped_column(primary_key=True)
    vk_group_id = mapped_column(String(64))
    vk_group_name = mapped_column(String(64))
    start_datetime = mapped_column(DateTime())
    channel_id = mapped_column(ForeignKey("channel.id"))
    channel = relationship("Channel", back_populates="mirror")
    posts = relationship("Post", back_populates="mirror")

    def __repr__(self):
        return f"""
            Mirror(
                id={self.id},
                vk_group_id={self.vk_group_id},
                vk_group_name={self.vk_group_name},
                start_datetime={self.start_datetime}
                channel_id={self.channel_id},
                channel={self.channel},
                posts={self.posts}
            )
        """


class Channel(Base):
    __tablename__ = "channel"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_channel_id = mapped_column(String(64))
    tg_channel_name = mapped_column(String(64))
    mirror = relationship("Mirror", back_populates="channel")
    users = relationship(
        "User",
        secondary=channel_user_mtm_table,
        back_populates="channels"
    )

    def __repr__(self):
        return f"""
            Channel(
                id={self.id},
                tg_channel_id={self.tg_channel_id},
                mirror_id={self.mirror_id},
                mirror={self.mirror},
                users={self.users}
            )
        """


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_user_id = mapped_column(String(64))
    channels = relationship(
        "Channel",
        secondary=channel_user_mtm_table,
        back_populates="users"
    )

    def __repr__(self):
        return f"""
            User(
                id={self.id},
                tg_user_id={self.tg_user_id},
                channels={self.channels}
            )
        """


class Post(Base):
    __tablename__ = "post"

    id: Mapped[int] = mapped_column(primary_key=True)
    posted_datetime = mapped_column(DateTime())
    vk_post_id = mapped_column(String(64))
    tg_post_id = mapped_column(String(64))
    mirror_id = mapped_column(ForeignKey("mirror.id"))
    mirror = relationship(
        "Mirror",
        uselist=False,
        back_populates="posts"
    )
    comments = relationship("Comment", back_populates="post")


class Comment(Base):
    __tablename__ = "comment"

    id: Mapped[int] = mapped_column(primary_key=True)
    vk_comment_id = mapped_column(String(64))
    tg_comment_id = mapped_column(String(64))
    commented_datetime = mapped_column(DateTime())
    post_id = mapped_column(ForeignKey("post.id"))
    post = relationship("Post", back_populates="comments")


engine = None


def init(username, host, database, password, port='5432', create_scheme=True):
    global engine
    url = URL.create(
        drivername="postgresql",
        username=username,
        host=host,
        database=database,
        password=password,
        port=port
    )

    engine = create_engine(url, echo=True)
    if create_scheme:
        Base.metadata.create_all(engine)
