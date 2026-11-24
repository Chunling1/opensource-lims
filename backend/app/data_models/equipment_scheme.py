"""Department-owned reusable instrument combinations, independent of reports."""
from ..extensions import db
from ..models import JSONText


class EquipmentScheme(db.Model):
    __tablename__ = "equipment_schemes"
    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    equipment_ids = db.Column(JSONText, nullable=False)
    project_ids = db.Column(JSONText, nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    department = db.relationship("Department")
    __table_args__ = (db.UniqueConstraint("department_id", "name", name="uq_equipment_scheme_department_name"),)

    def to_row(self):
        return dict(id=self.id, departmentId=self.department_id, department=self.department.name,
                    name=self.name, equipmentIds=self.equipment_ids or [], projectIds=self.project_ids or [],
                    enabled=self.enabled, version=self.version)
