import os
import uuid
import json
import tempfile

import streamlit as st

from pages.helper import db_queries
from pages.helper.data_models import PublicSubmissions
from pages.helper.utils import (
    image_obj_to_numpy,
    extract_face_mesh_landmarks,
    extract_unique_faces_from_video,
)

st.set_page_config("Public Portal — Sighting & Track Report", initial_sidebar_state="collapsed")

db_queries.create_db()

tab_sighting, tab_track = st.tabs(["📸 Report a Sighting", "🔎 Track Report"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: Report a Sighting
# ══════════════════════════════════════════════════════════════════════════════
with tab_sighting:
    st.title("Report a Sighting")

    upload_mode = st.radio(
        "Upload type",
        options=["Image", "Video"],
        horizontal=True,
    )

    image_col, form_col = st.columns(2)
    save_flag = 0
    extracted_faces = []  # list of (landmarks, frame_rgb) for video mode
    face_mesh = None  # single face for image mode
    face_detected = False
    unique_id = None
    uploaded_file_path = None

    # ── Image upload ──────────────────────────────────────────────────────────
    if upload_mode == "Image":
        with image_col:
            image_obj = st.file_uploader(
                "Upload photo", type=["jpg", "jpeg", "png"], key="user_submission_img"
            )
            if image_obj:
                unique_id = str(uuid.uuid4())

                with st.spinner("Processing..."):
                    os.makedirs("./resources", exist_ok=True)
                    uploaded_file_path = "./resources/" + unique_id + ".jpg"
                    with open(uploaded_file_path, "wb") as f:
                        f.write(image_obj.read())

                    image_obj.seek(0)
                    st.image(image_obj, width=200)
                    image_obj.seek(0)
                    image_numpy = image_obj_to_numpy(image_obj)
                    face_mesh = extract_face_mesh_landmarks(image_numpy)

                    if face_mesh is None:
                        if uploaded_file_path and os.path.exists(uploaded_file_path):
                            os.remove(uploaded_file_path)
                    else:
                        face_detected = True
                        st.success("✅ Face detected.")

        if image_obj and face_detected:
            with form_col.form(key="image_submission_form"):
                sub_name = st.text_input("Your Name *")
                mobile_number = st.text_input("Your Mobile Number * (10 digits)")
                email = st.text_input("Your Email")
                address = st.text_input("Location where person was seen *")
                birth_marks = st.text_input("Birth Marks / Identifying Features")

                submit_bt = st.form_submit_button("Submit")

                if submit_bt:
                    errors = []
                    if not sub_name.strip():
                        errors.append("❌ Your Name is required.")
                    if not mobile_number.strip():
                        errors.append("❌ Mobile Number is required.")
                    elif (
                        not mobile_number.strip().isdigit()
                        or len(mobile_number.strip()) != 10
                    ):
                        errors.append("❌ Mobile Number must be exactly 10 digits.")
                    if not address.strip():
                        errors.append("❌ Location is required.")

                    if errors:
                        for err in errors:
                            st.error(err)
                    else:
                        details = PublicSubmissions(
                            submitted_by=sub_name.strip(),
                            location=address.strip(),
                            email=email.strip() or None,
                            face_mesh=json.dumps(face_mesh),
                            id=unique_id,
                            mobile=mobile_number.strip(),
                            birth_marks=birth_marks.strip() or None,
                            status="NF",
                        )
                        db_queries.new_public_case(details)
                        save_flag = 1

            if save_flag == 1:
                st.success("✅ Submission received. Thank you!")

    # ── Video upload ──────────────────────────────────────────────────────────
    else:
        with image_col:
            video_obj = st.file_uploader(
                "Upload video", type=["mp4", "mov", "avi"], key="user_submission_video"
            )
            if video_obj:
                with st.spinner("Extracting faces from video..."):
                    suffix = "." + video_obj.name.rsplit(".", 1)[-1]
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(video_obj.read())
                        tmp_path = tmp.name

                    extracted_faces = extract_unique_faces_from_video(tmp_path)
                    os.unlink(tmp_path)

                    if not extracted_faces:
                        st.error(
                            "❌ No faces detected in the video.\n\n"
                            "**Tips:** ensure the video shows a clear front-facing view "
                            "of the person's face in good lighting."
                        )
                    else:
                        st.success(f"✅ Found {len(extracted_faces)} unique face(s).")
                        st.caption("Detected faces:")
                        thumb_cols = st.columns(min(len(extracted_faces), 4))
                        for idx, (_, frame_rgb) in enumerate(extracted_faces):
                            thumb_cols[idx % 4].image(frame_rgb, width=100)

        if extracted_faces:
            with form_col.form(key="video_submission_form"):
                sub_name = st.text_input("Your Name *")
                mobile_number = st.text_input("Your Mobile Number * (10 digits)")
                email = st.text_input("Your Email")
                address = st.text_input("Location where person was seen *")
                birth_marks = st.text_input("Birth Marks / Identifying Features")

                submit_bt = st.form_submit_button(f"Submit {len(extracted_faces)} face(s)")

                if submit_bt:
                    errors = []
                    if not sub_name.strip():
                        errors.append("❌ Your Name is required.")
                    if not mobile_number.strip():
                        errors.append("❌ Mobile Number is required.")
                    elif (
                        not mobile_number.strip().isdigit()
                        or len(mobile_number.strip()) != 10
                    ):
                        errors.append("❌ Mobile Number must be exactly 10 digits.")
                    if not address.strip():
                        errors.append("❌ Location is required.")

                    if errors:
                        for err in errors:
                            st.error(err)
                    else:
                        count = 0
                        for landmarks, _ in extracted_faces:
                            sub_id = str(uuid.uuid4())
                            details = PublicSubmissions(
                                submitted_by=sub_name.strip(),
                                location=address.strip(),
                                email=email.strip() or None,
                                face_mesh=json.dumps(landmarks),
                                id=sub_id,
                                mobile=mobile_number.strip(),
                                birth_marks=birth_marks.strip() or None,
                                status="NF",
                            )
                            db_queries.new_public_case(details)
                            count += 1
                        st.success(f"✅ {count} submission(s) received. Thank you!")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: Track Report (Docket Number & Progress Tracker)
# ══════════════════════════════════════════════════════════════════════════════
with tab_track:
    st.title("🔎 Track Report")
    st.write("Enter your **Docket Number** to check the live progress of your missing person report.")

    STAGES = [
        "Case Registered",
        "Under Verification",
        "Investigation in Progress",
        "Search in Progress",
        "Person Found",
        "Case Closed",
    ]

    with st.form("public_track_report_form"):
        pub_docket = st.text_input(
            "Docket Number *",
            placeholder="e.g. MP-20261118-ABC123",
        )
        track_btn = st.form_submit_button("Track Progress", type="primary")

    if track_btn:
        if not pub_docket.strip():
            st.warning("Please enter your Docket Number.")
        else:
            case = db_queries.get_case_by_docket(pub_docket)
            if not case:
                st.error("No report found for this Docket Number. Please check and try again.")
            else:
                st.success(f"Report found: **{case.docket_no}**")
                current_stage = case.progress_stage or "Case Registered"
                stage_idx = STAGES.index(current_stage) if current_stage in STAGES else 0
                progress_pct = int(((stage_idx + 1) / len(STAGES)) * 100)

                c1, c2 = st.columns(2)
                c1.metric("Status", "Person Found" if case.status == "F" else "Search Ongoing")
                c2.metric("Current Progress", current_stage)
                st.progress(progress_pct / 100, text=f"Progress: {progress_pct}%")

                st.write(f"**Person's Name:** {case.name}")
                st.write(f"**City:** {case.city or 'Not specified'}")
                st.write(f"**Last Seen:** {case.last_seen}")
                st.write(
                    f"**Registered On:** "
                    f"{case.submitted_on.strftime('%d %b %Y, %I:%M %p') if case.submitted_on else 'N/A'}"
                )
                if case.progress_note:
                    st.info(f"**Latest Update:** {case.progress_note}")

                st.markdown("### Progress Timeline")
                for i, stage in enumerate(STAGES):
                    if stage == current_stage:
                        st.markdown(f"🟢 **{stage}** — *(Current Stage)*")
                    elif i < stage_idx:
                        st.markdown(f"✅ {stage}")
                    else:
                        st.markdown(f"⚪ {stage}")
