"""A fictional personal-injury record set, with its ground truth.

Every person, provider, address and account number here is invented. The case
is built to contain the problems real record sets contain: a faxed duplicate,
a bill whose printed total is wrong, a visit billed but never documented, a
gap in treatment, and scanned pages that need OCR.
"""

FOOTER = "SAMPLE RECORD - fictional patient and providers - made for the Exhibit demo"

PATIENT = {"name": "Marisol Vega", "dob": "07/19/1988"}

ER = "Bayview Regional Medical Center"
IMAGING = "Coastline Imaging Associates"
ORTHO = "Pacific Spine & Orthopedics"
PT = "Harbor Physical Therapy"


def _header(org: str, address: str, title: str) -> str:
    return f"""
<div class="org">{org}</div>
<div class="addr">{address}</div>
<div class="title">{title}</div>
<table class="meta">
<tr><td><b>Patient:</b> {PATIENT['name']}</td><td><b>DOB:</b> {PATIENT['dob']}</td></tr>
</table>
"""


def _bill(org, address, account, rows, printed_total, statement_date):
    body = "".join(
        f"<tr><td>{d}</td><td>{c}</td><td>{desc}</td><td class='r'>{u}</td><td class='r'>${amt}</td></tr>"
        for d, c, desc, u, amt in rows
    )
    return (
        _header(org, address, "ITEMIZED STATEMENT OF CHARGES")
        + f"""
<p><b>Account:</b> {account} &nbsp;&nbsp; <b>Statement date:</b> {statement_date}</p>
<table class="grid">
<tr><th>Date of service</th><th>CPT</th><th>Description</th><th class='r'>Units</th><th class='r'>Charge</th></tr>
{body}
</table>
<p class="total"><b>TOTAL CHARGES: ${printed_total}</b></p>
<p class="small">Payments and adjustments: $0.00. Balance due upon receipt. Questions: billing office.</p>
"""
    )


ER_ADDR = "2200 Harbor Blvd, Seaview, CA 90000 (fictional)"
IMG_ADDR = "41 Lighthouse Way, Suite 3, Seaview, CA 90000 (fictional)"
ORTHO_ADDR = "900 Pacific Ave, Floor 2, Seaview, CA 90000 (fictional)"
PT_ADDR = "17 Marina Court, Seaview, CA 90000 (fictional)"

ER_BILL_ROWS = [
    ("02/03/2026", "99284", "Emergency dept visit, moderate-high complexity", "1", "1,850.00"),
    ("02/03/2026", "70450", "CT head/brain without contrast", "1", "2,400.00"),
    ("02/03/2026", "72040", "X-ray cervical spine, 2-3 views", "1", "420.00"),
    ("02/03/2026", "96372", "Therapeutic injection, IM (ketorolac)", "1", "165.00"),
]

PT_DATES_DOC = ["03/05/2026", "03/09/2026", "03/12/2026", "03/16/2026", "03/19/2026"]
PT_DATES_BILLED = PT_DATES_DOC + ["03/23/2026"]  # 03/23 has no treatment note

PT_BILL_ROWS = [("03/02/2026", "97161", "PT evaluation, low complexity", "1", "185.00")]
for _d in PT_DATES_BILLED:
    PT_BILL_ROWS.append((_d, "97110", "Therapeutic exercise, each 15 min", "2", "160.00"))
    PT_BILL_ROWS.append((_d, "97140", "Manual therapy, each 15 min", "1", "85.00"))

ORTHO_BILL_ROWS = [
    ("02/24/2026", "99204", "New patient office visit", "1", "425.00"),
    ("04/21/2026", "99214", "Established patient office visit", "1", "210.00"),
    ("05/05/2026", "62321", "Cervical epidural injection, with imaging guidance", "1", "2,100.00"),
    ("05/05/2026", "77003", "Fluoroscopic guidance, spine injection", "1", "380.00"),
]

