import os
import sqlite3
from datetime import datetime
from sqlmodel import create_engine, Session, select

from pages.helper.data_models import RegisteredCases, PublicSubmissions

sqlite_url = "sqlite:///sqlite_database.db"
engine = create_engine(sqlite_url)


def generate_docket_number(case_id: str, submitted_on: datetime = None) -> str:
    """Generate a human-friendly docket number in the format MP-YYYYMMDD-XXXXXX."""
    dt = submitted_on or datetime.now()
    short_id = str(case_id).replace("-", "")[:6].upper()
    return f"MP-{dt.strftime('%Y%m%d')}-{short_id}"


def create_db():
    try:
        RegisteredCases.__table__.create(engine)
        PublicSubmissions.__table__.create(engine)
    except Exception:
        pass
    # Add new columns to existing tables if they don't exist (SQLite migration)
    _migrate_db()


def _migrate_db():
    """Add any new columns to existing tables without dropping data and backfill docket numbers."""
    new_columns = [
        ("registeredcases", "complainant_email", "TEXT"),
        ("registeredcases", "city", "TEXT"),
        ("registeredcases", "description", "TEXT"),
        ("registeredcases", "docket_no", "TEXT"),
        ("registeredcases", "progress_stage", "TEXT NOT NULL DEFAULT 'Case Registered'"),
        ("registeredcases", "progress_note", "TEXT"),
    ]
    try:
        con = sqlite3.connect("sqlite_database.db")
        cursor = con.cursor()
        for table, column, col_type in new_columns:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            except sqlite3.OperationalError:
                pass  # Column already exists

        # Backfill docket_no for any legacy cases missing one
        try:
            rows = cursor.execute(
                "SELECT id, submitted_on FROM registeredcases WHERE docket_no IS NULL OR docket_no = ''"
            ).fetchall()
            for row_id, sub_on in rows:
                dt = None
                if sub_on:
                    try:
                        dt = datetime.fromisoformat(str(sub_on).split(".")[0])
                    except Exception:
                        dt = None
                docket = generate_docket_number(row_id, dt)
                cursor.execute(
                    "UPDATE registeredcases SET docket_no = ? WHERE id = ?",
                    (docket, row_id),
                )
        except Exception:
            pass

        con.commit()
        con.close()
    except Exception:
        pass


def register_new_case(case_details: RegisteredCases) -> str:
    if not case_details.docket_no:
        case_details.docket_no = generate_docket_number(
            case_details.id, case_details.submitted_on
        )
    if not case_details.progress_stage:
        case_details.progress_stage = "Case Registered"
    with Session(engine) as session:
        session.add(case_details)
        session.commit()
        session.refresh(case_details)
    return case_details.docket_no


def get_case_by_docket(docket_no: str):
    if not docket_no or not docket_no.strip():
        return None
    with Session(engine) as session:
        return session.exec(
            select(RegisteredCases).where(
                RegisteredCases.docket_no == docket_no.strip().upper()
            )
        ).first()


def update_case_progress(docket_no: str, progress_stage: str, progress_note: str = "") -> bool:
    if not docket_no or not docket_no.strip():
        return False
    with Session(engine) as session:
        case = session.exec(
            select(RegisteredCases).where(
                RegisteredCases.docket_no == docket_no.strip().upper()
            )
        ).first()
        if not case:
            return False
        case.progress_stage = progress_stage
        case.progress_note = progress_note.strip() if progress_note and progress_note.strip() else None
        if progress_stage in ("Person Found", "Case Closed"):
            case.status = "F"
        elif case.status == "F" and progress_stage not in ("Person Found", "Case Closed"):
            case.status = "NF"
        session.add(case)
        session.commit()
        return True


def fetch_registered_cases(submitted_by: str, status: str):
    print(f"submitted_by: {submitted_by}")
    if status == "All":
        status = ["F", "NF"]
    elif status == "Found":
        status = ["F"]
    elif status == "Not Found":
        status = ["NF"]

    with Session(engine) as session:
        result = session.exec(
            select(
                RegisteredCases.id,
                RegisteredCases.name,
                RegisteredCases.age,
                RegisteredCases.status,
                RegisteredCases.last_seen,
                RegisteredCases.docket_no,
                RegisteredCases.progress_stage,
                RegisteredCases.matched_with,
            )
            .where(RegisteredCases.submitted_by == submitted_by)
            .where(RegisteredCases.status.in_(status))
        ).all()
        return result


