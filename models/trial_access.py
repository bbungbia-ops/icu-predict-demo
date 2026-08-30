"""Trial-access rules shared by the clinical routes.

The limits deliberately live on the organization, not on a browser session or
individual user. A newly registered organization therefore starts with an
empty workspace and cannot bypass the commercial flow by adding more users.
"""

from __future__ import annotations


def has_full_access(role: str | None, license_valid: bool) -> bool:
    """System administrators and active-license organizations are unlimited."""
    return role == 'admin' or bool(license_valid)


def get_trial_status(
    connection,
    organization_id: int | None,
    *,
    role: str | None,
    license_valid: bool,
    patient_limit: int,
    assessment_limit: int,
) -> dict:
    """Return presentation-safe trial usage for one organization."""
    full_access = has_full_access(role, license_valid)
    if not organization_id:
        return {
            'full_access': full_access,
            'is_trial': not full_access,
            'patient_count': 0,
            'assessment_count': 0,
            'patient_limit': patient_limit,
            'assessment_limit': assessment_limit,
            'remaining_patients': 0,
            'remaining_assessments': 0,
            'can_add_patient': full_access,
            'can_create_assessment': full_access,
            'is_exhausted': not full_access,
        }

    patient_count = int(connection.execute(
        'SELECT COUNT(*) FROM patients WHERE organization_id = ?', (organization_id,)
    ).fetchone()[0])
    assessment_count = int(connection.execute(
        'SELECT COUNT(*) FROM predictions WHERE organization_id = ?', (organization_id,)
    ).fetchone()[0])
    remaining_patients = max(patient_limit - patient_count, 0)
    remaining_assessments = max(assessment_limit - assessment_count, 0)
    return {
        'full_access': full_access,
        'is_trial': not full_access,
        'patient_count': patient_count,
        'assessment_count': assessment_count,
        'patient_limit': patient_limit,
        'assessment_limit': assessment_limit,
        'remaining_patients': remaining_patients,
        'remaining_assessments': remaining_assessments,
        'can_add_patient': full_access or remaining_patients > 0,
        'can_create_assessment': full_access or remaining_assessments > 0,
        'is_exhausted': not full_access and (
            remaining_patients == 0 or remaining_assessments == 0
        ),
    }