# Each document: id, file name, plain title, kind, how it is produced, pages of HTML.
DOCUMENTS = [
    {
        "id": "D01", "file": "01_bayview_er_record.pdf", "title": "Emergency department record",
        "kind": "record", "scanned": False,
        "pages": [
            _header(ER, ER_ADDR, "EMERGENCY DEPARTMENT PHYSICIAN RECORD") + """
<p><b>Date of service:</b> 02/03/2026 &nbsp; <b>Arrival:</b> 14:32 &nbsp; <b>MRN:</b> BRM-4471902</p>
<p><b>Attending physician:</b> Daniel Okafor, MD</p>
<h3>Chief complaint</h3>
<p>Neck pain and low back pain after a motor vehicle collision.</p>
<h3>History of present illness</h3>
<p>37-year-old female, restrained driver, rear-ended at a stop light at moderate speed about one hour before
arrival. Airbags did not deploy. Reports immediate neck stiffness and low back pain, pain 7/10. Denies loss of
consciousness, numbness or weakness.</p>
<h3>Examination</h3>
<p>Tenderness over the cervical paraspinal muscles and the lumbar paraspinal muscles. Range of motion of the
neck reduced by pain. Strength 5/5 in all extremities. Sensation intact.</p>
<h3>Imaging</h3>
<p>CT head without contrast: no acute intracranial abnormality.<br/>
X-ray cervical spine, 3 views: no fracture or malalignment.</p>
<h3>Treatment in the department</h3>
<p>Ketorolac 30 mg IM given at 15:10. Pain improved to 5/10.</p>
<h3>Diagnoses</h3>
<p>1. S13.4XXA - Sprain of ligaments of cervical spine, initial encounter<br/>
2. S33.5XXA - Sprain of ligaments of lumbar spine, initial encounter</p>
""",
            _header(ER, ER_ADDR, "DISCHARGE INSTRUCTIONS") + """
<p><b>Date of service:</b> 02/03/2026 &nbsp; <b>Discharged:</b> 17:05, ambulatory, in stable condition</p>
<h3>Prescriptions</h3>
<p>Cyclobenzaprine 5 mg, one tablet at bedtime as needed for muscle spasm, 10 tablets.<br/>
Ibuprofen 600 mg, one tablet every 8 hours with food, 20 tablets.</p>
<h3>Follow-up</h3>
<p>Follow up with an orthopedic or spine specialist within 1 to 2 weeks. Return to the emergency department
for new weakness, numbness, or loss of bladder or bowel control.</p>
<p>Electronically signed: Daniel Okafor, MD, 02/03/2026 17:20</p>
""",
        ],
    },
    {
        "id": "D02", "file": "02_bayview_er_bill.pdf", "title": "Emergency department bill",
        "kind": "bill", "scanned": False,
        "pages": [_bill(ER, ER_ADDR, "BRM-ACCT-77310", ER_BILL_ROWS, "4,835.00", "03/01/2026")],
    },
    {
        "id": "D03", "file": "03_bayview_er_bill_fax.pdf", "title": "Emergency department bill (faxed copy)",
        "kind": "bill", "scanned": True, "duplicate_of": "D02", "fax": True,
        "pages": [_bill(ER, ER_ADDR, "BRM-ACCT-77310", ER_BILL_ROWS, "4,835.00", "03/01/2026")],
    },
    {
        "id": "D04", "file": "04_coastline_mri_report.pdf", "title": "MRI report, cervical spine",
        "kind": "record", "scanned": False,
        "pages": [
            _header(IMAGING, IMG_ADDR, "MAGNETIC RESONANCE IMAGING REPORT") + """
<p><b>Exam:</b> MRI cervical spine without contrast &nbsp; <b>Exam date:</b> Feb 17, 2026</p>
<p><b>Referring physician:</b> Daniel Okafor, MD &nbsp; <b>Indication:</b> neck pain radiating to the left arm
after a motor vehicle collision on 02/03/2026.</p>
<h3>Findings</h3>
<p>C4-C5: mild disc bulge without canal stenosis.<br/>
C5-C6: broad-based posterior disc protrusion with mild left neural foraminal narrowing, contacting the
exiting left C6 nerve root.<br/>
C6-C7: no significant disc abnormality.<br/>
Vertebral body heights are maintained. No fracture. Cord signal is normal.</p>
<h3>Impression</h3>
<p>1. C5-C6 disc protrusion with mild left foraminal narrowing (M50.222).<br/>
2. Mild C4-C5 disc bulge.</p>
<p>Interpreted by: Priya Raman, MD, Radiologist. Signed Feb 17, 2026.</p>
""",
        ],
    },
    {
        "id": "D05", "file": "05_coastline_imaging_bill.pdf", "title": "Imaging bill",
        "kind": "bill", "scanned": False,
        "pages": [_bill(IMAGING, IMG_ADDR, "CIA-20931",
                        [("02/17/2026", "72141", "MRI cervical spine without contrast", "1", "2,950.00")],
                        "2,950.00", "03/10/2026")],
    },
    {
        "id": "D06", "file": "06_pacific_ortho_notes.pdf", "title": "Orthopedic and spine notes",
        "kind": "record", "scanned": False,
        "pages": [
            _header(ORTHO, ORTHO_ADDR, "NEW PATIENT CONSULTATION") + """
<p><b>Date of visit:</b> 02/24/2026 &nbsp; <b>Provider:</b> Helen Park, MD</p>
<h3>History</h3>
<p>Referred after a motor vehicle collision on 02/03/2026. Neck pain 6/10 with intermittent pain and tingling
into the left forearm. Low back pain improving. MRI of 02/17/2026 reviewed.</p>
<h3>Examination</h3>
<p>Spurling test positive on the left. Reduced cervical rotation. Strength 5/5. Reflexes symmetric.</p>
<h3>Assessment</h3>
<p>1. M50.222 - Cervical disc displacement at C5-C6 level<br/>
2. S13.4XXA - Sprain of ligaments of cervical spine</p>
<h3>Plan</h3>
<p>Physical therapy two times a week for six weeks. Continue ibuprofen as needed. Return in 6 to 8 weeks.</p>
""",
            _header(ORTHO, ORTHO_ADDR, "FOLLOW-UP VISIT") + """
<p><b>Date of visit:</b> 04/21/2026 &nbsp; <b>Provider:</b> Helen Park, MD</p>
<h3>Interval history</h3>
<p>Completed six physical therapy sessions, then stopped after 03/19/2026 because of her work schedule.
Neck pain persists at 6/10 with left arm radiation that worsens with overhead work.</p>
<h3>Assessment</h3>
<p>M50.222 - Cervical disc displacement at C5-C6 level, persistent radicular symptoms despite conservative care.</p>
<h3>Plan</h3>
<p>Cervical interlaminar epidural steroid injection at C5-C6. Risks, benefits and alternatives discussed;
patient agrees.</p>
""",
            _header(ORTHO, ORTHO_ADDR, "PROCEDURE NOTE") + """
<p><b>Date of procedure:</b> 05/05/2026 &nbsp; <b>Physician:</b> Helen Park, MD</p>
<p><b>Procedure:</b> Cervical interlaminar epidural steroid injection, C5-C6, under fluoroscopic guidance
(CPT 62321, 77003).</p>
<p><b>Pre-procedure diagnosis:</b> M50.222 - Cervical disc displacement at C5-C6 level.</p>
<p><b>Description:</b> Prone position, sterile preparation. Under fluoroscopy, the C5-C6 interlaminar space was
entered using a loss-of-resistance technique. Contrast confirmed epidural spread. Injected 80 mg
triamcinolone with 3 mL preservative-free saline. No complications.</p>
<p><b>Pain:</b> 6/10 before, 2/10 after the procedure.</p>
""",
        ],
    },
    {
        "id": "D07", "file": "07_pacific_ortho_bill.pdf", "title": "Orthopedic bill",
        "kind": "bill", "scanned": False,
        # Printed total is $100 too high: the line items add up to 3,115.00.
        "pages": [_bill(ORTHO, ORTHO_ADDR, "PSO-55120", ORTHO_BILL_ROWS, "3,215.00", "05/20/2026")],
    },
    {
        "id": "D08", "file": "08_harbor_pt_notes_scanned.pdf", "title": "Physical therapy notes (scanned)",
        "kind": "record", "scanned": True,
        "pages": [
            _header(PT, PT_ADDR, "PHYSICAL THERAPY INITIAL EVALUATION") + """
<p><b>Date:</b> 3/2/26 &nbsp; <b>Therapist:</b> Luis Moreno, PT, DPT</p>
<p><b>Referral:</b> Helen Park, MD. Diagnosis M50.222, S13.4XXA.</p>
<p><b>Subjective:</b> neck pain 6/10, tingling into the left forearm, difficulty with overhead reaching at work.</p>
<p><b>Objective:</b> cervical rotation 45 degrees right, 40 degrees left. Neck Disability Index 38%.</p>
<p><b>Plan:</b> therapeutic exercise and manual therapy, 2x per week for 6 weeks.</p>
<p><b>Billing:</b> 97161 PT evaluation, low complexity.</p>
""",
            _header(PT, PT_ADDR, "PHYSICAL THERAPY DAILY NOTES") + """
<table class="grid">
<tr><th>Date</th><th>Treatment</th><th>Pain</th><th>Notes</th></tr>
<tr><td>3/5/26</td><td>97110 x2, 97140</td><td>6/10</td><td>Tolerated well.</td></tr>
<tr><td>3/9/26</td><td>97110 x2, 97140</td><td>5/10</td><td>Improved rotation.</td></tr>
<tr><td>3/12/26</td><td>97110 x2, 97140</td><td>5/10</td><td>Home exercises reviewed.</td></tr>
<tr><td>3/16/26</td><td>97110 x2, 97140</td><td>4/10</td><td>Less tingling.</td></tr>
<tr><td>3/19/26</td><td>97110 x2, 97140</td><td>4/10</td><td>Patient to hold PT due to work schedule.</td></tr>
</table>
<p>Signed: Luis Moreno, PT, DPT</p>
""",
        ],
    },
    {
        "id": "D09", "file": "09_harbor_pt_bill.pdf", "title": "Physical therapy bill",
        "kind": "bill", "scanned": False,
        "pages": [_bill(PT, PT_ADDR, "HPT-3381", PT_BILL_ROWS, "1,655.00", "04/01/2026")],
    },
]

