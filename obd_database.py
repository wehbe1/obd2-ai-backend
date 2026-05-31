"""
OBD2 AI — Professional Knowledge Base
──────────────────────────────────────
A curated database of the most common OBD / DTC codes encountered in
real-world vehicle diagnostics. Each entry provides:

  • title         — English technical name (for mechanics)
  • system_he     — Affected vehicle system in Hebrew
  • severity      — קריטי | גבוה | בינוני | נמוך
  • safe_to_drive — stop_immediately | drive_to_garage | safe_to_drive
  • causes_he     — Ordered list of probable causes in Hebrew
  • actions_he    — Ordered list of recommended repair steps in Hebrew
  • cost_range_ils — Estimated repair cost in Israel (NIS ₪)

Coverage: P0xxx Generic Powertrain · P1xxx OEM · C0xxx Chassis/ABS ·
          B0xxx Body/Airbag · U0xxx Network/Communication
"""

from __future__ import annotations

import re
from typing import Any

# ── Master database ────────────────────────────────────────────────────────────

_DB: dict[str, dict[str, Any]] = {

    # ═══════════════════════════════════════════════════════════════════════════
    # POWERTRAIN — FUEL & AIR METERING (P0001–P0099)
    # ═══════════════════════════════════════════════════════════════════════════

    "P0001": {
        "title": "Fuel Volume Regulator Control Circuit Open",
        "system_he": "מערכת דלק",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["תקלה בוסת לחץ דלק", "נזילת דלק", "חיישן לחץ דלק פגום", "קצר חשמלי"],
        "actions_he": ["בדיקת לחץ דלק", "בדיקת חיישן לחץ דלק", "בדיקת מסנן דלק", "בדיקת חיווט"],
        "cost_range_ils": "300–1,200",
    },
    "P0011": {
        "title": "Intake Camshaft Position Timing Over-Advanced (Bank 1)",
        "system_he": "עיתוי מנוע / VVT",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["שמן מנוע מלוכלך או ברמה נמוכה", "תקלה בשסתום OCV", "רצועת תזמון שחוקה", "חיישן מצב גל זיז פגום"],
        "actions_he": ["החלפת שמן מנוע מיידית", "בדיקת שסתום OCV", "בדיקת רצועת תזמון", "קריאת קודי שגיאה"],
        "cost_range_ils": "400–2,500",
    },
    "P0012": {
        "title": "Intake Camshaft Position Timing Over-Retarded (Bank 1)",
        "system_he": "עיתוי מנוע / VVT",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["שמן מנוע מלוכלך", "שסתום OCV תקוע", "לחץ שמן נמוך"],
        "actions_he": ["החלפת שמן מנוע", "בדיקת שסתום OCV", "מדידת לחץ שמן"],
        "cost_range_ils": "400–2,000",
    },
    "P0021": {
        "title": "Intake Camshaft Position Timing Over-Advanced (Bank 2)",
        "system_he": "עיתוי מנוע / VVT – בנק 2",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["שמן מנוע מלוכלך או ברמה נמוכה", "תקלה בשסתום OCV בנק 2", "חיישן גל זיז בנק 2 פגום"],
        "actions_he": ["החלפת שמן מנוע מיידית", "בדיקת שסתום OCV בנק 2", "בדיקת חיישן גל זיז"],
        "cost_range_ils": "400–2,500",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # MAF / MAP SENSORS (P0100–P0109)
    # ═══════════════════════════════════════════════════════════════════════════

    "P0100": {
        "title": "Mass Air Flow Sensor Circuit Malfunction",
        "system_he": "חיישן MAF (זרימת אוויר)",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["חיישן MAF מלוכלך", "חיישן MAF פגום", "נזילת אוויר בצינור שאיבה", "קצר חשמלי"],
        "actions_he": ["ניקוי חיישן MAF", "בדיקת חיווט חיישן", "בדיקת צינורות שאיבה", "החלפת חיישן MAF במידת הצורך"],
        "cost_range_ils": "200–900",
    },
    "P0101": {
        "title": "Mass Air Flow Sensor Range/Performance",
        "system_he": "חיישן MAF (ביצועים)",
        "severity": "בינוני",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["חיישן MAF מלוכלך", "נזילת אוויר", "מסנן אוויר סתום", "חיישן פגום"],
        "actions_he": ["ניקוי חיישן MAF", "בדיקת מסנן אוויר", "בדיקת צינורות אוויר", "החלפת חיישן במידת הצורך"],
        "cost_range_ils": "150–800",
    },
    "P0102": {
        "title": "Mass Air Flow Sensor Circuit Low",
        "system_he": "חיישן MAF – מתח נמוך",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["חיישן MAF פגום", "נזילת אוויר גדולה", "קצר חשמלי לאדמה", "ECU פגום"],
        "actions_he": ["בדיקת חיווט חיישן MAF", "בדיקת נזילות אוויר", "בדיקת ECU"],
        "cost_range_ils": "200–900",
    },
    "P0103": {
        "title": "Mass Air Flow Sensor Circuit High",
        "system_he": "חיישן MAF – מתח גבוה",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["חיישן MAF פגום", "נתק בחיווט חיישן", "בעיה ב-ECU"],
        "actions_he": ["בדיקת חיישן MAF", "בדיקת חיווט", "החלפת חיישן"],
        "cost_range_ils": "200–900",
    },
    "P0105": {
        "title": "Manifold Absolute Pressure Sensor Malfunction",
        "system_he": "חיישן MAP (לחץ מניפולד)",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["חיישן MAP פגום", "נזילת ואקום", "נתק בחיווט", "ECU פגום"],
        "actions_he": ["בדיקת חיישן MAP", "בדיקת צינורות ואקום", "בדיקת חיווט"],
        "cost_range_ils": "200–800",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # INTAKE AIR / COOLANT TEMPERATURE SENSORS (P0110–P0119)
    # ═══════════════════════════════════════════════════════════════════════════

    "P0110": {
        "title": "Intake Air Temperature Sensor Circuit Malfunction",
        "system_he": "חיישן טמפרטורת אוויר נכנס (IAT)",
        "severity": "בינוני",
        "safe_to_drive": "safe_to_drive",
        "causes_he": ["חיישן IAT פגום", "קצר חשמלי", "נתק בחיווט"],
        "actions_he": ["בדיקת חיישן IAT", "בדיקת חיווט חיישן", "החלפת חיישן"],
        "cost_range_ils": "100–400",
    },
    "P0115": {
        "title": "Engine Coolant Temperature Sensor Circuit Malfunction",
        "system_he": "חיישן טמפרטורת מים (ECT)",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["חיישן ECT פגום", "קצר חשמלי", "נזילת נוזל קירור", "רמת נוזל קירור נמוכה"],
        "actions_he": ["בדיקת רמת נוזל קירור", "בדיקת חיישן ECT", "בדיקת חיווט", "בדיקת נזילות"],
        "cost_range_ils": "150–600",
    },
    "P0116": {
        "title": "Engine Coolant Temperature Sensor Range/Performance",
        "system_he": "חיישן טמפרטורת מים – ביצועים",
        "severity": "בינוני",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["חיישן ECT מלוכלך או שחוק", "בעיית ת'רמוסטט", "נזילת נוזל קירור"],
        "actions_he": ["בדיקת ת'רמוסטט", "בדיקת חיישן ECT", "החלפת חיישן"],
        "cost_range_ils": "200–800",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # THROTTLE POSITION SENSOR (P0120–P0124)
    # ═══════════════════════════════════════════════════════════════════════════

    "P0120": {
        "title": "Throttle Position Sensor A Circuit Malfunction",
        "system_he": "חיישן מיקום מצערת (TPS)",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["חיישן TPS פגום", "גוף מצערת מלוכלך", "קצר חשמלי", "ECU פגום"],
        "actions_he": ["ניקוי גוף מצערת", "בדיקת חיישן TPS", "בדיקת חיווט", "כיול TPS"],
        "cost_range_ils": "300–1,500",
    },
    "P0121": {
        "title": "Throttle Position Sensor A Range/Performance",
        "system_he": "חיישן מיקום מצערת – ביצועים",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["חיישן TPS שחוק", "גוף מצערת מלוכלך", "נתק בחיווט"],
        "actions_he": ["ניקוי גוף מצערת", "בדיקת חיישן TPS", "החלפת חיישן"],
        "cost_range_ils": "300–1,500",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # OXYGEN SENSORS (P0130–P0175)
    # ═══════════════════════════════════════════════════════════════════════════

    "P0130": {
        "title": "O2 Sensor Circuit Malfunction (Bank 1, Sensor 1)",
        "system_he": "חיישן חמצן קדמי – בנק 1",
        "severity": "בינוני",
        "safe_to_drive": "safe_to_drive",
        "causes_he": ["חיישן חמצן קדמי פגום", "נזילת פליטה לפני החיישן", "בעיית דלק עשיר/רזה", "נתק בחיווט"],
        "actions_he": ["בדיקת חיישן O2 קדמי", "בדיקת נזילות פליטה", "בדיקת חיווט", "החלפת חיישן"],
        "cost_range_ils": "400–1,200",
    },
    "P0131": {
        "title": "O2 Sensor Circuit Low Voltage (Bank 1, Sensor 1)",
        "system_he": "חיישן חמצן קדמי – מתח נמוך",
        "severity": "בינוני",
        "safe_to_drive": "safe_to_drive",
        "causes_he": ["חיישן O2 פגום", "נזילת אוויר בפליטה", "קצר לאדמה", "מנוע רזה"],
        "actions_he": ["בדיקת חיישן O2", "בדיקת צינור פליטה", "בדיקת מערכת הדלק"],
        "cost_range_ils": "400–1,200",
    },
    "P0133": {
        "title": "O2 Sensor Circuit Slow Response (Bank 1, Sensor 1)",
        "system_he": "חיישן חמצן קדמי – תגובה איטית",
        "severity": "בינוני",
        "safe_to_drive": "safe_to_drive",
        "causes_he": ["חיישן O2 ישן ומפוגג", "מנוע שורף שמן", "דלק לא תקין", "קטליזטור פגום"],
        "actions_he": ["החלפת חיישן O2", "בדיקת צריכת שמן", "בדיקת קטליזטור"],
        "cost_range_ils": "400–1,200",
    },
    "P0136": {
        "title": "O2 Sensor Circuit Malfunction (Bank 1, Sensor 2)",
        "system_he": "חיישן חמצן אחורי – בנק 1",
        "severity": "בינוני",
        "safe_to_drive": "safe_to_drive",
        "causes_he": ["חיישן O2 אחורי פגום", "חיישן מבוצע קצר", "נזילת פליטה אחרי קטליזטור"],
        "actions_he": ["בדיקת חיישן O2 אחורי", "בדיקת חיווט", "החלפת חיישן"],
        "cost_range_ils": "400–1,200",
    },
    "P0171": {
        "title": "Fuel System Too Lean (Bank 1)",
        "system_he": "מערכת דלק – תערובת רזה בנק 1",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["נזילת אוויר בצינורות ואקום", "חיישן MAF מלוכלך", "מזרקי דלק סתומים", "משאבת דלק חלשה", "נזילת פליטה לפני חיישן O2"],
        "actions_he": ["בדיקת צינורות ואקום", "ניקוי חיישן MAF", "ניקוי מזרקי דלק", "בדיקת לחץ דלק"],
        "cost_range_ils": "300–2,500",
    },
    "P0172": {
        "title": "Fuel System Too Rich (Bank 1)",
        "system_he": "מערכת דלק – תערובת עשירה בנק 1",
        "severity": "בינוני",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["חיישן MAF פגום", "מזרק דלק דולף", "חיישן טמפרטורה פגום", "לחץ דלק גבוה מדי"],
        "actions_he": ["בדיקת חיישן MAF", "בדיקת מזרקי דלק", "בדיקת לחץ דלק", "בדיקת חיישן O2"],
        "cost_range_ils": "300–2,000",
    },
    "P0174": {
        "title": "Fuel System Too Lean (Bank 2)",
        "system_he": "מערכת דלק – תערובת רזה בנק 2",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["נזילת אוויר בנק 2", "חיישן MAF בנק 2 פגום", "מזרקי דלק בנק 2 סתומים"],
        "actions_he": ["בדיקת צינורות ואקום בנק 2", "ניקוי חיישן MAF", "בדיקת מזרקי דלק"],
        "cost_range_ils": "300–2,500",
    },
    "P0175": {
        "title": "Fuel System Too Rich (Bank 2)",
        "system_he": "מערכת דלק – תערובת עשירה בנק 2",
        "severity": "בינוני",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["חיישן MAF פגום", "מזרק דלק דולף בנק 2", "לחץ דלק גבוה"],
        "actions_he": ["בדיקת חיישן MAF", "בדיקת מזרקי דלק", "בדיקת לחץ דלק"],
        "cost_range_ils": "300–2,000",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # FUEL INJECTORS (P0200–P0275)
    # ═══════════════════════════════════════════════════════════════════════════

    "P0200": {
        "title": "Fuel Injector Circuit Malfunction",
        "system_he": "מזרק דלק – תקלה במעגל",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["מזרק דלק פגום", "קצר חשמלי", "ECU פגום", "נתק בחיווט"],
        "actions_he": ["בדיקת מזרקי דלק", "בדיקת חיווט", "בדיקת ECU"],
        "cost_range_ils": "500–2,500",
    },
    "P0201": {
        "title": "Injector Circuit/Open Cylinder 1",
        "system_he": "מזרק גליל 1",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["מזרק גליל 1 פגום", "נתק בחיווט מזרק", "ECU פגום"],
        "actions_he": ["בדיקת התנגדות מזרק גליל 1", "בדיקת חיווט", "החלפת מזרק"],
        "cost_range_ils": "400–1,500",
    },
    "P0202": {
        "title": "Injector Circuit/Open Cylinder 2",
        "system_he": "מזרק גליל 2",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["מזרק גליל 2 פגום", "נתק בחיווט", "ECU פגום"],
        "actions_he": ["בדיקת התנגדות מזרק גליל 2", "בדיקת חיווט", "החלפת מזרק"],
        "cost_range_ils": "400–1,500",
    },
    "P0203": {
        "title": "Injector Circuit/Open Cylinder 3",
        "system_he": "מזרק גליל 3",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["מזרק גליל 3 פגום", "נתק בחיווט", "ECU פגום"],
        "actions_he": ["בדיקת התנגדות מזרק גליל 3", "בדיקת חיווט", "החלפת מזרק"],
        "cost_range_ils": "400–1,500",
    },
    "P0204": {
        "title": "Injector Circuit/Open Cylinder 4",
        "system_he": "מזרק גליל 4",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["מזרק גליל 4 פגום", "נתק בחיווט", "ECU פגום"],
        "actions_he": ["בדיקת התנגדות מזרק גליל 4", "בדיקת חיווט", "החלפת מזרק"],
        "cost_range_ils": "400–1,500",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # MISFIRES (P0300–P0315)
    # ═══════════════════════════════════════════════════════════════════════════

    "P0300": {
        "title": "Random/Multiple Cylinder Misfire Detected",
        "system_he": "קצר ריתוח מרובה גלילים",
        "severity": "קריטי",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["מצתות פגומות (מרובות)", "חוטי מצת שחוקים", "מזרקי דלק סתומים", "דחיסה נמוכה בגלילים", "תקלה ב-ECU", "מנוע ישן ושחוק"],
        "actions_he": ["בדיקת מצתות", "בדיקת חוטי מצת", "בדיקת דחיסת מנוע", "בדיקת מזרקי דלק", "סריקת מחשב רכב"],
        "cost_range_ils": "300–3,000",
    },
    "P0301": {
        "title": "Cylinder 1 Misfire Detected",
        "system_he": "קצר ריתוח גליל 1",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["מצת גליל 1 פגום", "חוט מצת גליל 1 שחוק", "מזרק גליל 1 סתום", "דחיסה נמוכה בגליל 1", "שסתום גז פגום"],
        "actions_he": ["החלפת מצת גליל 1", "בדיקת חוט/קויל מצת", "בדיקת מזרק", "מדידת דחיסת גליל"],
        "cost_range_ils": "150–2,000",
    },
    "P0302": {
        "title": "Cylinder 2 Misfire Detected",
        "system_he": "קצר ריתוח גליל 2",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["מצת גליל 2 פגום", "קויל מצת גליל 2", "מזרק גליל 2", "דחיסה נמוכה"],
        "actions_he": ["החלפת מצת גליל 2", "בדיקת קויל מצת", "בדיקת מזרק", "מדידת דחיסה"],
        "cost_range_ils": "150–2,000",
    },
    "P0303": {
        "title": "Cylinder 3 Misfire Detected",
        "system_he": "קצר ריתוח גליל 3",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["מצת גליל 3 פגום", "קויל מצת גליל 3", "מזרק גליל 3", "דחיסה נמוכה"],
        "actions_he": ["החלפת מצת גליל 3", "בדיקת קויל מצת", "בדיקת מזרק", "מדידת דחיסה"],
        "cost_range_ils": "150–2,000",
    },
    "P0304": {
        "title": "Cylinder 4 Misfire Detected",
        "system_he": "קצר ריתוח גליל 4",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["מצת גליל 4 פגום", "קויל מצת גליל 4", "מזרק גליל 4", "דחיסה נמוכה"],
        "actions_he": ["החלפת מצת גליל 4", "בדיקת קויל מצת", "בדיקת מזרק", "מדידת דחיסה"],
        "cost_range_ils": "150–2,000",
    },
    "P0305": {
        "title": "Cylinder 5 Misfire Detected",
        "system_he": "קצר ריתוח גליל 5",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["מצת גליל 5 פגום", "קויל מצת גליל 5", "מזרק גליל 5", "דחיסה נמוכה"],
        "actions_he": ["החלפת מצת גליל 5", "בדיקת קויל מצת", "בדיקת מזרק", "מדידת דחיסה"],
        "cost_range_ils": "150–2,000",
    },
    "P0306": {
        "title": "Cylinder 6 Misfire Detected",
        "system_he": "קצר ריתוח גליל 6",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["מצת גליל 6 פגום", "קויל מצת גליל 6", "מזרק גליל 6", "דחיסה נמוכה"],
        "actions_he": ["החלפת מצת גליל 6", "בדיקת קויל מצת", "בדיקת מזרק", "מדידת דחיסה"],
        "cost_range_ils": "150–2,000",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # CRANKSHAFT / CAMSHAFT POSITION SENSORS (P0335–P0345)
    # ═══════════════════════════════════════════════════════════════════════════

    "P0335": {
        "title": "Crankshaft Position Sensor A Circuit Malfunction",
        "system_he": "חיישן מיקום גל ארכובה (CKP)",
        "severity": "קריטי",
        "safe_to_drive": "stop_immediately",
        "causes_he": ["חיישן CKP פגום", "גלגל שיניים CKP פגום", "קצר חשמלי", "נתק בחיווט"],
        "actions_he": ["החלפת חיישן CKP מיידית", "בדיקת גלגל שיניים", "בדיקת חיווט"],
        "cost_range_ils": "300–1,200",
    },
    "P0336": {
        "title": "Crankshaft Position Sensor A Range/Performance",
        "system_he": "חיישן גל ארכובה – ביצועים",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["חיישן CKP מוחלש", "גלגל שיניים פגום", "פגיעת גל ארכובה"],
        "actions_he": ["החלפת חיישן CKP", "בדיקת גלגל שיניים", "בדיקת גל ארכובה"],
        "cost_range_ils": "300–1,200",
    },
    "P0340": {
        "title": "Camshaft Position Sensor A Circuit Malfunction (Bank 1)",
        "system_he": "חיישן מיקום גל זיז (CMP) – בנק 1",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["חיישן CMP פגום", "גלגל שיניים CMP פגום", "רצועת תזמון שחוקה", "קצר חשמלי"],
        "actions_he": ["בדיקת חיישן CMP", "בדיקת גלגל שיניים", "בדיקת רצועת תזמון", "החלפת חיישן"],
        "cost_range_ils": "300–2,500",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # EGR SYSTEM (P0400–P0409)
    # ═══════════════════════════════════════════════════════════════════════════

    "P0400": {
        "title": "EGR Flow Malfunction",
        "system_he": "מערכת EGR (החזרת גזי פליטה)",
        "severity": "בינוני",
        "safe_to_drive": "safe_to_drive",
        "causes_he": ["שסתום EGR סתום", "צינור EGR סתום", "חיישן EGR פגום", "בעיה בוואקום EGR"],
        "actions_he": ["ניקוי שסתום EGR", "בדיקת צינורות EGR", "בדיקת חיישן EGR", "החלפת שסתום EGR"],
        "cost_range_ils": "400–2,500",
    },
    "P0401": {
        "title": "EGR Flow Insufficient",
        "system_he": "EGR – זרימה לא מספקת",
        "severity": "בינוני",
        "safe_to_drive": "safe_to_drive",
        "causes_he": ["שסתום EGR סתום מלוכלך", "צינור EGR חסום", "חיישן מיקום EGR פגום"],
        "actions_he": ["ניקוי שסתום EGR", "ניקוי צינורות EGR", "בדיקת ואקום", "החלפת שסתום"],
        "cost_range_ils": "400–2,500",
    },
    "P0402": {
        "title": "EGR Flow Excessive",
        "system_he": "EGR – זרימה עודפת",
        "severity": "בינוני",
        "safe_to_drive": "safe_to_drive",
        "causes_he": ["שסתום EGR תקוע פתוח", "נזילה בגוף שסתום EGR", "חיישן EGR מוטעה"],
        "actions_he": ["בדיקת שסתום EGR", "בדיקת חיישן EGR", "החלפת שסתום EGR"],
        "cost_range_ils": "400–2,500",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # CATALYTIC CONVERTER (P0420, P0430) — VERY COMMON
    # ═══════════════════════════════════════════════════════════════════════════

    "P0420": {
        "title": "Catalyst System Efficiency Below Threshold (Bank 1)",
        "system_he": "קטליזטור – יעילות נמוכה בנק 1",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["קטליזטור בלוי / מוזנח", "חיישן O2 אחורי (בנק 1) פגום", "מנוע שורף שמן", "דלק לא תקין", "נזילת קירור לתוך המנוע", "תקלת הצתה שגרמה לנזק לקטליזטור"],
        "actions_he": ["בדיקת חיישן O2 אחורי בנק 1", "בדיקת שמן מנוע", "בדיקת קטליזטור בבדיקת פליטה", "החלפת קטליזטור במידת הצורך", "בדיקת מנוע לנזק משני"],
        "cost_range_ils": "800–5,000",
    },
    "P0430": {
        "title": "Catalyst System Efficiency Below Threshold (Bank 2)",
        "system_he": "קטליזטור – יעילות נמוכה בנק 2",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["קטליזטור בנק 2 בלוי", "חיישן O2 אחורי בנק 2 פגום", "מנוע שורף שמן", "דלק לא תקין"],
        "actions_he": ["בדיקת חיישן O2 אחורי בנק 2", "בדיקת קטליזטור", "החלפת קטליזטור בנק 2"],
        "cost_range_ils": "800–5,000",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # EVAP SYSTEM (P0440–P0456) — VERY COMMON
    # ═══════════════════════════════════════════════════════════════════════════

    "P0440": {
        "title": "Evaporative Emission Control System Malfunction",
        "system_he": "מערכת EVAP (אדי דלק)",
        "severity": "נמוך",
        "safe_to_drive": "safe_to_drive",
        "causes_he": ["פקק מכל דלק לא הודק", "חיישן לחץ EVAP פגום", "שסתום EVAP פגום", "נזילה בצינורות EVAP"],
        "actions_he": ["בדיקת פקק מכל דלק", "בדיקת שסתום EVAP", "בדיקת צינורות", "בדיקת לחץ מערכת EVAP"],
        "cost_range_ils": "150–1,500",
    },
    "P0441": {
        "title": "EVAP System Incorrect Purge Flow",
        "system_he": "EVAP – זרימת ניקוי לא תקינה",
        "severity": "נמוך",
        "safe_to_drive": "safe_to_drive",
        "causes_he": ["שסתום פורג' EVAP פגום", "צינור פורג' סתום", "נתק בחיווט"],
        "actions_he": ["בדיקת שסתום פורג'", "בדיקת צינורות ואקום", "החלפת שסתום"],
        "cost_range_ils": "200–1,000",
    },
    "P0442": {
        "title": "EVAP System Small Leak Detected",
        "system_he": "EVAP – נזילה קטנה",
        "severity": "נמוך",
        "safe_to_drive": "safe_to_drive",
        "causes_he": ["פקק מכל דלק לא אטום", "חיישן EVAP פגום", "נזילה קטנה בצינורות", "גוף קנייסטר פגום"],
        "actions_he": ["הידוק פקק מכל דלק", "בדיקת צינורות EVAP", "בדיקת קנייסטר", "בדיקת פקק"],
        "cost_range_ils": "100–1,200",
    },
    "P0446": {
        "title": "EVAP System Vent Control Circuit Malfunction",
        "system_he": "EVAP – שסתום אוורור",
        "severity": "נמוך",
        "safe_to_drive": "safe_to_drive",
        "causes_he": ["שסתום אוורור EVAP פגום", "חסימה בשסתום", "קצר חשמלי"],
        "actions_he": ["בדיקת שסתום אוורור", "בדיקת חיווט", "החלפת שסתום"],
        "cost_range_ils": "300–1,000",
    },
    "P0455": {
        "title": "EVAP System Large Leak Detected",
        "system_he": "EVAP – נזילה גדולה",
        "severity": "בינוני",
        "safe_to_drive": "safe_to_drive",
        "causes_he": ["פקק מכל דלק חסר/פגום", "צינור EVAP נפרק", "שסתום EVAP פגום", "נזק בגוף מכל הדלק"],
        "actions_he": ["בדיקת פקק מכל דלק", "בדיקת צינורות EVAP", "בדיקת שסתומים", "בדיקת מכל הדלק"],
        "cost_range_ils": "200–2,000",
    },
    "P0456": {
        "title": "EVAP System Very Small Leak Detected",
        "system_he": "EVAP – נזילה זעירה",
        "severity": "נמוך",
        "safe_to_drive": "safe_to_drive",
        "causes_he": ["פקק מכל דלק לא אטום לחלוטין", "נזילה זעירה בצינורות", "חיישן לחץ EVAP פגום"],
        "actions_he": ["הידוק/החלפת פקק מכל דלק", "בדיקת צינורות ואקום", "בדיקת חיישן לחץ"],
        "cost_range_ils": "100–800",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # VEHICLE SPEED / IDLE (P0500–P0509)
    # ═══════════════════════════════════════════════════════════════════════════

    "P0500": {
        "title": "Vehicle Speed Sensor Malfunction",
        "system_he": "חיישן מהירות רכב (VSS)",
        "severity": "בינוני",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["חיישן VSS פגום", "קצר חשמלי", "בעיית גיר", "חיווט פגום"],
        "actions_he": ["בדיקת חיישן VSS", "בדיקת חיווט", "בדיקת גיר", "החלפת חיישן"],
        "cost_range_ils": "300–1,200",
    },
    "P0505": {
        "title": "Idle Control System Malfunction",
        "system_he": "מערכת בקרת סרק",
        "severity": "בינוני",
        "safe_to_drive": "safe_to_drive",
        "causes_he": ["שסתום IAC מלוכלך / פגום", "גוף מצערת מלוכלך", "נזילת אוויר", "חיישן TPS פגום"],
        "actions_he": ["ניקוי גוף מצערת", "בדיקת שסתום IAC", "בדיקת צינורות ואקום", "ניקוי / החלפת IAC"],
        "cost_range_ils": "200–1,200",
    },
    "P0506": {
        "title": "Idle Control System RPM Too Low",
        "system_he": "סרק – סל\"ד נמוך מדי",
        "severity": "בינוני",
        "safe_to_drive": "safe_to_drive",
        "causes_he": ["שסתום IAC סתום", "גוף מצערת מלוכלך", "נזילת אוויר"],
        "actions_he": ["ניקוי גוף מצערת", "בדיקת שסתום IAC", "בדיקת נזילות אוויר"],
        "cost_range_ils": "200–1,000",
    },
    "P0507": {
        "title": "Idle Control System RPM Too High",
        "system_he": "סרק – סל\"ד גבוה מדי",
        "severity": "בינוני",
        "safe_to_drive": "safe_to_drive",
        "causes_he": ["שסתום IAC תקוע פתוח", "נזילת אוויר גדולה", "גוף מצערת לא כוייל"],
        "actions_he": ["בדיקת שסתום IAC", "בדיקת נזילות אוויר", "כיול גוף מצערת"],
        "cost_range_ils": "200–1,200",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # ECU / PCM (P0600–P0699)
    # ═══════════════════════════════════════════════════════════════════════════

    "P0600": {
        "title": "Serial Communication Link Malfunction",
        "system_he": "ECU – בעיית תקשורת",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["תקלה ב-ECU", "בעיית חיווט CAN-Bus", "יחידת בקרה פגומה אחרת"],
        "actions_he": ["סריקת קודי שגיאה מלאה", "בדיקת חיווט CAN-Bus", "בדיקת ECU"],
        "cost_range_ils": "500–5,000",
    },
    "P0601": {
        "title": "Internal Control Module Memory Check Sum Error",
        "system_he": "ECU – שגיאת זיכרון",
        "severity": "קריטי",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["ECU פגום או שרוף", "תוכנת ECU פגומה", "מתח לא יציב"],
        "actions_he": ["עדכון תוכנת ECU", "החלפת ECU", "בדיקת מתח סוללה"],
        "cost_range_ils": "800–6,000",
    },
    "P0605": {
        "title": "Internal Control Module ROM Error",
        "system_he": "ECU – שגיאת ROM",
        "severity": "קריטי",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["ECU פגום", "תוכנת ECU פגומה", "נזק מחשמל"],
        "actions_he": ["ניסיון תכנות מחדש ECU", "החלפת ECU", "בדיקת חיווט"],
        "cost_range_ils": "800–6,000",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # TRANSMISSION (P0700–P0799)
    # ═══════════════════════════════════════════════════════════════════════════

    "P0700": {
        "title": "Transmission Control System Malfunction",
        "system_he": "תיבת הילוכים – תקלה כללית",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["תקלה בבקר תיבת הגיר (TCM)", "בעיית חיישני גיר", "שמן גיר מלוכלך", "תקלה מכנית בגיר"],
        "actions_he": ["קריאת קודי TCM", "בדיקת שמן גיר", "בדיקת מנגנון גיר", "ניסיון עדכון TCM"],
        "cost_range_ils": "500–8,000",
    },
    "P0705": {
        "title": "Transmission Range Sensor Circuit Malfunction",
        "system_he": "גיר – חיישן מצב כלי (P R N D)",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["חיישן TR פגום", "קצר חשמלי", "בעיית כניסה לגיר"],
        "actions_he": ["בדיקת חיישן TR", "בדיקת חיווט", "כיול חיישן TR", "החלפת חיישן"],
        "cost_range_ils": "400–2,000",
    },
    "P0715": {
        "title": "Input/Turbine Speed Sensor Malfunction",
        "system_he": "גיר – חיישן מהירות טורבינה",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["חיישן מהירות גיר פגום", "שמן גיר מלוכלך", "קצר חשמלי"],
        "actions_he": ["בדיקת חיישן מהירות גיר", "בדיקת שמן גיר", "החלפת חיישן"],
        "cost_range_ils": "400–2,000",
    },
    "P0730": {
        "title": "Incorrect Gear Ratio",
        "system_he": "גיר – יחס הילוך שגוי",
        "severity": "קריטי",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["שמן גיר מלוכלך / נמוך", "סולנואידים בגיר תקועים", "מנגנון גיר שחוק", "בקר TCM פגום"],
        "actions_he": ["בדיקת שמן גיר", "בדיקת סולנואידים", "אבחון מלא של הגיר"],
        "cost_range_ils": "800–10,000",
    },
    "P0740": {
        "title": "Torque Converter Clutch Circuit Malfunction",
        "system_he": "גיר – ממיר מומנט",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["סולנואיד ממיר מומנט פגום", "שמן גיר מלוכלך", "ממיר מומנט שחוק"],
        "actions_he": ["בדיקת שמן גיר", "בדיקת סולנואיד TCC", "אבחון ממיר מומנט"],
        "cost_range_ils": "600–5,000",
    },
    "P0741": {
        "title": "Torque Converter Clutch Circuit Performance",
        "system_he": "גיר – ממיר מומנט, ביצועים",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["שמן גיר מלוכלך", "ממיר מומנט שחוק", "בעיית לחץ הידראולי"],
        "actions_he": ["החלפת שמן גיר", "בדיקת לחץ הידראולי", "אבחון ממיר מומנט"],
        "cost_range_ils": "600–6,000",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # OEM / MANUFACTURER SPECIFIC (P1xxx)
    # ═══════════════════════════════════════════════════════════════════════════

    "P1000": {
        "title": "OBD II Readiness Test Not Complete",
        "system_he": "קודי מוכנות OBD לא הושלמו",
        "severity": "נמוך",
        "safe_to_drive": "safe_to_drive",
        "causes_he": ["הסוללה הוחלפה לאחרונה", "ECU אופס", "המכונית לא נסעה מספיק"],
        "actions_he": ["נסיעה של 50-100 ק\"מ במצבי נסיעה שונים", "המתנה לסיום מחזורי אבחון"],
        "cost_range_ils": "0",
    },
    "P1101": {
        "title": "MAF Sensor Out of Self Test Range",
        "system_he": "חיישן MAF – מחוץ לטווח בדיקה עצמית",
        "severity": "בינוני",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["חיישן MAF מלוכלך", "נזילת אוויר", "חיישן MAF פגום"],
        "actions_he": ["ניקוי חיישן MAF", "בדיקת נזילות אוויר", "החלפת חיישן MAF"],
        "cost_range_ils": "200–900",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # FUEL PRESSURE (P0087–P0090)
    # ═══════════════════════════════════════════════════════════════════════════

    "P0087": {
        "title": "Fuel Rail/System Pressure Too Low",
        "system_he": "לחץ דלק – נמוך מדי",
        "severity": "קריטי",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["משאבת דלק חלשה / פגומה", "מסנן דלק סתום", "שסתום לחץ דלק פגום", "נזילת דלק"],
        "actions_he": ["מדידת לחץ דלק", "בדיקת משאבת דלק", "החלפת מסנן דלק", "בדיקת נזילות"],
        "cost_range_ils": "400–2,500",
    },
    "P0088": {
        "title": "Fuel Rail/System Pressure Too High",
        "system_he": "לחץ דלק – גבוה מדי",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["שסתום הפחתת לחץ פגום", "קו דלק חוזר חסום", "ממסם לחץ דלק פגום"],
        "actions_he": ["בדיקת שסתום לחץ דלק", "בדיקת קו דלק חוזר", "מדידת לחץ דלק"],
        "cost_range_ils": "300–1,500",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # DIESEL SPECIFIC (P2000–P2099)
    # ═══════════════════════════════════════════════════════════════════════════

    "P2002": {
        "title": "Diesel Particulate Filter Efficiency Below Threshold",
        "system_he": "מסנן חלקיקי דיזל (DPF) – יעילות נמוכה",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["DPF סתום – זקוק לריג'נרציה", "שמן מנוע לא מתאים לדיזל עם DPF", "נסיעות קצרות בלבד", "חיישן לחץ DPF פגום"],
        "actions_he": ["נסיעה ממושכת בקצב גבוה (regeneration)", "בדיקת מפלס שמן", "בדיקת חיישן לחץ DPF", "ניקוי DPF במוסך"],
        "cost_range_ils": "500–5,000",
    },
    "P2263": {
        "title": "Turbocharger/Supercharger Boost System Performance",
        "system_he": "טורבו – ביצועים",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["טורבו שחוק / פגום", "אינטרקולר סתום", "שסתום wastegate תקוע", "נזילת אוויר בצינורות", "חיישן לחץ בוסט פגום"],
        "actions_he": ["בדיקת טורבו", "בדיקת צינורות אוויר", "בדיקת חיישן בוסט", "בדיקת שסתום wastegate"],
        "cost_range_ils": "1,000–8,000",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # CHASSIS / ABS / TRACTION (C0xxx)
    # ═══════════════════════════════════════════════════════════════════════════

    "C0031": {
        "title": "Right Front Wheel Speed Sensor Malfunction",
        "system_he": "חיישן מהירות גלגל קדמי ימין – ABS",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["חיישן מהירות ABS קדמי ימין פגום", "טבעת טון חיישן שחוקה", "נתק בחיווט", "מחשב ABS פגום"],
        "actions_he": ["בדיקת חיישן ABS קדמי ימין", "בדיקת טבעת טון", "בדיקת חיווט", "החלפת חיישן"],
        "cost_range_ils": "300–1,200",
    },
    "C0034": {
        "title": "Right Front Wheel Speed Sensor Range/Performance",
        "system_he": "חיישן ABS קדמי ימין – ביצועים",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["חיישן ABS מלוכלך / פגום", "טבעת טון חיישן מלוכלכת", "מרווח חיישן לא תקין"],
        "actions_he": ["ניקוי חיישן ABS", "בדיקת מרווח חיישן", "בדיקת טבעת טון", "החלפת חיישן"],
        "cost_range_ils": "300–1,200",
    },
    "C0035": {
        "title": "Left Front Wheel Speed Sensor Malfunction",
        "system_he": "חיישן מהירות גלגל קדמי שמאל – ABS",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["חיישן ABS קדמי שמאל פגום", "טבעת טון שחוקה", "נתק בחיווט"],
        "actions_he": ["בדיקת חיישן ABS קדמי שמאל", "בדיקת טבעת טון", "בדיקת חיווט", "החלפת חיישן"],
        "cost_range_ils": "300–1,200",
    },
    "C0040": {
        "title": "Right Rear Wheel Speed Sensor Malfunction",
        "system_he": "חיישן מהירות גלגל אחורי ימין – ABS",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["חיישן ABS אחורי ימין פגום", "טבעת טון שחוקה", "נתק בחיווט"],
        "actions_he": ["בדיקת חיישן ABS אחורי ימין", "בדיקת טבעת טון", "בדיקת חיווט"],
        "cost_range_ils": "300–1,200",
    },
    "C0041": {
        "title": "Left Rear Wheel Speed Sensor Malfunction",
        "system_he": "חיישן מהירות גלגל אחורי שמאל – ABS",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["חיישן ABS אחורי שמאל פגום", "טבעת טון שחוקה", "נתק בחיווט"],
        "actions_he": ["בדיקת חיישן ABS אחורי שמאל", "בדיקת טבעת טון", "בדיקת חיווט"],
        "cost_range_ils": "300–1,200",
    },
    "C0110": {
        "title": "ABS Motor Circuit Malfunction",
        "system_he": "מנוע משאבת ABS – תקלה",
        "severity": "קריטי",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["מנוע משאבת ABS פגום", "ממסר ABS פגום", "קצר חשמלי", "מחשב ABS פגום"],
        "actions_he": ["בדיקת מנוע משאבת ABS", "בדיקת ממסר ABS", "בדיקת מחשב ABS"],
        "cost_range_ils": "800–5,000",
    },
    "C0121": {
        "title": "ABS Valve Malfunction",
        "system_he": "שסתום ABS – תקלה",
        "severity": "קריטי",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["שסתום ABS פגום", "מחשב ABS פגום", "קצר חשמלי"],
        "actions_he": ["בדיקת שסתומי ABS", "בדיקת מחשב ABS", "החלפת יחידת ABS"],
        "cost_range_ils": "1,000–6,000",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # BODY / AIRBAG (B0xxx)
    # ═══════════════════════════════════════════════════════════════════════════

    "B0001": {
        "title": "Driver Frontal Stage 1 Deployment Loop Resistance Low",
        "system_he": "כרית אוויר קדמית נהג – נפרסה / תקלה",
        "severity": "קריטי",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["כרית אוויר שנפרסה", "מחשב כריות אוויר (SRS) פגום", "חיישן פגיעה פגום", "קצר חשמלי"],
        "actions_he": ["אסור לנסוע – פנה למוסך מיידית", "החלפת כרית אוויר", "בדיקת מחשב SRS"],
        "cost_range_ils": "2,000–8,000",
    },
    "B0002": {
        "title": "Driver Frontal Stage 2 Deployment Loop Resistance Low",
        "system_he": "כרית אוויר שלב 2 – תקלה",
        "severity": "קריטי",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["תקלה במפרוס כרית אוויר שלב 2", "מחשב SRS פגום", "נתק בחיווט"],
        "actions_he": ["פנייה למוסך מוסמך מיידית", "בדיקת מחשב SRS", "בדיקת כרית אוויר"],
        "cost_range_ils": "2,000–8,000",
    },
    "B0010": {
        "title": "Passenger Frontal Deployment Loop Resistance High",
        "system_he": "כרית אוויר קדמית נוסע – תקלה",
        "severity": "קריטי",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["נתק בחיווט כרית אוויר נוסע", "מחשב SRS פגום", "חיישן כיסא נוסע פגום"],
        "actions_he": ["פנייה למוסך מוסמך מיידית", "בדיקת מחשב SRS", "בדיקת חיווט"],
        "cost_range_ils": "1,500–6,000",
    },
    "B0019": {
        "title": "Front Seat Belt Retractor Pretensioner Resistance High",
        "system_he": "חגורת בטיחות – פרה-טנסיונר תקלה",
        "severity": "קריטי",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["פרה-טנסיונר חגורת בטיחות פגום", "נתק בחיווט", "מחשב SRS פגום"],
        "actions_he": ["פנייה למוסך SRS מוסמך", "בדיקת חגורות בטיחות", "בדיקת מחשב SRS"],
        "cost_range_ils": "1,000–4,000",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # NETWORK / COMMUNICATION (U0xxx)
    # ═══════════════════════════════════════════════════════════════════════════

    "U0001": {
        "title": "High Speed CAN Communication Bus",
        "system_he": "CAN-Bus – תקלת תקשורת",
        "severity": "קריטי",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["בעיה ב-CAN-Bus", "ECU פגום", "נתק בחיווט CAN", "קצר חשמלי"],
        "actions_he": ["סריקת כל מחשבי הרכב", "בדיקת קוי CAN", "בדיקת ECU/TCM/ABS"],
        "cost_range_ils": "500–5,000",
    },
    "U0100": {
        "title": "Lost Communication with ECM/PCM",
        "system_he": "אובדן תקשורת עם ECU/PCM",
        "severity": "קריטי",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["ECU פגום", "נתק בחיווט CAN-Bus", "בעיית מתח לECU", "קצר חשמלי"],
        "actions_he": ["בדיקת מתח סוללה", "בדיקת חיווט CAN", "בדיקת ECU", "העברה לשרות ECU"],
        "cost_range_ils": "500–6,000",
    },
    "U0101": {
        "title": "Lost Communication with TCM",
        "system_he": "אובדן תקשורת עם מחשב גיר (TCM)",
        "severity": "קריטי",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["TCM פגום", "נתק בחיווט CAN", "בעיית מתח"],
        "actions_he": ["בדיקת חיווט CAN לגיר", "בדיקת TCM", "בדיקת מתח סוללה"],
        "cost_range_ils": "500–5,000",
    },
    "U0121": {
        "title": "Lost Communication with ABS Control Module",
        "system_he": "אובדן תקשורת עם מחשב ABS",
        "severity": "קריטי",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["מחשב ABS פגום", "נתק בחיווט CAN", "קצר חשמלי"],
        "actions_he": ["בדיקת חיווט CAN לABS", "בדיקת מחשב ABS", "בדיקת מתח"],
        "cost_range_ils": "800–5,000",
    },
    "U0140": {
        "title": "Lost Communication with Body Control Module",
        "system_he": "אובדן תקשורת עם מחשב גוף (BCM)",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["BCM פגום", "נתק בחיווט CAN", "בעיית מתח"],
        "actions_he": ["בדיקת חיווט CAN", "בדיקת BCM", "בדיקת מתח סוללה"],
        "cost_range_ils": "500–4,000",
    },
    "U0155": {
        "title": "Lost Communication with Instrument Panel Cluster",
        "system_he": "אובדן תקשורת עם לוח המחוונים",
        "severity": "גבוה",
        "safe_to_drive": "drive_to_garage",
        "causes_he": ["בעיה בלוח המחוונים", "נתק בחיווט CAN", "BCM פגום"],
        "actions_he": ["בדיקת חיווט לוח מחוונים", "בדיקת CAN-Bus", "בדיקת לוח מחוונים"],
        "cost_range_ils": "400–3,000",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # OIL / COOLING SYSTEM
    # ═══════════════════════════════════════════════════════════════════════════

    "P0520": {
        "title": "Engine Oil Pressure Sensor/Switch Circuit Malfunction",
        "system_he": "חיישן לחץ שמן מנוע",
        "severity": "קריטי",
        "safe_to_drive": "stop_immediately",
        "causes_he": ["לחץ שמן נמוך מסכן!", "חיישן לחץ שמן פגום", "שמן מנוע ברמה נמוכה", "משאבת שמן חלשה", "נזילת שמן"],
        "actions_he": ["עצור מיד ובדוק מפלס שמן!", "אל תנסע עם אור שמן דולק!", "בדיקת לחץ שמן מנוע", "החלפת חיישן שמן", "בדיקת נזילות שמן"],
        "cost_range_ils": "100–3,000",
    },
    "P0521": {
        "title": "Engine Oil Pressure Sensor Range/Performance",
        "system_he": "חיישן לחץ שמן – ביצועים",
        "severity": "קריטי",
        "safe_to_drive": "stop_immediately",
        "causes_he": ["לחץ שמן חריג", "חיישן לחץ שמן פגום", "משאבת שמן חלשה"],
        "actions_he": ["עצור מיד!", "בדיקת מפלס שמן", "מדידת לחץ שמן", "החלפת חיישן"],
        "cost_range_ils": "200–3,000",
    },
    "P0128": {
        "title": "Coolant Temperature Below Thermostat Regulating Temperature",
        "system_he": "מנוע לא מתחמם – ת'רמוסטט פגום",
        "severity": "בינוני",
        "safe_to_drive": "safe_to_drive",
        "causes_he": ["ת'רמוסטט תקוע פתוח", "חיישן ECT פגום", "ת'רמוסטט מוחלף בדרגה לא נכונה"],
        "actions_he": ["בדיקת ת'רמוסטט", "החלפת ת'רמוסטט", "בדיקת חיישן ECT"],
        "cost_range_ils": "300–1,000",
    },
}

# ── Public API ─────────────────────────────────────────────────────────────────

# Regex to find OBD codes in arbitrary text
_CODE_RE = re.compile(r'\b([PBCU][0-9]{4})\b', re.IGNORECASE)


def extract_codes_from_text(text: str) -> list[str]:
    """Return deduplicated, uppercase OBD codes found in *text*."""
    if not text:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for m in _CODE_RE.finditer(text):
        code = m.group(1).upper()
        if code not in seen:
            seen.add(code)
            result.append(code)
    return result


def lookup(codes: list[str]) -> list[dict]:
    """
    Return database entries for *codes*.
    Each returned dict always includes the original *code* key.
    Unrecognised codes return a minimal skeleton so the caller never crashes.
    """
    results = []
    for raw in codes:
        code = raw.strip().upper()
        entry = _DB.get(code)
        if entry:
            results.append({"code": code, **entry})
        else:
            results.append({
                "code": code,
                "title": "Unknown Code",
                "system_he": "לא מזוהה",
                "severity": "בינוני",
                "safe_to_drive": "drive_to_garage",
                "causes_he": ["קוד לא נמצא בבסיס הנתונים"],
                "actions_he": ["פנה למוסך לאבחון מלא"],
                "cost_range_ils": "לא ידוע",
            })
    return results


def build_context_block(entries: list[dict]) -> str:
    """
    Build a concise human-readable context block for injection into the AI prompt.
    Each entry takes ~5 lines so a list of 10 codes stays under ~50 lines.
    """
    if not entries:
        return ""
    lines = [
        "══════════════════════════════════════════════",
        "AUTHORITATIVE OBD CODE DATABASE",
        "Use entries below as the PRIMARY technical source for detected codes.",
        "══════════════════════════════════════════════",
    ]
    for e in entries:
        lines += [
            f"\n[{e['code']}] {e.get('title', 'Unknown')}",
            f"  System   : {e.get('system_he', '')}",
            f"  Severity : {e.get('severity', '')} | Drive: {e.get('safe_to_drive', '')}",
            f"  Causes   : {' | '.join(e.get('causes_he', [])[:3])}",
            f"  Actions  : {' | '.join(e.get('actions_he', [])[:3])}",
            f"  Cost (₪) : {e.get('cost_range_ils', 'לא ידוע')}",
        ]
    lines.append("══════════════════════════════════════════════")
    return "\n".join(lines)


def enrich_detected_codes(ai_codes: list[dict]) -> list[dict]:
    """
    Merge AI-generated OBD code entries with database knowledge.
    AI descriptions are kept; database fields are added / used as fallback.
    """
    enriched = []
    for item in ai_codes:
        if not isinstance(item, dict):
            continue
        code = item.get("code", "").strip().upper()
        db_entry = _DB.get(code, {})
        enriched.append({
            "code":               code,
            "description":        item.get("description", db_entry.get("system_he", "")),
            "severity":           item.get("severity")  or db_entry.get("severity", "בינוני"),
            "title":              db_entry.get("title", ""),
            "common_causes":      db_entry.get("causes_he", []),
            "recommended_actions":db_entry.get("actions_he", []),
            "cost_range":         db_entry.get("cost_range_ils", "") + " ₪" if db_entry.get("cost_range_ils") else "",
            "safe_to_drive":      db_entry.get("safe_to_drive", ""),
        })
    return enriched


def db_size() -> int:
    return len(_DB)
