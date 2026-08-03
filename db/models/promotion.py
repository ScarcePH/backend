from db.database import db


class Promotion(db.Model):
    __tablename__ = "promotions"
    __table_args__ = (
        db.CheckConstraint("end_date >= start_date", name="ck_promotions_date_range"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    start_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=False, index=True)
    early_ended_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=db.func.now(),
        onupdate=db.func.now(),
        nullable=False,
    )

    items = db.relationship(
        "PromotionItem",
        back_populates="promotion",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PromotionItem.id",
    )

