from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    Table,
    Column,
    Integer,
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
    "channel_user_mtm_table",
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
    tg_linked_chat_id = mapped_column(String(64))
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
                tg_linked_chat_id={self.tg_linked_chat_id},
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
    vk_owner_id = mapped_column(String(64))
    tg_post_id = mapped_column(String(64))
    tg_linked_chat_post_id = mapped_column(String(64))
    comments_offset = mapped_column(Integer(), default=0)
    mirror_id = mapped_column(ForeignKey("mirror.id"))
    mirror = relationship(
        "Mirror",
        uselist=False,
        back_populates="posts"
    )
    comments = relationship("Comment", back_populates="post")

    def __repr__(self):
        return f"""
            Post(
                id={self.id},
                posted_datetime={self.posted_datetime},
                vk_post_id={self.vk_post_id},
                vk_owner_id={self.vk_owner_id},
                tg_post_id={self.tg_post_id},
                tg_linked_chat_post_id={self.tg_linked_chat_post_id},
                comments_offset={self.comments_offset},
                mirror_id={self.mirror_id},
                mirror={self.mirror},
                comments={self.comments}
            )
        """


class Comment(Base):
    __tablename__ = "comment"

    id: Mapped[int] = mapped_column(primary_key=True)
    vk_comment_id = mapped_column(String(64))
    tg_comment_id = mapped_column(String(64))
    commented_datetime = mapped_column(DateTime())
    post_id = mapped_column(ForeignKey("post.id"))
    post = relationship("Post", back_populates="comments")

    def __repr__(self):
        return f"""
            Comment(
                id={self.id},
                vk_comment_id={self.vk_comment_id},
                tg_comment_id={self.tg_comment_id},
                commented_datetime={self.commented_datetime},
                post_id={self.post_id},
                post={self.post}
            )
        """


engine = None


def init(
        username,
        host,
        database,
        password,
        port='5432',
        create_scheme=True,
        echo=False
):
    global engine
    url = URL.create(
        drivername="postgresql",
        username=username,
        host=host,
        database=database,
        password=password,
        port=port
    )
    engine = create_engine(url, echo=echo)

    if create_scheme:
        while True:
            try:
                Base.metadata.create_all(engine)
                break
            except:
                print("Failed to connect to db. Retrying...")
