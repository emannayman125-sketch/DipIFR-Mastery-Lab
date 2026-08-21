from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from ..db import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def is_valid(self) -> bool:
        expires = self.expires_at
        if expires.tzinfo is None:
            # SQLite drops tzinfo on round-trip; treat naive values as UTC
            # since that's how refresh_token_expiry() always writes them.
            expires = expires.replace(tzinfo=timezone.utc)
        return not self.revoked and expires > datetime.now(timezone.utc)