def fetch_public_cases(train_data: bool, status: str):
    if train_data:
        with Session(engine) as session:
            result = session.exec(
                select(
                    PublicSubmissions.id,
                    PublicSubmissions.face_mesh,
                ).where(PublicSubmissions.status == status)
            ).all()
            return result

    with Session(engine) as session:
        result = session.exec(
            select(
                PublicSubmissions.id,
                PublicSubmissions.status,
                PublicSubmissions.location,
                PublicSubmissions.mobile,
                PublicSubmissions.birth_marks,
                PublicSubmissions.submitted_on,
                PublicSubmissions.submitted_by,
            )
        ).all()
        return result


def get_not_confirmed_registered_cases(submitted_by: str):
    with Session(engine) as session:
        result = session.exec(
            select(RegisteredCases)
            .where(RegisteredCases.submitted_by == submitted_by)
            .where(RegisteredCases.status == "NF")
        ).all()
        return result


def get_training_data(submitted_by: str):
    with Session(engine) as session:
        result = session.exec(
            select(RegisteredCases.id, RegisteredCases.face_mesh)
            .where(RegisteredCases.submitted_by == submitted_by)
            .where(RegisteredCases.status == "NF")
        ).all()
        return result


def new_public_case(public_case_details: PublicSubmissions):
    with Session(engine) as session:
        session.add(public_case_details)
        session.commit()


def get_public_case_detail(case_id: str):
    with Session(engine) as session:
        result = session.exec(
            select(
                PublicSubmissions.location,
                PublicSubmissions.submitted_by,
                PublicSubmissions.mobile,
                PublicSubmissions.birth_marks,
            ).where(PublicSubmissions.id == case_id)
        ).all()
        return result


def get_registered_case_detail(case_id: str):
    with Session(engine) as session:
        result = session.exec(
            select(
                RegisteredCases.name,
                RegisteredCases.complainant_mobile,
                RegisteredCases.complainant_email,
                RegisteredCases.age,
                RegisteredCases.last_seen,
                RegisteredCases.birth_marks,
            ).where(RegisteredCases.id == case_id)
        ).all()
        return result


def list_public_cases():
    with Session(engine) as session:
        result = session.exec(select(PublicSubmissions)).all()
        return result


def update_found_status(register_case_id: str, public_case_id: str):
    with Session(engine) as session:
        registered_case_details = session.exec(
            select(RegisteredCases).where(RegisteredCases.id == str(register_case_id))
        ).one()
        registered_case_details.status = "F"
        registered_case_details.matched_with = str(public_case_id)
        if registered_case_details.progress_stage != "Case Closed":
            registered_case_details.progress_stage = "Person Found"
        if not registered_case_details.progress_note:
            registered_case_details.progress_note = (
                "Match confirmed via AI Facial Recognition."
            )

        public_case_details = session.exec(
            select(PublicSubmissions).where(PublicSubmissions.id == str(public_case_id))
        ).one()
        public_case_details.status = "F"

        session.add(registered_case_details)
        session.add(public_case_details)
        session.commit()


def get_registered_cases_count(submitted_by: str, status: str):
    with Session(engine) as session:
        result = session.exec(
            select(RegisteredCases)
            .where(RegisteredCases.submitted_by == submitted_by)
            .where(RegisteredCases.status == status)
        ).all()
        return result


def get_case_counts_by_city():
    """Return a dict mapping city -> {found: int, not_found: int}."""
    with Session(engine) as session:
        result = session.exec(
            select(RegisteredCases.city, RegisteredCases.status)
        ).all()
    counts = {}
    for city, status in result:
        if not city:
            city = "Unknown"
        if city not in counts:
            counts[city] = {"found": 0, "not_found": 0}
        if status == "F":
            counts[city]["found"] += 1
        else:
            counts[city]["not_found"] += 1
    return counts


def delete_registered_case(case_id: str):
    with Session(engine) as session:
        case = session.exec(
            select(RegisteredCases).where(RegisteredCases.id == case_id)
        ).one()
        session.delete(case)
        session.commit()
    # Remove image from disk
    image_path = f"./resources/{case_id}.jpg"
    if os.path.exists(image_path):
        os.remove(image_path)


def update_registered_case(case_id: str, fields: dict):
    with Session(engine) as session:
        case = session.exec(
            select(RegisteredCases).where(RegisteredCases.id == case_id)
        ).one()
        for key, value in fields.items():
            setattr(case, key, value)
        session.add(case)
        session.commit()


if __name__ == "__main__":
    r = fetch_public_cases("NF", "NF")
    print(r)