# ---------------------------------------------------------------------------
# Ground truth: what a careful paralegal would extract from the set above.
# ---------------------------------------------------------------------------


def _iso(us: str) -> str:
    m, d, y = us.split("/")
    return f"{y}-{int(m):02d}-{int(d):02d}"


GOLD_ENCOUNTERS = (
    [
        {"date": "2026-02-03", "provider": ER, "dx": ["S13.4XXA", "S33.5XXA"]},
        {"date": "2026-02-17", "provider": IMAGING, "dx": ["M50.222"]},
        {"date": "2026-02-24", "provider": ORTHO, "dx": ["M50.222", "S13.4XXA"]},
        {"date": "2026-03-02", "provider": PT, "dx": ["M50.222", "S13.4XXA"]},
    ]
    + [{"date": _iso(d), "provider": PT, "dx": []} for d in PT_DATES_DOC]
    + [
        {"date": "2026-04-21", "provider": ORTHO, "dx": ["M50.222"]},
        {"date": "2026-05-05", "provider": ORTHO, "dx": ["M50.222"]},
    ]
)


def _rows(provider, rows):
    return [
        {"provider": provider, "date": _iso(d), "code": c, "amount": float(a.replace(",", ""))}
        for d, c, _desc, _u, a in rows
    ]


GOLD_BILL_LINES = (
    _rows(ER, ER_BILL_ROWS)
    + _rows(IMAGING, [("02/17/2026", "72141", "", "1", "2,950.00")])
    + _rows(ORTHO, ORTHO_BILL_ROWS)
    + _rows(PT, PT_BILL_ROWS)
)

GOLD_TOTAL_BILLED = round(sum(r["amount"] for r in GOLD_BILL_LINES), 2)  # duplicates not counted

GOLD_FINDINGS = [
    {"type": "duplicate_document", "doc": "D03", "of": "D02"},
    {"type": "total_mismatch", "doc": "D07", "printed": 3215.00, "computed": 3115.00},
    {"type": "billed_not_documented", "provider": PT, "date": "2026-03-23"},
    {"type": "care_gap", "from": "2026-03-19", "to": "2026-04-21", "days": 33},
]
