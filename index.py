from flask import Flask, request, render_template_string, jsonify, send_file, session
from datetime import datetime
import math
import json
import io
import subprocess
import uuid
import speedtest
# PDF generation imports
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_RIGHT, TA_CENTER

app = Flask(__name__)
app.secret_key = 'isharati-pro-secret-key-2026'

# ==================== BTS DATA ====================
BTS_LIST = [
    {"name": "BTS-Center", "lat": 36.7538, "lon": 3.0588, "operator": "Mobilis"},
    {"name": "BTS-East", "lat": 36.7119, "lon": 3.1895, "operator": "Djezzy"},
    {"name": "BTS-West", "lat": 36.7431, "lon": 3.0372, "operator": "Ooredoo"},
    {"name": "BTS-North", "lat": 36.7838, "lon": 3.0688, "operator": "Mobilis"},
    {"name": "BTS-South", "lat": 36.7238, "lon": 3.0488, "operator": "Djezzy"},
]

# ==================== IN-MEMORY ANALYTICS STORAGE ====================
# In production, use a database (SQLite, PostgreSQL, etc.)
analytics_history = []

# ==================== UTILITY FUNCTIONS ====================
def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance between two points on Earth"""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def run_speedtest():
    """Run speedtest using the Python library directly (No subprocess)"""
    try:
        # إنشاء كائن الاختبار
        st = speedtest.Speedtest()
        
        # البحث عن أفضل سيرفر (هذه الخطوة ضرورية جداً)
        st.get_best_server()
        
        # قياس التحميل والرفع
        # ملاحظة: العمليات التالية تأخذ وقتاً (حوالي 20-30 ثانية)
# Sanity limits (realistic mobile network limits)
download_speed = min(download_speed, 300)   # Mbps
upload_speed = min(upload_speed, 100)       # Mbps
ping = max(ping, 5)                          # ms
        
        return {
            'download': round(download_speed, 2),
            'upload': round(upload_speed, 2),
            'ping': round(ping, 2)
        }
    except Exception as e:
        # إذا كان هناك خطأ في الاتصال بالإنترنت أو السيرفر
        return {'error': f'فشل الاختبار: تأكد من اتصالك بالإنترنت ({str(e)})'}

# ==================== ADVANCED DIAGNOSTIC ENGINE ====================
class NetworkDiagnosticEngine:
    @staticmethod
    def classify_rsrp(rsrp):
        if rsrp > -80:
            return {"status": "ممتازة", "rating": "Excellent", "emoji": "✅", "score": 100}
        elif rsrp > -90:
            return {"status": "جيدة جداً", "rating": "Very Good", "emoji": "✅", "score": 85}
        elif rsrp > -100:
            return {"status": "جيدة", "rating": "Good", "emoji": "⚠️", "score": 70}
        elif rsrp > -110:
            return {"status": "متوسطة", "rating": "Fair", "emoji": "⚠️", "score": 50}
        else:
            return {"status": "ضعيفة جداً", "rating": "Poor", "emoji": "❌", "score": 20}
    
    @staticmethod
    def classify_sinr(sinr):
        if sinr > 20:
            return {"status": "ممتازة (سرعة عالية)", "rating": "Excellent", "emoji": "📶", "score": 100}
        elif sinr > 13:
            return {"status": "جيدة جداً", "rating": "Very Good", "emoji": "📶", "score": 85}
        elif sinr > 0:
            return {"status": "مقبولة", "rating": "Acceptable", "emoji": "📶", "score": 60}
        else:
            return {"status": "سيئة (تشويش عالي)", "rating": "Poor", "emoji": "🚫", "score": 20}
    
    @staticmethod
    def estimate_distance_category(distance):
        if distance < 0.5:
            return {"category": "قريب جداً", "desc": "Near tower", "emoji": "✅"}
        elif distance < 2:
            return {"category": "قريب", "desc": "Close to tower", "emoji": "✅"}
        elif distance < 5:
            return {"category": "متوسط", "desc": "Medium distance", "emoji": "⚠️"}
        elif distance < 10:
            return {"category": "بعيد", "desc": "Far from tower", "emoji": "⚠️"}
        else:
            return {"category": "بعيد جداً", "desc": "Very far", "emoji": "❌"}
    
    @staticmethod
    def detect_issue_type(rsrp, sinr, download_speed=None):
        if rsrp > -95 and sinr < 5:
            return {
                "type": "interference",
                "ar": "تداخل في الإشارة",
                "explanation": "الإشارة قوية لكن هناك تشويش من أبراج أخرى"
            }
        elif rsrp < -105:
            return {
                "type": "coverage",
                "ar": "مشكلة تغطية",
                "explanation": "الإشارة ضعيفة بسبب البعد عن البرج"
            }
        elif download_speed and download_speed < 5 and rsrp > -90 and sinr > 10:
            return {
                "type": "congestion",
                "ar": "ازدحام على البرج",
                "explanation": "الإشارة جيدة لكن البرج مزدحم"
            }
        else:
            return {
                "type": "normal",
                "ar": "طبيعي",
                "explanation": "القيم ضمن المعدل الطبيعي"
            }
    
    @staticmethod
    def calculate_network_score(rsrp, sinr, download=None):
        engine = NetworkDiagnosticEngine()
        rsrp_class = engine.classify_rsrp(rsrp)
        sinr_class = engine.classify_sinr(sinr)
        
        score = (rsrp_class['score'] * 0.4) + (sinr_class['score'] * 0.4)
        
        if download is not None:
            if download > 20:
                speed_score = 100
            elif download > 10:
                speed_score = 80
            elif download > 5:
                speed_score = 60
            else:
                speed_score = 40
            score += speed_score * 0.2
        else:
            score = (rsrp_class['score'] * 0.5) + (sinr_class['score'] * 0.5)
        
        return round(score, 1)
    
    @staticmethod
    def get_star_rating(score):
        if score >= 90:
            return "⭐⭐⭐⭐⭐"
        elif score >= 75:
            return "⭐⭐⭐⭐"
        elif score >= 60:
            return "⭐⭐⭐"
        elif score >= 40:
            return "⭐⭐"
        else:
            return "⭐"

def analyze_network(lat, lon, rsrp, sinr, network_type, operator, place, wilaya, city, speed_data=None):
    """Advanced network analysis with comprehensive diagnostics"""
    engine = NetworkDiagnosticEngine()
    
    # Find nearest BTS
    operator_towers = [b for b in BTS_LIST if b["operator"] == operator]
    if not operator_towers:
        operator_towers = BTS_LIST
    
    distances = [haversine(lat, lon, b["lat"], b["lon"]) for b in operator_towers]
    min_dist = min(distances)
    closest_bts = operator_towers[distances.index(min_dist)]
    dist_category = engine.estimate_distance_category(min_dist)
    
    # Classify signals
    rsrp_class = engine.classify_rsrp(rsrp)
    sinr_class = engine.classify_sinr(sinr)
    
    # Detect issue
    download_speed = speed_data.get('download') if speed_data else None
    issue_type = engine.detect_issue_type(rsrp, sinr, download_speed)
    
    # Generate summary (for display)
    summary = []
    summary.append(f"📍 المسافة لأقرب برج ({closest_bts['name']} - {operator}): {min_dist:.2f} كم")
    summary.append(f"{dist_category['emoji']} {dist_category['category']} من البرج")
    summary.append(f"{rsrp_class['emoji']} قوة الإشارة (RSRP): {rsrp_class['status']}")
    summary.append(f"{sinr_class['emoji']} جودة الإشارة (SINR): {sinr_class['status']}")
    
    if speed_data and 'download' in speed_data:
        summary.append(f"⚡ سرعة التحميل: {speed_data['download']} Mbps")
        summary.append(f"⬆️ سرعة الرفع: {speed_data['upload']} Mbps")
        summary.append(f"📡 Ping: {speed_data['ping']} ms")
    
    hour = datetime.now().hour
    if 18 <= hour <= 23:
        summary.append("⏰ تنبيه: وقت ذروة (18:00-23:00)")
    
    # Technical explanation
    technical_explanation = {
        "rsrp_explanation": f"RSRP يقيس قوة الإشارة. قيمتك {rsrp} dBm تعني إشارة {rsrp_class['status']}.",
        "sinr_explanation": f"SINR يقيس نقاء الإشارة. قيمتك {sinr} dB تعني جودة {sinr_class['status']}.",
        "distance_explanation": f"المسافة {min_dist:.2f} كم من البرج - {dist_category['category']}.",
        "issue_diagnosis": issue_type['explanation'],
        "network_type_info": f"شبكة {network_type} من {operator}.",
        "location_impact": f"موقعك {place} في {city}, {wilaya}."
    }
    
    # Recommendations
    recommendations = {"physical": [], "network": [], "usage": []}
    
    if place == "Indoor" and rsrp < -100:
        recommendations["physical"].append("📍 اقترب من النافذة")
        recommendations["physical"].append("📍 فكر في مقوي إشارة (Repeater)")
    
    if sinr < 5:
        recommendations["network"].append("📡 حاول تغيير موقعك لتقليل التداخل")
        recommendations["network"].append("📡 أعد تشغيل الهاتف")
    
    if hour >= 18 and hour <= 23:
        recommendations["usage"].append("⏱ تجنب التحميلات الكبيرة الآن (وقت الذروة)")
    
    recommendations["usage"].append("⏱ أغلق التطبيقات غير المستخدمة")
    
    if speed_data and speed_data.get('download', 0) < 1:
        recommendations["usage"].append("📱 السرعة منخفضة جداً - تحقق من الباقة")
    
    # Calculate score
    network_score = engine.calculate_network_score(rsrp, sinr, download_speed)
    star_rating = engine.get_star_rating(network_score)
    
    score_breakdown = {
        "overall": network_score,
        "stars": star_rating,
        "coverage": rsrp_class['score'],
        "quality": sinr_class['score'],
        "speed": round((download_speed / 50) * 100) if download_speed else None
    }
    
    # Short recommendation
    if issue_type['type'] == 'coverage':
        if place == "Indoor":
            rec = "الإشارة ضعيفة داخل المبنى. الحل الأمثل: تركيب مقوي شبكة (Repeater) أو استخدام WiFi Calling."
        else:
            rec = "الإشارة ضعيفة حتى في الخارج. المنطقة قد تكون في ظل تغطية (Coverage Hole)."
    elif issue_type['type'] == 'interference':
        rec = "الإشارة قوية لكن الجودة سيئة. هذا يعني وجود 'تداخل' (Interference) من أبراج أخرى. جرب تغيير الغرفة لعزل التشويش."
    elif issue_type['type'] == 'congestion':
        rec = "الإشارة ممتازة لكن السرعة بطيئة. البرج مزدحم بالمشتركين. جرب في وقت آخر."
    else:
        rec = "القيم تبدو جيدة. إذا كان النت بطيئاً، فالمشكلة غالباً من المصدر (تشبع البرج بالمشتركين) وليس من تغطيتك."
    
    # Enhanced recommendation with speed test data
    if speed_data and 'download' in speed_data:
        download = speed_data['download']
        if download < 1:
            rec += " سرعة التحميل بطيئة جداً (<1 Mbps). تحقق من الباقة المشترك بها أو اتصل بمزود الخدمة."
        elif download < 5:
            rec += " سرعة التحميل محدودة (1-5 Mbps). مناسبة للتصفح الأساسي فقط."
        elif download < 20:
            rec += " سرعة التحميل جيدة (5-20 Mbps). مناسبة للفيديو بجودة HD."
        else:
            rec += " سرعة التحميل ممتازة (>20 Mbps). يمكنك البث بجودة 4K."
    
    return summary, technical_explanation, recommendations, network_score, score_breakdown, rec, issue_type

def save_analytics_record(data, analysis_results):
    """Save an analytics record to the history"""
    record = {
        'id': str(uuid.uuid4())[:8],
        'timestamp': datetime.now().isoformat(),
        'date': datetime.now().strftime("%Y-%m-%d"),
        'time': datetime.now().strftime("%H:%M:%S"),
        'lat': data['lat'],
        'lon': data['lon'],
        'rsrp': data['rsrp'],
        'sinr': data['sinr'],
        'network_type': data['network'],
        'operator': data['operator'],
        'place': data['place'],
        'wilaya': data['wilaya'],
        'city': data['city'],
        'speed_data': data.get('speed_data'),
        'network_score': analysis_results['network_score'],
        'score_breakdown': analysis_results['score_breakdown'],
        'issue_type': analysis_results['issue_type'],
        'summary': analysis_results['summary'],
        'recommendations': analysis_results['recommendations'],
        'short_recommendation': analysis_results['short_recommendation']
    }
    analytics_history.insert(0, record)  # Most recent first
    return record['id']

def get_analytics_stats():
    """Calculate statistics from analytics history"""
    if not analytics_history:
        return {
            'total': 0,
            'most_used_operator': 'N/A',
            'most_frequent_issue': 'N/A',
            'average_score': 0
        }
    
    operators = {}
    issues = {}
    total_score = 0
    
    for record in analytics_history:
        # Count operators
        op = record['operator']
        operators[op] = operators.get(op, 0) + 1
        
        # Count issues
        issue = record['issue_type']['ar']
        issues[issue] = issues.get(issue, 0) + 1
        
        # Sum scores
        total_score += record['network_score']
    
    most_used_operator = max(operators.items(), key=lambda x: x[1])[0] if operators else 'N/A'
    most_frequent_issue = max(issues.items(), key=lambda x: x[1])[0] if issues else 'N/A'
    average_score = round(total_score / len(analytics_history), 1) if analytics_history else 0
    
    return {
        'total': len(analytics_history),
        'most_used_operator': most_used_operator,
        'most_frequent_issue': most_frequent_issue,
        'average_score': average_score
    }

# ==================== PDF GENERATION ====================
def generate_advanced_pdf(data):
    """Generate comprehensive PDF report"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor('#0052FF'), 
                                 spaceAfter=20, alignment=TA_CENTER, fontName='Helvetica-Bold')
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#0052FF'),
                                   spaceAfter=10, alignment=TA_RIGHT, fontName='Helvetica-Bold')
    
    # Title
    elements.append(Paragraph("ISHARATI PRO - Network Analysis Report", title_style))
    elements.append(Spacer(1, 20))
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_id = f"RPT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Cover info
    cover_data = [
        ['Report ID:', report_id],
        ['Date & Time:', current_time],
        ['Location:', f"{data.get('city', 'N/A')}, {data.get('wilaya', 'N/A')}"],
        ['Operator:', data.get('operator', 'N/A')],
        ['Network Type:', data.get('network', 'N/A')],
        ['Platform:', 'ISHARATI PRO v1.0']
    ]
    
    cover_table = Table(cover_data, colWidths=[6*cm, 11*cm])
    cover_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
    ]))
    
    elements.append(cover_table)
    elements.append(Spacer(1, 20))
    
    # Network Score Section
    elements.append(Paragraph("Network Quality Score", heading_style))
    
    score_breakdown = data.get('score_breakdown', {})
    score_data = [
        ['Category', 'Score'],
        ['Overall Quality', f"{score_breakdown.get('overall', 0)}/100 "],
        ['Coverage (RSRP)', f"{score_breakdown.get('coverage', 0)}/100"],
        ['Signal Quality (SINR)', f"{score_breakdown.get('quality', 0)}/100"],
    ]
    
    if score_breakdown.get('speed'):
        score_data.append(['Speed Performance', f"{score_breakdown.get('speed', 0)}/100"])
    
    score_table = Table(score_data, colWidths=[8*cm, 9*cm])
    score_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, 1), 14),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('PADDING', (0, 0), (-1, -1), 10),
    ]))
    
    elements.append(score_table)
    elements.append(Spacer(1, 20))
    
    # Input Parameters
    elements.append(Paragraph("Technical Parameters", heading_style))
    
    input_data = [
        ['Parameter', 'Value'],
        ['Latitude', str(data.get('lat', 'N/A'))],
        ['Longitude', str(data.get('lon', 'N/A'))],
        ['RSRP (Signal Strength)', f"{data.get('rsrp', 'N/A')} dBm"],
        ['SINR (Signal Quality)', f"{data.get('sinr', 'N/A')} dB"],
        ['Network Type', data.get('network', 'N/A')],
        ['Operator', data.get('operator', 'N/A')],
        ['Location Type', data.get('place', 'N/A')],
        ['City', data.get('city', 'N/A')],
        ['Wilaya', data.get('wilaya', 'N/A')],
    ]
    
    if data.get('speed_data'):
        speed = data['speed_data']
        input_data.append(['Download Speed', f"{speed.get('download', 'N/A')} Mbps"])
        input_data.append(['Upload Speed', f"{speed.get('upload', 'N/A')} Mbps"])
        input_data.append(['Ping', f"{speed.get('ping', 'N/A')} ms"])
    
    input_table = Table(input_data, colWidths=[8*cm, 9*cm])
    input_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0052FF')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    
    elements.append(input_table)
    elements.append(Spacer(1, 20))
    
    # Footer
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("---------------------------------------------------------------------", styles['Normal']))
    elements.append(Paragraph("Generated by ISHARATI PRO v1.0 - Advanced Network Diagnostic Platform", styles['Normal']))
    elements.append(Paragraph("For support: isharatipro@gmail.com", styles['Normal']))
    
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

HTML_PAGE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/png" href="{{ url_for('static', filename='logo2.png') }}">
    <title>ISHARATI PRO - تشخيص احترافي للشبكة</title>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&family=IBM+Plex+Sans+Arabic:wght@400;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<style>
:root {
--primary: #0052FF;
            --primary-dark: #003db3;
            --secondary: #10b981;
            --accent: #f59e0b;
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text: #1e293b;
            --text-light: #64748b;
            --border: #e2e8f0;
            --shadow-sm: 0 1px 3px rgba(0,0,0,0.12);
            --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.1);
            --shadow-lg: 0 20px 25px -5px rgba(0,0,0,0.1);
            --radius: 12px;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body { 
font-family: 'IBM Plex Sans Arabic', sans-serif; 
            background: var(--bg); 
            color: var(--text);
            line-height: 1.6;
}
.brand {
            display: flex;
            align-items: center;
            gap: 15px;
            text-decoration: none;
        }

        .logo-img { height: 45px; width: auto; }

        .brand-text h1 {
            font-size: 1.2rem;
            font-weight: 800;
            color: var(--primary);
            line-height: 1;
        }

        .brand-text p { font-size: 0.7rem; color: var(--text-light); }

        .search-bar {
            flex: 1;
            max-width: 500px;
            position: relative;
            display: none; /* Hidden on mobile */
        }
/* ========== HEADER SECTION ========== */
.main-header {
background: white;
            padding: 12px 0;
            border-bottom: 1px solid var(--border);
            position: sticky;
            top: 0;
            z-index: 2000;
}

.header-content {
max-width: 1400px;
            margin: 0 auto;
            padding: 0 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 20px;
}

.logo-section {
    display: flex;
    align-items: center;
    gap: 12px;
    text-decoration: none;
}
.logo-icon {
    background: linear-gradient(135deg, var(--primary), var(--primary-dark));
    width: 45px;
    height: 45px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
}

.logo-text h1 {
    font-size: 1.5rem;
    font-weight: 900;
    color: var(--primary);
    font-family: 'Tajawal', sans-serif;
}

.logo-text p {
    font-size: 0.75rem;
    color: var(--text-light);
}


.logo-text p {
    font-size: 0.75rem;
    color: var(--text-light);
}

.search-container {
    flex: 1;
    max-width: 600px;
    position: relative;
}

.search-wrapper {
    position: relative;
    display: flex;
    align-items: center;
}

.search-input {
    width: 100%;
    padding: 12px 50px 12px 20px;
    border: 2px solid var(--border);
    border-radius: 50px;
    font-size: 0.95rem;
    transition: all 0.3s;
    font-family: inherit;
}

.search-input:focus {
    outline: none;
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(0, 82, 255, 0.1);
}

.search-btn {
    position: absolute;
    left: 5px;
    background: var(--primary);
    color: white;
    border: none;
    padding: 8px 20px;
    border-radius: 50px;
    cursor: pointer;
    transition: background 0.3s;
}

.search-btn:hover { background: var(--primary-dark); }

.cta-btn {
    background: var(--primary);
    color: white;
    padding: 10px 25px;
    border-radius: 50px;
    text-decoration: none;
    font-weight: 700;
    transition: all 0.3s;
    border: none;
    cursor: pointer;
}

.cta-btn:hover {
    background: var(--primary-dark);
    transform: translateY(-2px);
    box-shadow: var(--shadow);
}
@media (min-width: 992px) { .search-bar { display: block; } }

        .search-bar input {
            width: 100%;
            padding: 10px 45px 10px 15px;
            border-radius: 50px;
            border: 1px solid var(--border);
            background: #f1f5f9;
            transition: 0.3s;
        }

        .search-bar i {
            position: absolute;
            right: 15px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-light);
        }
/* ========== NAVIGATION ========== */
.main-nav {
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid #eee;
    padding: 15px 0;
    width: 100%;
    position: sticky;
    top: 0;
    z-index: 1000;
    display: flex;
    justify-content: center;
}

.nav-content {
    display: flex;
    gap: 15px;
    direction: rtl;
    align-items: center;
}

.nav-item {
    text-decoration: none;
    color: #555;
    padding: 10px 20px;
    border-radius: 12px;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    font-weight: 600;
    font-size: 15px;
    display: flex;
    align-items: center;
    gap: 10px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.nav-item i {
    font-size: 18px;
}

.nav-item:hover {
    background-color: #f0f7ff;
    color: #007bff;
    transform: translateY(-2px);
}

.nav-item.active {
    background-color: #007bff;
    color: #ffffff;
    box-shadow: 0 4px 12px rgba(0, 123, 255, 0.3);
}
.nav-bar {
    background: rgba(255,255,255,0.8);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border);
    padding: 0; /* Changed from 10px */
    position: sticky;
    top: 0; /* Changed from 70px */
    z-index: 1000;
}

        .nav-container {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            justify-content: center;
            gap: 10px;
            overflow-x: auto;
            white-space: nowrap;
            padding: 0 10px;
        }

        .nav-link {
            text-decoration: none;
            color: var(--text-light);
            padding: 8px 16px;
            border-radius: 50px;
            font-weight: 600;
            font-size: 0.95rem;
            transition: 0.3s;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .nav-link:hover, .nav-link.active {
            color: var(--primary);
            background: rgba(0, 82, 255, 0.1);
        }
/* ========== HERO SECTION ========== */
.hero {
    background: linear-gradient(145deg, #0052FF 0%, #002e8f 100%);
    color: white;
    padding: 80px 20px 20px; /* Changed from 120px to 20px */
    text-align: center;
}
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}
        .hero h1 { font-size: clamp(1.8rem, 5vw, 3rem); font-weight: 800; margin-bottom: 15px; }
        .hero p { font-size: 1.1rem; opacity: 0.9; max-width: 700px; margin: 0 auto; }
.hero-content {
    max-width: 1200px;
    margin: 0 auto;
    text-align: center;
    position: relative;
    z-index: 1;
}

.hero h1 {
    color: white;
    font-size: 3rem;
    font-weight: 900;
    margin-bottom: 20px;
    text-shadow: 0 2px 10px rgba(0,0,0,0.2);
}

.hero p {
    color: rgba(255,255,255,0.95);
    font-size: 1.3rem;
    margin-bottom: 30px;
}

/* ========== MAIN CONTENT ========== */
.container {
    max-width: 1400px;
    margin: 20px auto 100px; /* Changed from -60px to 20px */
    padding: 0 20px;
    position: relative;
    z-index: 10;
}
.content-grid {
    display: grid;
    grid-template-columns: 1fr 350px;
    gap: 30px;
    margin-bottom: 40px;
    min-height: 150vh;
}

.main-content {
    display: flex;
    flex-direction: column;
    gap: 30px;
}

.card {
    background: var(--card-bg);
    padding: 50px;
    border-radius: 20px;
    box-shadow: var(--shadow);
    border: 1px solid var(--border);
    margin-bottom: 40px;
}

.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 30px;
    padding-bottom: 20px;
    border-bottom: 2px solid var(--border);
}

.card-title {
    font-size: 1.5rem;
    font-weight: 800;
    color: var(--text);
    display: flex;
    align-items: center;
    gap: 10px;
}

.form-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr); /* Exactly 3 columns as per your image */
    gap: 25px 20px; /* Vertical and horizontal spacing */
    margin-bottom: 30px;
    direction: rtl; /* Ensures order matches your image from right to left */
}
.form-group {
    display: flex;
    flex-direction: column;
    align-items: flex-start; /* Align contents to the right (start of RTL) */
}

label {
    font-weight: 700;
    color: var(--text);
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
}

label small {
    color: var(--text-light);
    font-weight: 400;
    font-size: 0.85rem;
}

input, select {
    width: 100%;
    padding: 12px 15px;
    border: 2px solid var(--border);
    border-radius: 12px;
    font-size: 1rem;
    transition: all 0.3s;
    font-family: inherit;
    background: white;
}

input:focus, select:focus {
    outline: none;
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(0, 82, 255, 0.1);
}

.btn {
    background: var(--primary);
    color: white;
    padding: 15px 30px;
    border: none;
    border-radius: 50px;
    font-size: 1.1rem;
    font-weight: 700;
    cursor: pointer;
    width: 100%;
    transition: all 0.3s;
    margin-top: 20px;
}

.btn:hover {
    background: var(--primary-dark);
    transform: translateY(-2px);
    box-shadow: var(--shadow-lg);
}

.btn:disabled {
    background: #94a3b8;
    cursor: not-allowed;
    transform: none;
}

.btn-secondary {
    background: var(--secondary);
}

.btn-secondary:hover {
    background: #059669;
}

.btn-accent {
    background: var(--accent);
    margin-top: 15px;
}

.btn-accent:hover {
    background: #d97706;
}

.result {
    background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
    border: 2px solid var(--secondary);
    padding: 40px;
    border-radius: 20px;
    margin-top: 40px;
    margin-bottom: 40px;
}

.result h3 {
    color: var(--secondary);
    font-size: 1.5rem;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 10px;
}

.result ul {
    list-style: none;
    padding: 0;
    margin: 30px 0;
}

.result li {
    padding: 18px 0;
    border-bottom: 1px solid rgba(16, 185, 129, 0.2);
    font-size: 1.05rem;
}

.result li:last-child { border-bottom: none; }

.recommendation {
    background: white;
    padding: 20px;
    border-radius: 15px;
    margin-top: 20px;
    border-right: 5px solid var(--accent);
}

.recommendation strong {
    color: var(--accent);
    font-size: 1.1rem;
}

/* ========== NETWORK SCORE DISPLAY ========== */
.score-display {
    text-align: center;
    padding: 30px;
    background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
    border-radius: 20px;
    margin: 20px 0;
    border: 2px solid var(--primary);
}

.score-number {
    font-size: 4rem;
    font-weight: 900;
    color: var(--primary);
    margin: 10px 0;
}

.score-stars {
    font-size: 2.5rem;
    margin: 10px 0;
}

.score-label {
    font-size: 1.1rem;
    color: var(--text-light);
    margin-top: 10px;
}

/* ========== SPEED TEST SECTION ========== */
.speed-test-section {
    background: white;
    padding: 25px;
    border-radius: 15px;
    margin-top: 20px;
    border: 2px solid var(--primary);
}

.speed-test-section h4 {
    color: var(--primary);
    margin-bottom: 15px;
    display: flex;
    align-items: center;
    gap: 10px;
}

.speed-results {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 15px;
    margin-top: 15px;
}

.speed-metric {
    text-align: center;
    padding: 15px;
    background: var(--bg);
    border-radius: 10px;
}

.speed-value {
    font-size: 2rem;
    font-weight: bold;
    color: var(--primary);
}

.speed-label {
    font-size: 0.9rem;
    color: var(--text-light);
    margin-top: 5px;
}

.loading-spinner {
    display: inline-block;
    width: 20px;
    height: 20px;
    border: 3px solid rgba(255,255,255,0.3);
    border-radius: 50%;
    border-top-color: white;
    animation: spin 1s ease-in-out infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* ========== SIDEBAR ========== */
.sidebar {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.sidebar-card {
    background: var(--card-bg);
    padding: 25px;
    border-radius: 20px;
    box-shadow: var(--shadow);
    border: 1px solid var(--border);
    border-radius: 16px;
    position: relative;
    overflow: hidden;
    transition: transform 0.3s ease, box-shadow 0.3s ease;
    cursor: pointer;
    animation: slideIn 0.6s ease-out;
}

.sidebar-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 10px 30px rgba(0,0,0,0.15);
}

.sidebar-card h3 {
    font-size: 1.2rem;
    margin-bottom: 15px;
    color: var(--text);
    display: flex;
    align-items: center;
    gap: 10px;
}

.sidebar-card h3 i {
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.2); opacity: 0.8; }
    100% { transform: scale(1); opacity: 1; }
}

@keyframes slideIn {
    from { opacity: 0; transform: translateX(20px); }
    to { opacity: 1; transform: translateX(0); }
}

.quick-link {
    display: block;
    padding: 12px 15px;
    background: var(--bg);
    border-radius: 12px;
    text-decoration: none;
    color: var(--text);
    margin-bottom: 10px;
    transition: all 0.3s;
    font-weight: 600;
}

.quick-link:hover {
    background: var(--primary);
    color: white;
    transform: translateX(-5px);
}

/* ========== FOOTER ========== */
.footer {
    background: #1e293b;
    color: white;
    /* Reduced top padding from 80px to 40px */
    padding: 40px 20px 20px; 
    /* Reduced margin from 120px to 40px to pull it closer to content */
    margin-top: 40px; 
}

.footer-content {
    max-width: 1400px;
    margin: 0 auto;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    /* Reduced gap between columns */
    gap: 20px; 
    margin-bottom: 20px;
    direction: rtl; /* Ensures alignment matches your Arabic text */
}

.footer-section h3 {
    /* Smaller headings */
    font-size: 1.1rem;
    margin-bottom: 12px;
    color: var(--secondary);
}


.footer-section a, 
.footer-section a:visited, 

    
    
.footer-section p, 
.footer-section a {
    /* Smaller text for a more compact look */
    font-size: 0.85rem;
    color: #ffffff;
}
.footer-section ul {
    list-style: none;
    padding: 0;
    margin: 0;
}
.footer-bottom {
    text-align: center;
    /* Reduced padding */
    padding-top: 20px;
    border-top: 1px solid rgba(255,255,255,0.1);
    color: rgba(255,255,255,0.6);
    font-size: 0.8rem;
}

.footer-bottom p {
    margin-bottom: 5px;
}

/* ========== RESPONSIVE ========== */
@media (max-width: 1024px) {
    .content-grid {
        grid-template-columns: 1fr;
    }
    
    .sidebar {
        order: -1;
    }
}

@media (max-width: 768px) {
    .header-content {
        flex-wrap: wrap;
    }
    
    .search-container {
        order: 3;
        width: 100%;
        max-width: 100%;
    }
    
    .hero h1 {
        font-size: 2rem;
    }
    
    .form-grid {
        grid-template-columns: 1fr;
    }
    
    .speed-results {
        grid-template-columns: 1fr;
    }

    .nav-content {
        gap: 5px;
        padding: 0 10px;
    }
    
    .nav-item {
        padding: 8px 12px;
        font-size: 14px;
    }
}
</style>
</head>

<body>

<!-- Main Header -->
<header class="main-header">
    <div class="header-content">

<div class="logo">
    <img 
<link rel="icon" type="image/png" href="{{ url_for('static', filename='logo2.png') }}">
<img src="logo2.png">        alt="Logo"
        style="height: 50px; width: center;"
    >
</div>
            <div class="logo-text">
                <h1>ISHARATI PRO</h1>
                <p>تشخيص احترافي للشبكة</p>
            </div>
        </a>

        <div class="search-container">
            <div class="search-wrapper">
                <input type="text" class="search-input" id="searchInput" placeholder="ابحث عن مشكلة، منطقة، أو مقال...">
                <button class="search-btn" onclick="performSearch()">
                    <i class="fas fa-search"></i>
                </button>
            </div>
        </div>

        <a href="/guide" class="cta-btn">دليل الاستخدام</a>
    </div>
</header>

<!-- Navigation -->
<nav class="main-nav">
    <div class="nav-content" id="mainNav">
        <a href="/" class="nav-item active">
            <i class="fas fa-home"></i> الرئيسية
        </a>
        <a href="/speed-test" class="nav-item">
            <i class="fas fa-tachometer-alt"></i> اختبار السرعة
        </a>
        <a href="/knowledge" class="nav-item">
            <i class="fas fa-newspaper"></i> معرفة
        </a>
        <a href="/guide" class="nav-item">
            <i class="fas fa-book-open"></i> الدليل
        </a>
        <a href="/analytics" class="nav-item">
    <i class="fas fa-chart-line"></i> السجل
        </a>

    </div>
</nav>

<!-- Hero Section -->
<section class="hero">
    <div class="hero-content">
        <h1>شخّص سبب ضعف الإنترنت بدقة عالية</h1>
        <p>أدخل البيانات واحصل على تحليل هندسي شامل مع توصيات عملية</p>
    </div>
</section>


<!-- Main Content -->
<div class="container">
    <div class="content-grid">
        <!-- Main Analysis Form -->
        <div class="main-content">
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">
                        <i class="fas fa-microscope"></i>
                        نموذج التحليل الشامل
                    </h2>
                </div>

                <form method="POST" id="analysisForm">
<div class="form-grid">
    <div class="form-group">
        <label>Latitude <small>(خط العرض)</small> <i class="fas fa-map-marker-alt"></i></label>
        <input name="lat" type="number" step="any" placeholder="36.75">
    </div>

    <div class="form-group">
        <label>Longitude <small>(خط الطول)</small> <i class="fas fa-map-marker-alt"></i></label>
        <input name="lon" type="number" step="any" placeholder="3.05">
    </div>

    <div class="form-group">
        <label>RSRP (dBm) <small>كلما اقترب من 0 أفضل</small> <i class="fas fa-signal"></i></label>
        <input type="number" name="rsrp" placeholder="85-">
    </div>

    <div class="form-group">
        <label>SINR (dB) <small>أكثر من 20 ممتاز</small> <i class="fas fa-chart-bar"></i></label>
        <input type="number" name="sinr" placeholder="15">
    </div>

    <div class="form-group">
        <label>Network Type <i class="fas fa-network-wired"></i></label>
        <select name="network">
                                 <option>3G</option>
                                 <option>4G</option>
                                <option>5G</option>
                                <option value="ADSL">Algerie Telecom (ADSL)</option>
        </select>
    </div>

    <div class="form-group">
        <label>المشغّل <i class="fas fa-signal"></i></label>
        <select name="operator">
            <option>Djezzy</option>
            <option>Mobilis</option>
            <option>Ooredoo</option>
            <option value="ADSL">Algerie Telecom (ADSL)</option>

        </select>
    </div>

    <div class="form-group">
        <label>المكان <i class="fas fa-location-arrow"></i></label>
        <select name="place">
            <option>Indoor</option>
            <option>Outdoor</option>
        </select>
    </div>

    <div class="form-group">
        <label>الولاية <i class="fas fa-city"></i></label>
        <input type="text" name="Wilaya" placeholder="مثال: بومرداس">
    </div>

    <div class="form-group">
        <label>المدينة <i class="fas fa-map-pin"></i></label>
        <input type="text" name="city" placeholder="مثال: الثنية">
    </div>
</div>

                    <button class="btn" type="submit">
                        <i class="fas fa-cogs"></i> ابدأ التحليل الهندسي الشامل
                    </button>
                    
                    <button class="btn btn-secondary" type="button" onclick="testSpeed()" id="speedTestBtn">
                        <i class="fas fa-tachometer-alt"></i> اختبر سرعة الإنترنت
                    </button>
                    
                    <input type="hidden" name="speed_data" id="speedDataInput">
                </form>

                <!-- Speed Test Results -->
                <div id="speedTestResults" style="display: none;" class="speed-test-section">
                    <h4><i class="fas fa-tachometer-alt"></i> نتائج اختبار السرعة</h4>
                    <div class="speed-results">
                        <div class="speed-metric">
                            <div class="speed-value" id="downloadSpeed">-</div>
                            <div class="speed-label">التحميل (Mbps)</div>
                        </div>
                        <div class="speed-metric">
                            <div class="speed-value" id="uploadSpeed">-</div>
                            <div class="speed-label">الرفع (Mbps)</div>
                        </div>
                        <div class="speed-metric">
                            <div class="speed-value" id="pingSpeed">-</div>
                            <div class="speed-label">Ping (ms)</div>
                        </div>
                    </div>
                </div>

                {% if analysis %}
                <div class="result">
                    <h3>
                        <i class="fas fa-check-circle"></i>
                        نتيجة التشخيص
                    </h3>
                    <ul>
                    {% for a in analysis %}
                        <li>{{a}}</li>
                    {% endfor %}
                    </ul>
                    
                    {% if network_score %}
                    <div class="score-display">
                        <div class="score-label">Network Quality Score</div>
                        <div class="score-number">{{network_score}}/100</div>
                        <div class="score-stars">{{star_rating}}</div>
                        <div class="score-label">تقييم جودة الشبكة</div>
                    </div>
                    {% endif %}
                    
                    <div class="recommendation">
                        <p><strong>💡 التوصية الهندسية:</strong></p>
                        <p>{{rec}}</p>
                    </div>
                    
                    <a href="/download_pdf" class="btn btn-accent" style="display: inline-block; text-decoration: none; text-align: center;">
                        <i class="fas fa-file-pdf"></i> تحميل التقرير الكامل PDF
                    </a>
                    
                    <canvas id="chart" height="100" style="margin-top: 30px;"></canvas>
                    <script>
                    new Chart(document.getElementById('chart'), {
                        type: 'bar',
                        data: {
                            labels: ['RSRP (قوة الإشارة)', 'SINR (الجودة)'],
                            datasets: [{
                                label: 'القيم الحالية',
                                data: [{{rsrp}}, {{sinr}}],
                                backgroundColor: ['#0052FF', '#10b981'],
                                borderRadius: 10,
                                borderWidth: 0
                            }]
                        },
                        options: {
                            responsive: true,
                            plugins: {
                                legend: { display: false }
                            },
                            scales: {
                                y: { beginAtZero: false }
                            }
                        }
                    });
                    </script>
                </div>
                {% endif %}
            </div>
        </div>

        <!-- Sidebar -->
        <aside class="sidebar">
            <div class="sidebar-card">
                <h3><i class="fas fa-bolt"></i> إجراءات سريعة</h3>
                <a href="/guide" class="quick-link">
                    <i class="fas fa-book"></i> دليل الاستخدام
                </a>
                <a href="/speed-test" class="quick-link">
                    <i class="fas fa-tachometer-alt"></i> اختبار السرعة
                </a>
                <a href="/knowledge" class="quick-link">
                    <i class="fas fa-lightbulb"></i> المعرفة التقنية
                </a>
                <a href="/analytics" class="quick-link">
    <i class="fas fa-chart-line"></i> السجل
</a>
<script>
    // منع الزر الأيمن للفأرة
    document.addEventListener('contextmenu', event => event.preventDefault());

    // منع اختصارات لوحة المفاتيح مثل Ctrl+U (رؤية السورس)
    document.onkeydown = function(e) {
        if (e.ctrlKey && (e.keyCode === 85 || e.keyCode === 83)) {
            return false;
        }
    };
</script>
            </div>

            <div class="sidebar-card" style="background: linear-gradient(135deg, #f8fafc, #e2e8f0); border: none;">
                <h3><i class="fas fa-lightbulb"></i> نصيحة اليوم</h3>
                <p style="font-size: 0.95rem; line-height: 1.8;">
                    لتحسين جودة الإشارة داخل المنزل، حاول الاقتراب من النافذة أو استخدام مقوي الإشارة (Repeater).
                </p>
            </div>
        </aside>
    </div>
</div>

<!-- Footer -->
<footer class="footer">
    <div class="footer-content">
        <div class="footer-section">
            <h3>حول ISHARATI PRO</h3>
            <p style="color: rgba(255,255,255,0.7); line-height: 1.8;">
                منصة لتشخيص مشاكل الشبكة وتحليل جودة الإنترنت باستخدام أحدث التقنيات الهندسية.
            </p>
        </div>
        
 
        
        <div class="footer-section">
            <h3>الدعم</h3>
            <ul>
                <li><a href="#">مركز المساعدة</a></li>
                <li><a href="#">اتصل بنا</a></li>
            </ul>
        </div>
        
        <div class="footer-section">
            <h3>معلومات قانونية</h3>
            <ul>
                <li><a href="#">سياسة الخصوصية</a></li>
                <li><a href="#">شروط الاستخدام</a></li>
                <li><a href="#">سياسة الكوكيز</a></li>
            </ul>
        </div>
    </div>
    
    <div class="footer-bottom">
        <p>&copy; 2026  ISHARATI PRO   v1.0   جميع الحقوق محفوظة.</p>
        <p>Advanced Network Diagnostic Platform</p>
    </div>
</footer>

<script>async function startTest() {
    const btn = document.getElementById('testBtn');
    const downloadEl = document.getElementById('downloadSpeed');
    const pingEl = document.getElementById('pingSpeed');
    
    btn.disabled = true;
    btn.innerHTML = 'جاري القياس الحقيقي...';

    const startTime = performance.now();
    
    try {
        // Measure Ping first
        const pingStart = performance.now();
        await fetch('/api/download-test', { method: 'HEAD' });
        const pingEnd = performance.now();
        pingEl.textContent = Math.round(pingEnd - pingStart);

        // Measure Download Speed
        const response = await fetch('/api/download-test', { cache: "no-store" });
        const reader = response.body.getReader();
        let receivedLength = 0;

        while(true) {
            const {done, value} = await reader.read();
            if (done) break;
            receivedLength += value.length;
        }

        const endTime = performance.now();
        const durationInSeconds = (endTime - startTime) / 1000;
        const bitsLoaded = receivedLength * 8;
        const speedMbps = ((bitsLoaded / durationInSeconds) / 1000000).toFixed(2);

        downloadEl.textContent = speedMbps;
        document.getElementById('uploadSpeed').textContent = (speedMbps * 0.2).toFixed(2); // Estimated upload

    } catch (error) {
        document.getElementById('errorLog').textContent = 'خطأ في الاتصال: جرب متصفح آخر';
        document.getElementById('errorLog').style.display = 'block';
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'إعادة الاختبار';
    }
}
function performSearch() {
    const query = document.getElementById('searchInput').value;
    if(query) {
        alert('البحث عن: ' + query);
    }
}
</script>

</body>
</html>
"""


ANALYTICS_PAGE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/png" href="{{ url_for('static', filename='logo2.png') }}">
    <title>السجل التاريخي للتحليلات - ISHARATI PRO</title>
    
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&family=IBM+Plex+Sans+Arabic:wght@400;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    
    <style>
    /* Your CSS starts here */
:root {
    --primary: #0052FF;
    --primary-dark: #003db3;
    --secondary: #10b981;
    --accent: #f59e0b;
    --danger: #ef4444;
    --bg: #f8fafc;
    --card-bg: white;
    --text: #1e293b;
    --text-light: #64748b;
    --border: #e2e8f0;
    --shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    --shadow-lg: 0 20px 25px -5px rgba(0,0,0,0.1);
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body { 
    font-family: 'IBM Plex Sans Arabic', 'Tajawal', sans-serif; 
    background: var(--bg); 
    color: var(--text);
    line-height: 1.6;
    min-height: 100vh;
}

/* ========== HEADER ========== */
.page-header {
    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
    color: white;
    padding: 30px 20px 20px; /* Reduced padding */
}

.header-content {
    max-width: 1200px; /* Narrowed width */
    margin: 0 auto;
}

.header-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
}
.back-link {
    font-size: 0.85rem;
    padding: 8px 16px;
    background: rgba(255,255,255,0.15);
    border-radius: 50px;
    text-decoration: none;
    color: white;
}
.header-title h1 {
    font-size: 1.8rem; /* Reduced from 2.5rem */
    margin-bottom: 5px;
}

.header-title p {
    font-size: 0.95rem;
    opacity: 0.8;
}
.back-link:hover {
    background: rgba(255,255,255,0.2);
    transform: translateX(5px);
}

.header-actions {
    display: flex;
    gap: 15px;
    align-items: center;
}

.search-box {
    position: relative;
}

.search-input {
    padding: 10px 40px 10px 20px;
    border: 2px solid rgba(255,255,255,0.3);
    border-radius: 50px;
    background: rgba(255,255,255,0.1);
    color: white;
    width: 300px;
    font-family: inherit;
}

.search-input::placeholder {
    color: rgba(255,255,255,0.7);
}

.search-input:focus {
    outline: none;
    background: rgba(255,255,255,0.15);
    border-color: rgba(255,255,255,0.5);
}

.search-icon {
    position: absolute;
    left: 15px;
    top: 50%;
    transform: translateY(-50%);
    color: rgba(255,255,255,0.7);
}

.clear-btn {
    background: var(--danger);
    color: white;
    padding: 10px 20px;
    border: none;
    border-radius: 50px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.3s;
    display: flex;
    align-items: center;
    gap: 8px;
}

.clear-btn:hover {
    background: #dc2626;
    transform: translateY(-2px);
}

.header-title h1 {
    font-size: 2.5rem;
    font-weight: 900;
    margin-bottom: 10px;
}

.header-title p {
    font-size: 1.1rem;
    opacity: 0.9;
}

/* ========== STATS OVERVIEW ========== */
.stats-container {
    max-width: 1400px;
    margin: 20px auto 40px; /* Changed -40px to 20px for a clear gap */
    padding: 0 20px;
    position: relative;
    z-index: 10;
}
.header-title {
    margin-bottom: 50px; /* Adjust this value to increase the space */
}
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 20px;
}

.stat-card {
    background: var(--card-bg);
    padding: 30px;
    border-radius: 20px;
    box-shadow: var(--shadow);
    border: 1px solid var(--border);
    transition: all 0.3s;
    position: relative;
    overflow: hidden;
}

.stat-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 4px;
    background: linear-gradient(90deg, var(--primary), var(--secondary));
}

.stat-card:hover {
    transform: translateY(-5px);
    box-shadow: var(--shadow-lg);
}

.stat-icon {
    width: 60px;
    height: 60px;
    border-radius: 15px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.8rem;
    margin-bottom: 15px;
}

.stat-icon.primary {
    background: linear-gradient(135deg, var(--primary), var(--primary-dark));
    color: white;
}

.stat-icon.secondary {
    background: linear-gradient(135deg, var(--secondary), #059669);
    color: white;
}

.stat-icon.accent {
    background: linear-gradient(135deg, var(--accent), #d97706);
    color: white;
}

.stat-icon.info {
    background: linear-gradient(135deg, #3b82f6, #2563eb);
    color: white;
}

.stat-value {
    font-size: 2.5rem;
    font-weight: 900;
    color: var(--text);
    margin-bottom: 5px;
}

.stat-label {
    color: var(--text-light);
    font-size: 0.95rem;
    font-weight: 600;
}

/* ========== MAIN CONTENT ========== */
.container {
    max-width: 1400px;
    margin: 0 auto 60px;
    padding: 0 20px;
}

/* ========== EMPTY STATE ========== */
.empty-state {
    background: var(--card-bg);
    border-radius: 20px;
    padding: 80px 40px;
    text-align: center;
    box-shadow: var(--shadow);
}

.empty-illustration {
    font-size: 8rem;
    margin-bottom: 30px;
    opacity: 0.3;
}

.empty-state h2 {
    font-size: 2rem;
    color: var(--text);
    margin-bottom: 15px;
}

.empty-state p {
    color: var(--text-light);
    font-size: 1.1rem;
    margin-bottom: 30px;
}

.empty-cta {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    background: var(--primary);
    color: white;
    padding: 15px 30px;
    border-radius: 50px;
    text-decoration: none;
    font-weight: 700;
    transition: all 0.3s;
}

.empty-cta:hover {
    background: var(--primary-dark);
    transform: translateY(-2px);
}

/* ========== ANALYTICS LIST ========== */
.analytics-list {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.analysis-card {
    background: var(--card-bg);
    border-radius: 20px;
    padding: 30px;
    box-shadow: var(--shadow);
    border: 1px solid var(--border);
    transition: all 0.3s;
    position: relative;
}

.analysis-card:hover {
    box-shadow: var(--shadow-lg);
    transform: translateY(-2px);
}

.card-header-section {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 20px;
    padding-bottom: 20px;
    border-bottom: 2px solid var(--bg);
}

.card-info {
    flex: 1;
}

.card-id {
    display: inline-block;
    background: linear-gradient(135deg, var(--primary), var(--primary-dark));
    color: white;
    padding: 5px 15px;
    border-radius: 20px;
    font-weight: 700;
    font-size: 0.85rem;
    margin-bottom: 10px;
}

.card-datetime {
    color: var(--text-light);
    font-size: 0.95rem;
    display: flex;
    align-items: center;
    gap: 15px;
    margin-bottom: 10px;
}

.card-location {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--text);
    display: flex;
    align-items: center;
    gap: 8px;
}

.operator-badge {
    display: inline-block;
    padding: 8px 16px;
    border-radius: 20px;
    font-weight: 700;
    font-size: 0.9rem;
}

.operator-djezzy {
    background: linear-gradient(135deg, #ef4444, #dc2626);
    color: white;
}

.operator-mobilis {
    background: linear-gradient(135deg, #10b981, #059669);
    color: white;
}

.operator-ooredoo {
    background: linear-gradient(135deg, #f59e0b, #d97706);
    color: white;
}

.operator-adsl {
    background: linear-gradient(135deg, #3b82f6, #2563eb);
    color: white;
}

.status-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 15px;
    margin: 20px 0;
}

.status-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px;
    background: var(--bg);
    border-radius: 12px;
}

.status-icon {
    font-size: 1.5rem;
}

.status-label {
    font-size: 0.85rem;
    color: var(--text-light);
}

.status-value {
    font-weight: 700;
    color: var(--text);
}

.diagnosis-summary {
    background: linear-gradient(135deg, #fef3c7, #fde68a);
    padding: 20px;
    border-radius: 15px;
    border-right: 4px solid var(--accent);
    margin: 20px 0;
}

.diagnosis-summary p {
    line-height: 1.8;
    color: var(--text);
}

.card-actions {
    display: flex;
    gap: 10px;
    justify-content: flex-end;
    margin-top: 20px;
}

.action-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 20px;
    border-radius: 50px;
    font-weight: 700;
    border: none;
    cursor: pointer;
    transition: all 0.3s;
    text-decoration: none;
}

.btn-view {
    background: var(--primary);
    color: white;
}

.btn-view:hover {
    background: var(--primary-dark);
    transform: translateY(-2px);
}

.btn-pdf {
    background: var(--secondary);
    color: white;
}

.btn-pdf:hover {
    background: #059669;
    transform: translateY(-2px);
}

.btn-delete {
    background: var(--danger);
    color: white;
}

.btn-delete:hover {
    background: #dc2626;
    transform: translateY(-2px);
}

/* ========== MODAL ========== */
.modal {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0,0,0,0.7);
    z-index: 1000;
    padding: 20px;
    overflow-y: auto;
}

.modal.active {
    display: flex;
    align-items: center;
    justify-content: center;
}

.modal-content {
    background: var(--card-bg);
    border-radius: 20px;
    max-width: 900px;
    width: 100%;
    max-height: 90vh;
    overflow-y: auto;
    position: relative;
    animation: modalSlideIn 0.3s ease-out;
}

@keyframes modalSlideIn {
    from {
        opacity: 0;
        transform: translateY(-50px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.modal-header {
    background: linear-gradient(135deg, var(--primary), var(--primary-dark));
    color: white;
    padding: 30px;
    border-radius: 20px 20px 0 0;
    position: sticky;
    top: 0;
    z-index: 10;
}

.modal-header h2 {
    font-size: 1.8rem;
    margin-bottom: 10px;
}

.close-modal {
    position: absolute;
    top: 20px;
    left: 20px;
    background: rgba(255,255,255,0.2);
    border: none;
    color: white;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    cursor: pointer;
    font-size: 1.5rem;
    transition: all 0.3s;
}

.close-modal:hover {
    background: rgba(255,255,255,0.3);
    transform: rotate(90deg);
}

.modal-body {
    padding: 30px;
}

.detail-section {
    margin-bottom: 30px;
}

.detail-section h3 {
    color: var(--primary);
    font-size: 1.3rem;
    margin-bottom: 15px;
    display: flex;
    align-items: center;
    gap: 10px;
    padding-bottom: 10px;
    border-bottom: 2px solid var(--bg);
}

.detail-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 15px;
    margin-top: 15px;
}

.detail-item {
    background: var(--bg);
    padding: 15px;
    border-radius: 12px;
}

.detail-label {
    font-size: 0.85rem;
    color: var(--text-light);
    margin-bottom: 5px;
}

.detail-value {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--text);
}

.recommendation-grid {
    display: grid;
    gap: 15px;
    margin-top: 15px;
}

.recommendation-item {
    background: var(--bg);
    padding: 15px 20px;
    border-radius: 12px;
    border-right: 4px solid var(--primary);
    display: flex;
    align-items: center;
    gap: 12px;
}

.recommendation-item i {
    font-size: 1.3rem;
    color: var(--primary);
}

/* ========== FOOTER ========== */
.footer {
    background: #1e293b;
    color: white;
    padding: 40px 20px 20px;
    margin-top: 80px;
}

.footer-content {
    max-width: 1400px;
    margin: 0 auto;
    text-align: center;
}

.footer-links {
    display: flex;
    justify-content: center;
    gap: 30px;
    margin-bottom: 20px;
    flex-wrap: wrap;
}

.footer-links a {
    color: rgba(255,255,255,0.8);
    text-decoration: none;
    transition: color 0.3s;
}

.footer-links a:hover {
    color: white;
}

.footer-disclaimer {
    color: rgba(255,255,255,0.6);
    font-size: 0.9rem;
    line-height: 1.8;
    max-width: 800px;
    margin: 20px auto;
    padding: 20px;
    background: rgba(255,255,255,0.05);
    border-radius: 12px;
}

.footer-bottom {
    padding-top: 20px;
    border-top: 1px solid rgba(255,255,255,0.1);
    color: rgba(255,255,255,0.5);
    font-size: 0.85rem;
}

/* ========== RESPONSIVE ========== */
@media (max-width: 768px) {
    .header-top {
        flex-direction: column;
        gap: 15px;
    }
    
    .header-actions {
        width: 100%;
        flex-direction: column;
    }
    
    .search-input {
        width: 100%;
    }
    
 .stats-container {
    max-width: 1200px;
    margin: -30px auto 30px; /* Overlap header slightly */
    padding: 0 20px;
}

.stat-card {
    padding: 15px 20px; /* Reduced from 30px */
    border-radius: 12px;
}

.stat-icon {
    width: 40px; /* Reduced from 60px */
    height: 40px;
    font-size: 1.2rem;
    margin-bottom: 10px;
}

.stat-value {
    font-size: 1.5rem; /* Reduced from 2.5rem */
}

.stat-label {
    font-size: 0.8rem;
}
.container {
    max-width: 1200px;
}

.analysis-card {
    padding: 20px; /* Reduced from 30px */
    border-radius: 15px;
    margin-bottom: 15px;
}

.card-header-section {
    margin-bottom: 15px;
    padding-bottom: 15px;
}

.card-location {
    font-size: 1rem;
}

.status-row {
    margin: 15px 0;
    gap: 10px;
}

.status-item {
    padding: 8px 12px;
}

.diagnosis-summary {
    padding: 12px 15px;
    font-size: 0.9rem;
}

.action-btn {
    padding: 8px 16px;
    font-size: 0.85rem;
}
    .status-row {
        grid-template-columns: 1fr;
    }
    
    .card-actions {
        flex-direction: column;
    }
    
    .action-btn {
        width: 100%;
        justify-content: center;
    }
}

/* ========== ANIMATIONS ========== */
@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

.analysis-card {
    animation: fadeIn 0.5s ease-out;
}
</style>
</head>

<body>

<!-- Page Header -->
<header class="page-header">
    <div class="header-content">
        <div class="header-top">
            <a href="/" class="back-link">
                <i class="fas fa-arrow-right"></i>
                العودة للرئيسية
            </a>
            
            <div class="header-actions">
                <div class="search-box">
                    <input type="text" class="search-input" id="searchInput" placeholder="ابحث حسب المدينة، المشغل، أو التاريخ...">
                    <i class="fas fa-search search-icon"></i>
                </div>
                
                <button class="clear-btn" onclick="clearAllHistory()">
                    <i class="fas fa-trash-alt"></i>
                    مسح الكل
                </button>
            </div>
        </div>
        <script>
    // منع الزر الأيمن للفأرة
    document.addEventListener('contextmenu', event => event.preventDefault());

    // منع اختصارات لوحة المفاتيح مثل Ctrl+U (رؤية السورس)
    document.onkeydown = function(e) {
        if (e.ctrlKey && (e.keyCode === 85 || e.keyCode === 83)) {
            return false;
        }
    };
</script>
<div class="header-title">
    <h1> السجل التاريخي للتحليلات</h1>
    <p> راجع وقارن وصدّر تحليلاتك السابقة للشبكة</p>
    
    <div class="footer-disclaimer" style="background: rgba(0,0,0,0.2); margin-top: 20px; max-width: 600px;">
        <strong>⚠️ إخلاء مسؤولية:</strong>
        <p style="font-size: 0.85rem; opacity: 0.9;">
            جميع التحليلات المعروضة هي تقديرات إرشادية تعتمد على البيانات المدخلة وظروف الشبكة اللحظية. 
            ISHARATI PRO ليست مسؤولة عن أي قرارات تتخذها بناءً على هذه التحليلات.
        </p>
    </div>
</div>
    </div>
</header>

<!-- Stats Overview -->
<div class="stats-container">
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-icon primary">
                <i class="fas fa-chart-line"></i>
            </div>
            <div class="stat-value">{{ stats.total }}</div>
            <div class="stat-label">إجمالي التحليلات</div>
        </div>
        
        <div class="stat-card">
            <div class="stat-icon secondary">
                <i class="fas fa-signal"></i>
            </div>
            <div class="stat-value">{{ stats.most_used_operator }}</div>
            <div class="stat-label">المشغل الأكثر استخداماً</div>
        </div>
        
        <div class="stat-card">
            <div class="stat-icon accent">
                <i class="fas fa-exclamation-triangle"></i>
            </div>
            <div class="stat-value">{{ stats.most_frequent_issue }}</div>
            <div class="stat-label">المشكلة الأكثر تكراراً</div>
        </div>
        
        <div class="stat-card">
            <div class="stat-icon info">
                <i class="fas fa-star"></i>
            </div>
            <div class="stat-value">{{ stats.average_score }}/100</div>
            <div class="stat-label">متوسط جودة الشبكة</div>
        </div>
    </div>
</div>

<!-- Main Content -->
<div class="container">
    {% if analytics|length == 0 %}
    <!-- Empty State -->
    <div class="empty-state">
        <div class="empty-illustration">
            📭
        </div>
        <h2>لا توجد تحليلات بعد</h2>
        <p>ابدأ أول تحليل للشبكة لرؤية النتائج هنا</p>
        <a href="/" class="empty-cta">
            <i class="fas fa-play-circle"></i>
            ابدأ التحليل الآن
        </a>
    </div>
    {% else %}
    <!-- Analytics List -->
    <div class="analytics-list" id="analyticsList">
        {% for record in analytics %}
        <div class="analysis-card" data-id="{{ record.id }}">
            <div class="card-header-section">
                <div class="card-info">
                    <span class="card-id">
                        <i class="fas fa-hashtag"></i> {{ record.id }}
                    </span>
                    
                    <div class="card-datetime">
                        <span><i class="fas fa-calendar"></i> {{ record.date }}</span>
                        <span><i class="fas fa-clock"></i> {{ record.time }}</span>
                    </div>
                    
                    <div class="card-location">
                        <i class="fas fa-map-marker-alt"></i>
                        {{ record.city }} - {{ record.wilaya }}
                    </div>
                </div>
                
                <span class="operator-badge operator-{{ record.operator.lower() }}">
                    {{ record.operator }}
                </span>
            </div>
            
            <!-- Status Row -->
            <div class="status-row">
                <div class="status-item">
                    <span class="status-icon">
                        {% if record.network_score >= 75 %}
                            ✅
                        {% elif record.network_score >= 50 %}
                            ⚠️
                        {% else %}
                            ❌
                        {% endif %}
                    </span>
                    <div>
                        <div class="status-label">قوة الإشارة</div>
                        <div class="status-value">
                            {% if record.score_breakdown.coverage >= 75 %}
                                جيدة
                            {% elif record.score_breakdown.coverage >= 50 %}
                                متوسطة
                            {% else %}
                                ضعيفة
                            {% endif %}
                        </div>
                    </div>
                </div>
                
                <div class="status-item">
                    <span class="status-icon">
                        {% if record.speed_data and record.speed_data.download >= 10 %}
                            🚀
                        {% elif record.speed_data and record.speed_data.download >= 5 %}
                            ⚡
                        {% else %}
                            🐌
                        {% endif %}
                    </span>
                    <div>
                        <div class="status-label">السرعة</div>
                        <div class="status-value">
                            {% if record.speed_data %}
                                {% if record.speed_data.download >= 10 %}
                                    سريعة
                                {% elif record.speed_data.download >= 5 %}
                                    جيدة
                                {% else %}
                                    بطيئة
                                {% endif %}
                            {% else %}
                                غير متوفر
                            {% endif %}
                        </div>
                    </div>
                </div>
                
                <div class="status-item">
                    <span class="status-icon">
                        {% if record.speed_data and record.speed_data.ping < 50 %}
                            ✅
                        {% elif record.speed_data and record.speed_data.ping < 100 %}
                            ⚠️
                        {% else %}
                            ❌
                        {% endif %}
                    </span>
                    <div>
                        <div class="status-label">الكمون</div>
                        <div class="status-value">
                            {% if record.speed_data %}
                                {% if record.speed_data.ping < 50 %}
                                    منخفض
                                {% elif record.speed_data.ping < 100 %}
                                    متوسط
                                {% else %}
                                    مرتفع
                                {% endif %}
                            {% else %}
                                غير متوفر
                            {% endif %}
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Diagnosis Summary -->
            <div class="diagnosis-summary">
                <p><strong>💡 التشخيص:</strong> {{ record.short_recommendation }}</p>
            </div>
            
            <!-- Actions -->
            <div class="card-actions">
                <button class="action-btn btn-view" onclick="viewDetails('{{ record.id }}')">
                    <i class="fas fa-eye"></i>
                    عرض التفاصيل
                </button>
                
                <a href="/download_pdf_analytics/{{ record.id }}" class="action-btn btn-pdf">
                    <i class="fas fa-file-pdf"></i>
                    تصدير PDF
                </a>
                
                <button class="action-btn btn-delete" onclick="deleteRecord('{{ record.id }}')">
                    <i class="fas fa-trash"></i>
                    حذف
                </button>
            </div>
        </div>
        {% endfor %}
    </div>
    {% endif %}
</div>

<!-- Details Modal -->
<div class="modal" id="detailsModal">
    <div class="modal-content">
        <div class="modal-header">
            <button class="close-modal" onclick="closeModal()">
                <i class="fas fa-times"></i>
            </button>
            <h2 id="modalTitle">تفاصيل التحليل</h2>
            <p id="modalSubtitle"></p>
        </div>
        
        <div class="modal-body" id="modalBody">
            <!-- Content will be injected here -->
        </div>
    </div>
</div>

<!-- Footer -->
<footer class="footer">
    <div class="footer-content">
        <div class="footer-links">
            <a href="/">الرئيسية</a>
            <a href="/guide">دليل الاستخدام</a>
            <a href="/knowledge">المعرفة التقنية</a>
            <a href="/speed-test">اختبار السرعة</a>
            <a href="#">تواصل معنا</a>
        </div>
        

        
        <div class="footer-bottom">
            <p>&copy; 2026 ISHARATI PRO v1.0 - Advanced Network Diagnostic Platform</p>
            <p>جميع الحقوق محفوظة</p>
        </div>
    </div>
</footer>

<script>
// Store analytics data for access
const analyticsData = {{ analytics_json|safe }};

// Search functionality
// Updated Search Functionality
document.getElementById('searchInput').addEventListener('input', function(e) {
    const searchTerm = e.target.value.toLowerCase().trim();
    const cards = document.querySelectorAll('.analysis-card');
    
    cards.forEach(card => {
        // Targets the location text and the operator badge text
        const locationText = card.querySelector('.card-location').textContent.toLowerCase();
        const operatorText = card.querySelector('.operator-badge').textContent.toLowerCase();
        const cardId = card.querySelector('.card-id').textContent.toLowerCase();

        if (locationText.includes(searchTerm) || 
            operatorText.includes(searchTerm) || 
            cardId.includes(searchTerm)) {
            card.style.display = 'block';
            card.style.animation = 'fadeIn 0.3s ease-out';
        } else {
            card.style.display = 'none';
        }
    });
});
// Add this inside your input listener
const visibleCards = document.querySelectorAll('.analysis-card[style="display: block;"]');
const listContainer = document.getElementById('analyticsList');

if (searchTerm !== "" && visibleCards.length === 0) {
    // You can trigger a "No results" alert or div here
    console.log("No matching analyses found.");
}
// View details
function viewDetails(recordId) {
    const record = analyticsData.find(r => r.id === recordId);
    if (!record) return;
    
    const modal = document.getElementById('detailsModal');
    const modalBody = document.getElementById('modalBody');
    const modalTitle = document.getElementById('modalTitle');
    const modalSubtitle = document.getElementById('modalSubtitle');
    
    modalTitle.textContent = `تحليل رقم ${record.id}`;
    modalSubtitle.textContent = `${record.city}, ${record.wilaya} - ${record.date} ${record.time}`;
    
    let speedSection = '';
    if (record.speed_data) {
        speedSection = `
            <div class="detail-section">
                <h3><i class="fas fa-tachometer-alt"></i> نتائج اختبار السرعة</h3>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-label">التحميل</div>
                        <div class="detail-value">${record.speed_data.download} Mbps</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">الرفع</div>
                        <div class="detail-value">${record.speed_data.upload} Mbps</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Ping</div>
                        <div class="detail-value">${record.speed_data.ping} ms</div>
                    </div>
                </div>
            </div>
        `;
    }
    
    let recommendationsHtml = '';
    if (record.recommendations) {
        const allRecs = [
            ...record.recommendations.physical,
            ...record.recommendations.network,
            ...record.recommendations.usage
        ];
        
        if (allRecs.length > 0) {
            recommendationsHtml = `
                <div class="detail-section">
                    <h3><i class="fas fa-lightbulb"></i> التوصيات</h3>
                    <div class="recommendation-grid">
                        ${allRecs.map(rec => `
                            <div class="recommendation-item">
                                <i class="fas fa-check-circle"></i>
                                <span>${rec}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }
    }
    
    modalBody.innerHTML = `
        <div class="detail-section">
            <h3><i class="fas fa-map-marker-alt"></i> الموقع والبيئة</h3>
            <div class="detail-grid">
                <div class="detail-item">
                    <div class="detail-label">خط العرض</div>
                    <div class="detail-value">${record.lat}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">خط الطول</div>
                    <div class="detail-value">${record.lon}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">المكان</div>
                    <div class="detail-value">${record.place}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">نوع الشبكة</div>
                    <div class="detail-value">${record.network_type}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">المشغل</div>
                    <div class="detail-value">${record.operator}</div>
                </div>
            </div>
        </div>
        
        <div class="detail-section">
            <h3><i class="fas fa-signal"></i> مؤشرات الإشارة</h3>
            <div class="detail-grid">
                <div class="detail-item">
                    <div class="detail-label">RSRP (قوة الإشارة)</div>
                    <div class="detail-value">${record.rsrp} dBm</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">SINR (جودة الإشارة)</div>
                    <div class="detail-value">${record.sinr} dB</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">التقييم الإجمالي</div>
                    <div class="detail-value">${record.network_score}/100 ${record.score_breakdown.stars}</div>
                </div>
            </div>
        </div>
        
        ${speedSection}
        
        <div class="detail-section">
            <h3><i class="fas fa-stethoscope"></i> التشخيص الكامل</h3>
            <div class="diagnosis-summary">
                <p>${record.short_recommendation}</p>
            </div>
        </div>
        
        ${recommendationsHtml}
    `;
    
    modal.classList.add('active');
}

function closeModal() {
    document.getElementById('detailsModal').classList.remove('active');
}

// Close modal on background click
document.getElementById('detailsModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeModal();
    }
});

// Delete record
function deleteRecord(recordId) {
    if (!confirm('هل أنت متأكد من حذف هذا التحليل؟ لا يمكن التراجع عن هذا الإجراء.')) {
        return;
    }
    
    fetch(`/api/delete_analytics/${recordId}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const card = document.querySelector(`[data-id="${recordId}"]`);
            card.style.animation = 'fadeOut 0.3s ease-out';
            setTimeout(() => {
                card.remove();
                
                // Check if list is empty
                if (document.querySelectorAll('.analysis-card').length === 0) {
                    location.reload();
                }
            }, 300);
        } else {
            alert('حدث خطأ أثناء الحذف');
        }
    })
    .catch(error => {
        alert('فشل الاتصال بالخادم');
    });
}

// Clear all history
function clearAllHistory() {
    if (!confirm('هل أنت متأكد من حذف جميع التحليلات؟ لا يمكن التراجع عن هذا الإجراء.')) {
        return;
    }
    
    fetch('/api/clear_all_analytics', {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            location.reload();
        } else {
            alert('حدث خطأ أثناء الحذف');
        }
    })
    .catch(error => {
        alert('فشل الاتصال بالخادم');
    });
}

// Add fadeOut animation
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeOut {
        from { opacity: 1; transform: scale(1); }
        to { opacity: 0; transform: scale(0.95); }
    }
`;
document.head.appendChild(style);
</script>

</body>
</html>
"""

SPEED_TEST_PAGE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/png" href="{{ url_for('static', filename='logo2.png') }}">
    <title>اختبار سرعة الإنترنت - ISHARATI PRO</title>
    
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&family=IBM+Plex+Sans+Arabic:wght@400;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    
    <style>
:root {
    --primary: #0052FF;
    --primary-dark: #0052FF;
    --secondary: #0052FF;
    --accent: #0052FF;
    --bg: #FFFFFF;
    --card-bg: #1a1d23;
    --text: white;
    --border: #e2e8f0;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body { 
    font-family: 'IBM Plex Sans Arabic', sans-serif; 
    background: var(--bg); 
    color: var(--text);
    line-height: 1.5;
    font-size: 0.95rem; /* Reduced base font size */
}
    .header {
        background: linear-gradient(135deg, var(--primary), var(--primary-dark));
        color: white;
        padding: 60px 20px;
        text-align: center;
        border-bottom-left-radius: 40px;
        border-bottom-right-radius: 40px;
        box-shadow: 0 10px 20px rgba(0,0,0,0.1);
    }

.header-content {
    max-width: 1400px;
    margin: 0 auto;
    padding: 15px 20px;
    display: flex;
    /* This ensures they follow the Right-to-Left flow */
    flex-direction: row; 
    justify-content: space-between;
    align-items: center;
    gap: 30px;
}
.logo {
    display: flex;
    align-items: center;
    gap: 12px;
    color: var(--primary);
    font-weight: 900;
    font-size: 1.4rem;
    text-decoration: none;
}

.logo-icon-box {
    background: var(--primary);
    color: white;
    width: 40px;
    height: 40px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
}
.logo-section {
    display: flex;
    align-items: center;
    gap: 12px;
    text-decoration: none;
    /* Ensures the icon stays to the right of the text within the logo group */
    flex-direction: row; 
}
.logo-text p {
    font-size: 0.75rem;
    color: var(--text-light);
}
/* Search Bar */
.search-container {
    flex: 1;
    max-width: 600px;
}

.search-wrapper {
    position: relative;
    display: flex;
    align-items: center;
}

.search-input {
    width: 100%;
    /* Add padding to the left so text doesn't go under the button */
    padding: 12px 20px 12px 50px; 
    border: 1px solid var(--border);
    border-radius: 50px;
}
.search-input:focus {
    outline: none;
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(0, 82, 255, 0.1);
}

.search-btn {
    position: absolute;
    left: 5px; 
    background: var(--primary);
    color: white;
    border: none;
    padding: 8px 20px;
    border-radius: 50px;
    cursor: pointer;
}

    .back-btn {
        display: inline-flex; align-items: center; gap: 8px;
        color: white; text-decoration: none; font-weight: bold;
        margin-bottom: 25px; background: rgba(255,255,255,0.15);
        padding: 10px 20px; border-radius: 50px; transition: 0.3s;
        backdrop-filter: blur(5px);
    }
    .back-btn:hover { background: white; color: var(--primary); transform: translateX(-5px); }
.search-btn:hover { background: var(--primary-dark); }

.search-results {
    position: absolute;
    top: 110%;
    right: 0;
    left: 0;
    background: white;
    border-radius: 15px;
    box-shadow: var(--shadow-lg);
    max-height: 400px;
    overflow-y: auto;
    display: none;
    z-index: 100;
}

.search-results.active { display: block; }

.search-result-item {
    padding: 15px 20px;
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    transition: background 0.2s;
}

.search-result-item:hover { background: var(--bg); }
.search-result-item:last-child { border-bottom: none; }

.cta-btn {
    background: var(--primary);
    color: white;
    padding: 10px 25px;
    border-radius: 50px;
    text-decoration: none;
    font-weight: 700;
    transition: all 0.3s;
    border: none;
    cursor: pointer;
}

.cta-btn:hover {
    background: var(--primary-dark);
    transform: translateY(-2px);
    box-shadow: var(--shadow);
}

.mobile-menu-btn {
    display: none;
    background: transparent;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    color: var(--text);
}

.guide-btn {
    background: var(--primary);
    color: white;
    padding: 10px 25px;
    border-radius: 50px;
    text-decoration: none;
    font-weight: bold;
    font-size: 0.9rem;
}.search-icon {
    position: absolute;
    right: 15px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--primary);
}.search-container {
    flex: 1;
    max-width: 500px;
    margin: 0 30px;
    position: relative;
}

.search-input {
    width: 100%;
    padding: 10px 45px 10px 20px;
    border: 1px solid var(--border);
    border-radius: 50px;
    font-family: inherit;
    background: #fdfdfd;
}


/* Hover Animation for inactive links */
.nav-links a:hover {
    background-color: #f0f7ff;
    color: #007bff;
    transform: translateY(-3px); /* Lifts the button up */
}

/* The Blue "Active" Button (The one in the picture) */
.nav-links a.active {
    background-color: #007bff;
    color: white;
    /* This creates the glow/shadow effect seen in picture 2 */
    box-shadow: 0 8px 15px rgba(0, 123, 255, 0.25);
    transform: translateY(-2px);
}

/* Active Button pulse/click effect */
.nav-links a.active:active {
    transform: translateY(0);
    box-shadow: 0 4px 6px rgba(0, 123, 255, 0.2);
}
.container {
    flex: 1;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 40px 20px;

}

.speed-card {
    background: var(--card-bg);
    padding: 40px;
    border-radius: 25px;
    text-align: center;
    width: 100%;
    max-width: 500px;
    border: 1px solid var(--border);
    box-shadow: 0 10px 40px rgba(0,0,0,0.3);
}

.speed-card h1 {
    color: var(--primary);
    margin-bottom: 30px;
    font-size: 2rem;
}

.speed-display {
    margin: 40px 0;
}

.speed-value {
    font-size: 5rem;
    font-weight: bold;
    color: #00ffcc;
    margin: 20px 0;
}

.speed-label {
    font-size: 1.2rem;
    color: #888;
}

.secondary-stats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin: 30px 0;
}

.stat-box {
    background: #000;
    padding: 20px;
    border-radius: 15px;
}

.stat-value {
    font-size: 2rem;
    color: #00ffcc;
    font-weight: bold;
}

.stat-label {
    color: #888;
    font-size: 0.9rem;
    margin-top: 5px;
}

.test-btn {
    background: #00ffcc;
    border: none;
    padding: 18px 40px;
    border-radius: 50px;
    font-weight: bold;
    font-size: 1.1rem;
    cursor: pointer;
    width: 100%;
    transition: all 0.3s;
    color: #000;
}

.test-btn:hover {
    background: #00d4aa;
    transform: translateY(-2px);
}

.test-btn:disabled {
    background: #444;
    color: #888;
    cursor: wait;
}

.error-log {
    color: #ff5555;
    font-size: 0.9rem;
    margin-top: 20px;
    background: #000;
    padding: 15px;
    border-radius: 10px;
    display: none;
}

.loading-spinner {
    display: inline-block;
    width: 30px;
    height: 30px;
    border: 4px solid rgba(255,255,255,0.3);
    border-radius: 50%;
    border-top-color: #00ffcc;
    animation: spin 1s ease-in-out infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

.info-section {
    margin-top: 30px;
    padding-top: 30px;
    border-top: 1px solid var(--border);
}

.info-section h3 {
    color: var(--primary);
    margin-bottom: 15px;
}

.info-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 15px;
    margin-top: 20px;
}

.info-box {
    background: #000;
    padding: 15px;
    border-radius: 10px;
    text-align: right;
}

.info-box h4 {
    color: #00ffcc;
    font-size: 0.9rem;
    margin-bottom: 5px;
}

.info-box p {
    color: #FFFFFF;
    font-size: 0.85rem;
}

@media (max-width: 768px) {
    .speed-value {
        font-size: 3.5rem;
    }
    
    .secondary-stats {
        grid-template-columns: 1fr;
    }
}
</style>
</head>
<body>



<div class="header">
    <div style="max-width: 1100px; margin: 0 auto; text-align: right;">
        <a href="/" class="back-btn"><i class="fas fa-arrow-right"></i> العودة للرئيسية</a>
    </div>
    <h1>فحص نبض الشبكة</h1>
    <p>حلل سرعة إنترنتك وتعلّم كيف تزيد من استقرارها</p>
</div>



<div class="container">
    <div class="speed-card">
        <h1><i class="fas fa-tachmoeter-alt"></i> اختبار سرعة الإنترنت</h1>
        
        <div class="speed-display">
            <div class="speed-label">سرعة التحميل</div>
            <div class="speed-value" id="downloadSpeed">0.0</div>
            <div class="speed-label">Mbps</div>
        </div>
        
        <div class="secondary-stats">
            <div class="stat-box">
                <div class="stat-value" id="uploadSpeed">-</div>
                <div class="stat-label">الرفع (Mbps)</div>
            </div>
            <div class="stat-box">
                <div class="stat-value" id="pingSpeed">-</div>
                <div class="stat-label">Ping (ms)</div>
            </div>
        </div>
        
        <button class="test-btn" id="testBtn" onclick="startTest()">
            <i class="fas fa-play"></i> ابدأ الاختبار
        </button>
        
        <div class="error-log" id="errorLog"></div>
        
        <div class="info-section">
            <h3><i class="fas fa-info-circle"></i> معلومات مفيدة</h3>
            <div class="info-grid">
                <div class="info-box">
                    <h4>سرعة ممتازة</h4>
                    <p>> 20 Mbps</p>
                </div>
                <div class="info-box">
                    <h4>سرعة جيدة</h4>
                    <p>5-20 Mbps</p>
                </div>
                <div class="info-box">
                    <h4>سرعة محدودة</h4>
                    <p>1-5 Mbps</p>
                </div>
                <div class="info-box">
                    <h4>سرعة بطيئة</h4>
                    <p>< 1 Mbps</p>
                </div>
            </div>
        </div>
    </div>
</div>
<script>
    // منع الزر الأيمن للفأرة
    document.addEventListener('contextmenu', event => event.preventDefault());

    // منع اختصارات لوحة المفاتيح مثل Ctrl+U (رؤية السورس)
    document.onkeydown = function(e) {
        if (e.ctrlKey && (e.keyCode === 85 || e.keyCode === 83)) {
            return false;
        }
    };
</script>
<script>async function startTest() {
    const btn = document.getElementById('testBtn');
    const downloadEl = document.getElementById('downloadSpeed');
    
    btn.disabled = true;
    btn.innerHTML = 'جاري القياس الحقيقي...';

    const startTime = performance.now();
    
    try {
        // Fetch the 5MB dummy file from your own API
        const response = await fetch('/api/download-test', { cache: "no-store" });
        const reader = response.body.getReader();
        let receivedLength = 0;

        while(true) {
            const {done, value} = await reader.read();
            if (done) break;
            receivedLength += value.length;
        }

        const endTime = performance.now();
        const durationInSeconds = (endTime - startTime) / 1000;
        const bitsLoaded = receivedLength * 8;
        const speedMbps = ((bitsLoaded / durationInSeconds) / 1000000).toFixed(2);

        downloadEl.textContent = speedMbps;
        document.getElementById('uploadSpeed').textContent = "---";
        document.getElementById('pingSpeed').textContent = Math.round(durationInSeconds * 10) + " ms";

    } catch (error) {
        document.getElementById('errorLog').textContent = 'فشل الاختبار: قيود الخادم';
        document.getElementById('errorLog').style.display = 'block';
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'إعادة الاختبار';
    }
}
</script>

</body>
</html>
"""
GUIDE_PAGE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/png" href="{{ url_for('static', filename='logo2.png') }}">
    <title>دليل الاستخدام الشامل - ISHARATI PRO</title>
    
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&family=IBM+Plex+Sans+Arabic:wght@400;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    
 <style>
        :root {
            --primary: #0052FF;
            --primary-dark: #003db3;
            --primary-light: #3B82F6;
            --secondary: #10b981;
            --accent: #f59e0b;
            --danger: #ef4444;
            --bg: #f8fafc;
            --text: #1e293b;
            --text-light: #64748b;
            --border: #e2e8f0;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.8;
        }

        /* Header Styles */
.guide-header {
    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
    color: white;
    /* Change the bottom padding from 80px to 120px or more */
    padding: 40px 20px 120px; 
    text-align: center;
    border-bottom-left-radius: 40px;
    border-bottom-right-radius: 40px;
    box-shadow: 0 10px 20px rgba(0,0,0,0.1);
}

        .back-btn-wrapper {
            max-width: 1200px;
            margin: 0 auto;
            text-align: right;
            padding-bottom: 20px;
        }

        .back-btn-modern {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            color: white;
            text-decoration: none;
            font-weight: 700;
            background: rgba(255, 255, 255, 0.15);
            padding: 10px 22px;
            border-radius: 50px;
            backdrop-filter: blur(8px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            transition: all 0.3s ease;
        }

        .back-btn-modern:hover {
            background: white;
            color: var(--primary);
            transform: translateX(5px);
        }

/* ========== HEADER ========== */
.guide-header {
    background: linear-gradient(135deg, var(--primary) 0%, #003db3 100%);
    color: white;
    padding: 40px 20px;
    text-align: center;
    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
}

/* البحث عن العنوان الرئيسي */
.guide-header h1 {
    font-size: 1.8rem; /* قمنا بتصغيره من 2.5rem */
    font-weight: 800;
    margin-bottom: 10px;
}

/* البحث عن النص الفرعي */
.guide-header p {
    font-size: 1rem; /* قمنا بتصغيره من 1.2rem */
    opacity: 0.9;
    max-width: 600px;
    margin: 0 auto;
}
.guide-header {
    padding: 30px 20px 60px; /* تقليل التباعد العلوي والسفلي */
    /* باقي الخصائص كما هي */
}
.header-actions {
    margin-top: 30px;
    display: flex;
    justify-content: center;
    gap: 15px;
    flex-wrap: wrap;
}

.header-btn {
    background: rgba(255,255,255,0.2);
    backdrop-filter: blur(10px);
    color: white;
    padding: 12px 30px;
    border-radius: 50px;
    text-decoration: none;
    font-weight: 700;
    transition: all 0.3s;
    border: 2px solid rgba(255,255,255,0.3);
}

.header-btn:hover {
    background: white;
    color: var(--primary);
    transform: translateY(-2px);
}

.header-btn.primary {
    background: white;
    color: var(--primary);
}

/* ========== TABLE OF CONTENTS ========== */
.toc-container {
    max-width: 1200px;
    /* The first value is the top margin. 
       Currently -50px (pulls it up). 
       Change it to -20px or 0px to create more space from the text above. */
    margin: -20px auto 40px; 
    padding: 0 20px;
    position: relative;
    z-index: 10;
}

.toc-card {
    background: white;
    border-radius: 20px;
    padding: 30px;
    box-shadow: 0 10px 40px rgba(0,0,0,0.1);
    border: 1px solid var(--border);
}

.toc-title {
    font-size: 1.5rem;
    font-weight: 800;
    color: var(--primary);
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 10px;
}

.toc-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 15px;
}

.toc-item {
    padding: 15px;
    background: var(--bg);
    border-radius: 12px;
    text-decoration: none;
    color: var(--text);
    font-weight: 600;
    transition: all 0.3s;
    display: flex;
    align-items: center;
    gap: 12px;
    border: 2px solid transparent;
}

.toc-item:hover {
    background: var(--primary);
    color: white;
    transform: translateX(-5px);
    border-color: var(--primary);
}

.toc-icon {
    width: 40px;
    height: 40px;
    background: linear-gradient(135deg, var(--primary), var(--primary-light));
    color: white;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.2rem;
    flex-shrink: 0;
}

/* ========== MAIN CONTENT ========== */
.container, .toc-container {
    max-width: 1000px; /* هذا الحجم مثالي لموازنة العناصر كما في صورتك */
    margin-left: auto;
    margin-right: auto;
}

.section {
    background: white;
    padding: 40px;
    border-radius: 25px;
    margin-bottom: 30px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    border-right: 6px solid var(--primary);
    scroll-margin-top: 100px;
}

.section-header {
    display: flex;
    align-items: center;
    gap: 15px;
    margin-bottom: 30px;
    padding-bottom: 20px;
    border-bottom: 3px solid var(--bg);
}

.section-icon {
    width: 60px;
    height: 60px;
    background: linear-gradient(135deg, var(--primary), var(--primary-light));
    color: white;
    border-radius: 15px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.8rem;
    flex-shrink: 0;
}

.section-title {
    font-size: 2rem;
    font-weight: 900;
    color: var(--text);
}

.section-subtitle {
    color: var(--text-light);
    font-size: 0.95rem;
    margin-top: 5px;
}

/* ========== CONTENT BLOCKS ========== */
.content-block {
    margin-bottom: 25px;
}

.block-title {
    font-size: 1.3rem;
    font-weight: 700;
    color: var(--primary);
    margin-bottom: 15px;
    display: flex;
    align-items: center;
    gap: 10px;
}

.method-card {
    background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
    padding: 25px;
    border-radius: 15px;
    margin-bottom: 20px;
    border-right: 4px solid var(--secondary);
}

.method-card h4 {
    color: var(--secondary);
    font-size: 1.2rem;
    margin-bottom: 15px;
    display: flex;
    align-items: center;
    gap: 10px;
}

.method-card ul, .content-block ul {
    padding-right: 20px;
    margin: 15px 0;
}

.method-card li, .content-block li {
    margin: 10px 0;
    line-height: 1.8;
}

/* ========== INFO BOXES ========== */
.info-box {
    background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
    padding: 20px 25px;
    border-radius: 15px;
    border-right: 5px solid var(--accent);
    margin: 25px 0;
    display: flex;
    gap: 15px;
}

.info-box-icon {
    font-size: 1.5rem;
    color: var(--accent);
    flex-shrink: 0;
}

.warning-box {
    background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
    border-right-color: var(--danger);
}

.warning-box .info-box-icon {
    color: var(--danger);
}

.success-box {
    background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
    border-right-color: var(--secondary);
}

.success-box .info-box-icon {
    color: var(--secondary);
}

/* ========== TABLE ========== */
.data-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    margin: 25px 0;
    overflow: hidden;
    border-radius: 15px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.05);
}

.data-table thead {
    background: linear-gradient(135deg, var(--primary), var(--primary-light));
    color: white;
}

.data-table th {
    padding: 18px;
    text-align: right;
    font-weight: 700;
    font-size: 1.05rem;
}

.data-table td {
    padding: 18px;
    border-bottom: 1px solid var(--border);
    background: white;
}

.data-table tr:hover td {
    background: var(--bg);
}

.data-table tr:last-child td {
    border-bottom: none;
}

/* ========== BADGES & HIGHLIGHTS ========== */
.badge {
    display: inline-block;
    background: linear-gradient(135deg, #dbeafe, #bfdbfe);
    color: var(--primary);
    padding: 5px 15px;
    border-radius: 20px;
    font-weight: 700;
    font-size: 0.9rem;
    margin: 0 5px;
}

.highlight {
    background: linear-gradient(135deg, #fef3c7, #fde68a);
    padding: 2px 8px;
    border-radius: 5px;
    font-weight: 600;
}

.check-mark {
    color: var(--secondary);
    font-weight: 700;
    font-size: 1.1rem;
}

.x-mark {
    color: var(--danger);
    font-weight: 700;
    font-size: 1.1rem;
}

/* ========== VISUAL GUIDE ========== */
.visual-steps {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 25px;
    margin: 30px 0;
}

.step-card {
    background: white;
    border: 2px solid var(--border);
    border-radius: 15px;
    padding: 25px;
    text-align: center;
    transition: all 0.3s;
}

.step-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 10px 30px rgba(0,0,0,0.1);
    border-color: var(--primary);
}

.step-number {
    width: 50px;
    height: 50px;
    background: linear-gradient(135deg, var(--primary), var(--primary-light));
    color: white;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    font-weight: 900;
    margin: 0 auto 15px;
}

.step-card h4 {
    font-size: 1.2rem;
    margin-bottom: 10px;
    color: var(--text);
}

/* ========== SIGNAL QUALITY METER ========== */
.signal-meter {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    margin: 30px 0;
}

.meter-card {
    background: white;
    border: 2px solid var(--border);
    border-radius: 15px;
    padding: 20px;
    text-align: center;
}

.meter-icon {
    font-size: 2.5rem;
    margin-bottom: 10px;
}

.meter-label {
    font-weight: 700;
    font-size: 1.1rem;
    margin-bottom: 10px;
    color: var(--text);
}

.meter-value {
    font-size: 0.95rem;
    color: var(--text-light);
}

.meter-excellent { border-color: var(--secondary); }
.meter-excellent .meter-icon { color: var(--secondary); }

.meter-good { border-color: var(--accent); }
.meter-good .meter-icon { color: var(--accent); }

.meter-poor { border-color: var(--danger); }
.meter-poor .meter-icon { color: var(--danger); }

/* ========== CTA SECTION ========== */
.cta-section {
    background: linear-gradient(135deg, var(--primary) 0%, #003db3 100%);
    color: white;
    padding: 60px 40px;
    border-radius: 25px;
    text-align: center;
    margin: 40px 0;
}

.cta-section h2 {
    font-size: 2rem;
    margin-bottom: 15px;
}

.cta-section p {
    font-size: 1.1rem;
    opacity: 0.95;
    margin-bottom: 30px;
}

.cta-btn {
    background: white;
    color: var(--primary);
    padding: 15px 40px;
    border-radius: 50px;
    text-decoration: none;
    font-weight: 700;
    font-size: 1.1rem;
    display: inline-block;
    transition: all 0.3s;
}

.cta-btn:hover {
    transform: scale(1.05);
    box-shadow: 0 10px 30px rgba(255,255,255,0.3);
}

        .cta-btn:hover { transform: scale(1.05); }

@media (max-width: 768px) {
    .toc-grid {
        grid-template-columns: repeat(2, 1fr); /* عمودين فقط للموبايل لمنع التداخل */
    }
    .guide-header h1 {
        font-size: 1.5rem;
    }
}
    </style>
</head>
<body>
<script>
    // منع الزر الأيمن للفأرة
    document.addEventListener('contextmenu', event => event.preventDefault());

    // منع اختصارات لوحة المفاتيح مثل Ctrl+U (رؤية السورس)
    document.onkeydown = function(e) {
        if (e.ctrlKey && (e.keyCode === 85 || e.keyCode === 83)) {
            return false;
        }
    };
</script>
<header class="guide-header">
    <div class="back-btn-wrapper">
        <a href="/" class="back-btn-modern"><i class="fas fa-arrow-right"></i> العودة للرئيسية</a>
    </div>
    <h1> دليل استخدام ISHARATI PRO</h1>
    <p>نظامك الذكي لتحليل وتصحيح أداء شبكات الاتصال</p>
</header>
<!-- Table of Contents -->
<div class="toc-container">
    <div class="toc-card">
        <h2 class="toc-title">
            <i class="fas fa-list"></i>
            محتويات الدليل
        </h2>
        <div class="toc-grid">
            <a href="#network-types" class="toc-item">
                <div class="toc-icon"><i class="fas fa-network-wired"></i></div>
                <span>أنواع الشبكات</span>
            </a>
            <a href="#signal-reading" class="toc-item">
                <div class="toc-icon"><i class="fas fa-chart-line"></i></div>
                <span>قراءة الإشارة</span>
            </a>
            <a href="#speed-test" class="toc-item">
    <div class="toc-icon"><i class="fas fa-gauge-high"></i></div>
    <span>اختبار السرعة</span>
</a>
            <a href="#data-entry" class="toc-item">
                <div class="toc-icon"><i class="fas fa-keyboard"></i></div>
                <span>إدخال البيانات</span>
            </a>
            <a href="#location" class="toc-item">
                <div class="toc-icon"><i class="fas fa-map-marker-alt"></i></div>
                <span>تحديد الموقع</span>
            </a>
            <a href="#results" class="toc-item">
                <div class="toc-icon"><i class="fas fa-chart-bar"></i></div>
                <span>فهم النتائج</span>
            </a>
            <a href="#troubleshooting" class="toc-item">
                <div class="toc-icon"><i class="fas fa-tools"></i></div>
                <span>حل المشاكل</span>
            </a>
        </div>
    </div>
</div>

<!-- Main Content -->
<div class="container">

    <!-- Section 1: Network Types -->
    <section id="network-types" class="section">
        <div class="section-header">
            <div class="section-icon">
                <i class="fas fa-network-wired"></i>
            </div>
            <div>
                <h2 class="section-title">1. تحديد نوع الشبكة</h2>
                <p class="section-subtitle">الخطوة الأولى: معرفة نوع الاتصال الذي تريد تشخيصه</p>
            </div>
        </div>

        <div class="visual-steps">
            <div class="step-card">
                <div class="step-number">1</div>
                <h4>شبكة الهاتف المحمول</h4>
                <p>3G / 4G / 5G من شريحة SIM</p>
                <div class="badge">NetMonster</div>
            </div>
            <div class="step-card">
                <div class="step-number">2</div>
                <h4>شبكة الواي فاي</h4>
                <p>من الراوتر المنزلي أو العام</p>
                <div class="badge">WiFi Analyzer</div>
            </div>
        </div>

        <div class="content-block">
            <h3 class="block-title">
                <i class="fas fa-mobile-alt"></i>
                لشبكة الهاتف المحمول (Mobile Data)
            </h3>
            <div class="method-card">
                <h4><i class="fas fa-download"></i> التطبيق المطلوب: NetMonster</h4>
                <ul>
                    <li><strong>لماذا NetMonster؟</strong> يعطيك قيم دقيقة عن قوة الإشارة والجودة</li>
                    <li><strong>البيانات المتاحة:</strong> RSRP, SINR, RSRQ, نوع الشبكة، موقع البرج</li>
                    <li><strong>الاستخدام:</strong> مناسب لتشخيص مشاكل 3G, 4G, 5G</li>
                </ul>
            </div>
        </div>

        <div class="content-block">
            <h3 class="block-title">
                <i class="fas fa-wifi"></i>
                لشبكة الواي فاي (WiFi)
            </h3>
            <div class="method-card">
                <h4><i class="fas fa-download"></i> التطبيق المطلوب: WiFi Analyzer</h4>
                <ul>
                    <li><strong>لماذا WiFi Analyzer؟</strong> يحلل جودة اتصال الواي فاي والتداخلات</li>
                    <li><strong>البيانات المتاحة:</strong> قوة الإشارة (dBm)، القنوات المستخدمة، التداخلات</li>
                    <li><strong>الاستخدام:</strong> لتحديد أفضل موقع للراوتر أو حل مشاكل البطء</li>
                </ul>
            </div>
        </div>

        <div class="warning-box info-box">
            <div class="info-box-icon"><i class="fas fa-exclamation-triangle"></i></div>
            <div>
                <strong>تحذير مهم:</strong>
                <p>لا يمكنك استخدام NetMonster لقياس الواي فاي، ولا WiFi Analyzer لقياس شبكة الموبايل. كل تطبيق مخصص لنوع شبكة محدد.</p>
            </div>
        </div>
    </section>

    <!-- Section 2: Signal Reading -->
    <section id="signal-reading" class="section" style="border-right-color: var(--secondary);">
        <div class="section-header">
            <div class="section-icon" style="background: linear-gradient(135deg, var(--secondary), #059669);">
                <i class="fas fa-signal"></i>
            </div>
            <div>
                <h2 class="section-title">2. قراءة معلومات الإشارة</h2>
                <p class="section-subtitle">كيفية الحصول على القيم الدقيقة من التطبيقات</p>
            </div>
        </div>

        <div class="content-block">
            <h3 class="block-title">
                <i class="fas fa-mobile-alt"></i>
                استخدام NetMonster (للشبكة الخلوية)
            </h3>
            
            <div class="visual-steps">
                <div class="step-card">
                    <div class="step-number">1</div>
                    <h4>افتح NetMonster</h4>
                    <p>انقر على أيقونة التطبيق</p>
                </div>
                <div class="step-card">
                    <div class="step-number">2</div>
                    <h4>تبويب Graphs</h4>
                    <p>اذهب إلى قسم الرسوم البيانية</p>
                </div>
                <div class="step-card">
                    <div class="step-number">3</div>
                    <h4>انتظر 20-30 ثانية</h4>
                    <p>دع التطبيق يستقر في مكانك</p>
                </div>
                <div class="step-card">
                    <div class="step-number">4</div>
                    <h4>انسخ القيم</h4>
                    <p>RSRP, SINR, Type, Location</p>
                </div>
            </div>

            <div class="info-box success-box">
                <div class="info-box-icon"><i class="fas fa-lightbulb"></i></div>
                <div>
                    <strong>نصيحة احترافية:</strong>
                    <p>قف ثابتاً لمدة 20-30 ثانية قبل نسخ القيم. الحركة المستمرة تعطي قراءات غير دقيقة.</p>
                </div>
            </div>
        </div>

        <div class="content-block">
            <h3 class="block-title">
                <i class="fas fa-wifi"></i>
                استخدام WiFi Analyzer (للواي فاي)
            </h3>
            
            <ol style="padding-right: 20px; line-height: 2;">
                <li>افتح تطبيق WiFi Analyzer على هاتفك</li>
                <li>اختر شبكتك من قائمة الشبكات المتاحة</li>
                <li>انظر إلى قوة الإشارة (Signal Strength) بوحدة dBm</li>
                <li>راقب مستوى التداخل من الشبكات الأخرى</li>
                <li>انسخ القيم لاستخدامها في التحليل</li>
            </ol>
        </div>
    </section>
<section id="speed-test" class="section" style="border-right-color: #10b981;">
    <div class="section-header">
        <div class="section-icon" style="background: linear-gradient(135deg, #10b981, #059669);">
            <i class="fas fa-gauge-high"></i>
        </div>
        <div>
            <h2 class="section-title">3. اختبار سرعة الإنترنت</h2>
            <p class="section-subtitle">قياس أداء التحميل والرفع واستقرار الاتصال</p>
        </div>
    </div>

    <div class="content-block">
        <h3 class="block-title">
            <i class="fas fa-rocket"></i>
            كيفية إجراء اختبار صحيح
        </h3>
        <p>للحصول على نتائج تعكس واقع الشبكة فعلياً، يفضل اتباع الخطوات التالية قبل إدخال البيانات:</p>
        
        <div class="visual-steps">
            <div class="step-card">
                <div class="step-number">1</div>
                <h4>أغلق التحديثات</h4>
                <p>تأكد من عدم وجود تحميلات في الخلفية</p>
            </div>
            <div class="step-card">
                <div class="step-number">2</div>
                <h4>استخدم سيرفر محلي</h4>
                <p>اختر أقرب سيرفر (Ooredoo, Mobilis, Djaweb)</p>
            </div>
            <div class="step-card">
                <div class="step-number">3</div>
                <h4>كرر الاختبار</h4>
                <p>قم بإجراء الفحص مرتين للتأكد من الثبات</p>
            </div>
        </div>
    </div>

    <div class="content-block">
        <h3 class="block-title">
            <i class="fas fa-microchip"></i>
            المصطلحات الأساسية
        </h3>
        <div class="method-card">
            <ul>
                <li><strong>Download (التحميل):</strong> سرعة استقبال البيانات (مشاهدة الفيديو، تصفح).</li>
                <li><strong>Upload (الرفع):</strong> سرعة إرسال البيانات (رفع الصور، مكالمات الفيديو).</li>
                <li><strong>Ping / Latency:</strong> زمن الاستجابة بالملي ثانية. كلما قل، كان أفضل للألعاب والمكالمات.</li>
            </ul>
        </div>
    </div>

    <div class="success-box info-box">
        <div class="info-box-icon"><i class="fas fa-check-double"></i></div>
        <div>
            <strong>رابط الفحص:</strong>
            <p>نوصي باستخدام موقع <a href="https://www.speedtest.net" target="_blank" style="color: var(--primary); font-weight: bold;">Speedtest.net</a> أو تطبيقهم الرسمي للحصول على أدق النتائج في الجزائر.</p>
        </div>
    </div>
</section>
    <!-- Section 3: Data Entry -->
    <section id="data-entry" class="section" style="border-right-color: var(--accent);">
        <div class="section-header">
            <div class="section-icon" style="background: linear-gradient(135deg, var(--accent), #d97706);">
                <i class="fas fa-keyboard"></i>
            </div>
            <div>
                <h2 class="section-title">4. إدخال البيانات في الموقع</h2>
                <p class="section-subtitle">نقل القيم من التطبيق إلى نموذج التحليل</p>
            </div>
        </div>

        <div class="content-block">
            <h3 class="block-title">
                <i class="fas fa-table"></i>
                جدول مطابقة الحقول
            </h3>
            
            <table class="data-table">
                <thead>
                    <tr>
                        <th>الحقل في الموقع</th>
                        <th>من أين تأخذه</th>
                        <th>مثال</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Latitude (خط العرض)</strong></td>
                        <td>NetMonster → MAP أو Google Maps</td>
                        <td><span class="badge">36.75</span></td>
                    </tr>
                    <tr>
                        <td><strong>Longitude (خط الطول)</strong></td>
                        <td>NetMonster → MAP أو Google Maps</td>
                        <td><span class="badge">3.05</span></td>
                    </tr>
                    <tr>
                        <td><strong>RSRP (قوة الإشارة)</strong></td>
                        <td>NetMonster → Graphs → RSRP</td>
                        <td><span class="badge">-85</span></td>
                    </tr>
                    <tr>
                        <td><strong>SINR (جودة الإشارة)</strong></td>
                        <td>NetMonster → Graphs → SINR</td>
                        <td><span class="badge">15</span></td>
                    </tr>
                    <tr>
                        <td><strong>Network Type</strong></td>
                        <td>NetMonster → شاشة رئيسية (LTE/NR)</td>
                        <td><span class="badge">4G</span></td>
                    </tr>
                    <tr>
                        <td><strong>المكان</strong></td>
                        <td>اختيارك (داخل/خارج المبنى)</td>
                        <td><span class="badge">Indoor</span></td>
                    </tr>
                </tbody>
            </table>
        </div>

        <div class="warning-box info-box">
            <div class="info-box-icon"><i class="fas fa-exclamation-circle"></i></div>
            <div>
                <strong>تنبيه حرج:</strong>
                <p>انسخ القيم <span class="highlight">كما هي تماماً</span>، خاصة الإشارة السالبة (-):</p>
                <p style="margin-top: 10px;">
                    <span class="check-mark">✓ صحيح:</span> <span class="badge">-85</span>
                    &nbsp;&nbsp;|&nbsp;&nbsp;
                    <span class="x-mark">✗ خاطئ:</span> <span class="badge">85</span>
                </p>
            </div>
        </div>

        <div class="info-box">
            <div class="info-box-icon"><i class="fas fa-info-circle"></i></div>
            <div>
                <strong>معلومة:</strong>
                <p>قيم RSRP دائماً سالبة. كلما اقتربت من 0، كانت الإشارة أقوى. مثلاً: -70 أفضل من -100.</p>
            </div>
        </div>
    </section>

    <!-- Section 4: Location -->
    <section id="location" class="section" style="border-right-color: #8b5cf6;">
        <div class="section-header">
            <div class="section-icon" style="background: linear-gradient(135deg, #8b5cf6, #6d28d9);">
                <i class="fas fa-map-marker-alt"></i>
            </div>
            <div>
                <h2 class="section-title">5. كيفية الحصول على Latitude و Longitude</h2>
                <p class="section-subtitle">طرق سهلة لمعرفة إحداثياتك بدقة</p>
            </div>
        </div>

        <div class="visual-steps">
            <div class="step-card">
                <div class="step-number"><i class="fas fa-map"></i></div>
                <h4>Google Maps</h4>
                <p>الطريقة الأسهل والأكثر دقة</p>
            </div>
            <div class="step-card">
                <div class="step-number"><i class="fas fa-mobile"></i></div>
                <h4>NetMonster</h4>
                <p>مباشرة من تبويب MAP</p>
            </div>
            <div class="step-card">
                <div class="step-number"><i class="fas fa-compass"></i></div>
                <h4>GPS Status</h4>
                <p>تطبيق متخصص في GPS</p>
            </div>
        </div>

        <div class="content-block">
            <h3 class="block-title">
                <i class="fas fa-map"></i>
                الطريقة الأولى: Google Maps (الأسهل)
            </h3>
            <div class="method-card">
                <ol style="padding-right: 20px; line-height: 2;">
                    <li>افتح تطبيق Google Maps على هاتفك</li>
                    <li>اضغط ضغطة مطولة (Long Press) على موقعك الحالي في الخريطة</li>
                    <li>سيظهر دبوس أحمر مع الإحداثيات في الأسفل</li>
                    <li>انقر على الإحداثيات لنسخها</li>
                    <li>ستظهر بالشكل: <span class="badge">36.7538, 3.0588</span></li>
                    <li>الرقم الأول هو Latitude والثاني Longitude</li>
                </ol>
            </div>
        </div>

        <div class="content-block">
            <h3 class="block-title">
                <i class="fas fa-mobile-alt"></i>
                الطريقة الثانية: NetMonster MAP
            </h3>
            <div class="method-card">
                <ol style="padding-right: 20px; line-height: 2;">
                    <li>افتح تطبيق NetMonster</li>
                    <li>انتقل إلى تبويب <span class="badge">MAP</span></li>
                    <li>ستجد الإحداثيات مكتوبة مباشرة:</li>
                    <ul style="margin-top: 10px;">
                        <li><strong>Lat:</strong> خط العرض</li>
                        <li><strong>Lon:</strong> خط الطول</li>
                    </ul>
                    <li>انسخ القيم مباشرة إلى الموقع</li>
                </ol>
            </div>
        </div>

        <div class="warning-box info-box">
            <div class="info-box-icon"><i class="fas fa-globe"></i></div>
            <div>
                <strong>نطاق إحداثيات الجزائر:</strong>
                <ul style="margin-top: 10px; padding-right: 20px;">
                    <li><strong>Latitude:</strong> من <span class="badge">18</span> إلى <span class="badge">37</span></li>
                    <li><strong>Longitude:</strong> من <span class="badge">-9</span> إلى <span class="badge">12</span></li>
                </ul>
                <p style="margin-top: 10px;">إذا كانت قيمك خارج هذا النطاق، فهناك خطأ في القراءة.</p>
            </div>
        </div>
    </section>

    <!-- Section 5: Understanding Results -->
    <section id="results" class="section" style="border-right-color: var(--secondary);">
        <div class="section-header">
            <div class="section-icon" style="background: linear-gradient(135deg, var(--secondary), #059669);">
                <i class="fas fa-chart-bar"></i>
            </div>
            <div>
                <h2 class="section-title">6. فهم نتائج التحليل</h2>
                <p class="section-subtitle">كيف تقرأ وتفهم التشخيص الذي يقدمه الموقع</p>
            </div>
        </div>

        <div class="content-block">
            <h3 class="block-title">
                <i class="fas fa-signal"></i>
                مؤشر RSRP (قوة الإشارة)
            </h3>
            
            <div class="signal-meter">
                <div class="meter-card meter-excellent">
                    <div class="meter-icon">🟢</div>
                    <div class="meter-label">ممتاز</div>
                    <div class="meter-value">-70 إلى -85 dBm</div>
                </div>
                <div class="meter-card meter-good">
                    <div class="meter-icon">🟡</div>
                    <div class="meter-label">جيد</div>
                    <div class="meter-value">-86 إلى -100 dBm</div>
                </div>
                <div class="meter-card meter-good">
                    <div class="meter-icon">🟠</div>
                    <div class="meter-label">متوسط</div>
                    <div class="meter-value">-101 إلى -110 dBm</div>
                </div>
                <div class="meter-card meter-poor">
                    <div class="meter-icon">🔴</div>
                    <div class="meter-label">ضعيف</div>
                    <div class="meter-value">أقل من -110 dBm</div>
                </div>
            </div>

            <div class="info-box">
                <div class="info-box-icon"><i class="fas fa-info-circle"></i></div>
                <div>
                    <strong>ملاحظة هامة:</strong>
                    <p>RSRP يقيس <span class="highlight">قوة الإشارة</span> من البرج. كلما كانت القيمة أقرب إلى 0 (أي -70 أفضل من -110)، كانت الإشارة أقوى.</p>
                </div>
            </div>
        </div>

        <div class="content-block">
            <h3 class="block-title">
                <i class="fas fa-chart-line"></i>
                مؤشر SINR (جودة الإشارة)
            </h3>
            
            <div class="signal-meter">
                <div class="meter-card meter-excellent">
                    <div class="meter-icon">⭐⭐⭐</div>
                    <div class="meter-label">ممتاز جداً</div>
                    <div class="meter-value">أكثر من 20 dB</div>
                </div>
                <div class="meter-card meter-excellent">
                    <div class="meter-icon">⭐⭐</div>
                    <div class="meter-label">جيد جداً</div>
                    <div class="meter-value">13 - 20 dB</div>
                </div>
                <div class="meter-card meter-good">
                    <div class="meter-icon">⭐</div>
                    <div class="meter-label">مقبول</div>
                    <div class="meter-value">0 - 13 dB</div>
                </div>
                <div class="meter-card meter-poor">
                    <div class="meter-icon">❌</div>
                    <div class="meter-label">سيئ</div>
                    <div class="meter-value">أقل من 0 dB</div>
                </div>
            </div>

            <div class="info-box">
                <div class="info-box-icon"><i class="fas fa-info-circle"></i></div>
                <div>
                    <strong>ما هو SINR؟</strong>
                    <p>SINR يقيس <span class="highlight">نقاء الإشارة</span> (Signal to Interference + Noise Ratio). كلما كان أعلى، كانت جودة الاتصال أفضل وأسرع.</p>
                </div>
            </div>
        </div>

        <div class="content-block">
            <h3 class="block-title">
                <i class="fas fa-lightbulb"></i>
                أمثلة على حالات شائعة
            </h3>
            
            <div class="method-card" style="border-right-color: var(--secondary);">
                <h4><i class="fas fa-check-circle" style="color: var(--secondary);"></i> الحالة 1: إشارة ممتازة وسريعة</h4>
                <p><strong>RSRP:</strong> -75 dBm | <strong>SINR:</strong> 22 dB</p>
                <p><strong>التفسير:</strong> أنت قريب من البرج والإشارة نقية. السرعة ممتازة. استمتع! 🎉</p>
            </div>

            <div class="method-card" style="border-right-color: var(--accent);">
                <h4><i class="fas fa-exclamation-triangle" style="color: var(--accent);"></i> الحالة 2: إشارة قوية لكن بطيئة</h4>
                <p><strong>RSRP:</strong> -80 dBm | <strong>SINR:</strong> 3 dB</p>
                <p><strong>التفسير:</strong> الإشارة قوية، لكن هناك تداخل أو ازدحام. جرّب تغيير موقعك أو الوقت.</p>
            </div>

            <div class="method-card" style="border-right-color: var(--danger);">
                <h4><i class="fas fa-times-circle" style="color: var(--danger);"></i> الحالة 3: إشارة ضعيفة</h4>
                <p><strong>RSRP:</strong> -115 dBm | <strong>SINR:</strong> -2 dB</p>
                <p><strong>التفسير:</strong> أنت بعيد عن البرج أو في منطقة تغطية ضعيفة. الحل: مقوي إشارة أو واي فاي.</p>
            </div>
        </div>
    </section>

    <!-- Section 6: Troubleshooting -->
    <section id="troubleshooting" class="section" style="border-right-color: var(--danger);">
        <div class="section-header">
            <div class="section-icon" style="background: linear-gradient(135deg, var(--danger), #dc2626);">
                <i class="fas fa-tools"></i>
            </div>
            <div>
                <h2 class="section-title">7. حل المشاكل الشائعة</h2>
                <p class="section-subtitle">أسئلة متكررة ونصائح عملية</p>
            </div>
        </div>

        <div class="content-block">
            <h3 class="block-title">
                <i class="fas fa-question-circle"></i>
                المشاكل الشائعة وحلولها
            </h3>
            
            <div class="method-card">
                <h4><i class="fas fa-wifi"></i> المشكلة: النت بطيء رغم إشارة قوية</h4>
                <p><strong>السبب المحتمل:</strong> SINR منخفض (ازدحام أو تداخل)</p>
                <p><strong>الحل:</strong></p>
                <ul>
                    <li>جرّب في وقت مختلف (تجنب أوقات الذروة 6م - 11م)</li>
                    <li>غيّر موقعك داخل الغرفة</li>
                    <li>أعد تشغيل الهاتف</li>
                    <li>جرّب وضع الطيران لمدة 10 ثواني ثم أعد التشغيل</li>
                </ul>
            </div>

            <div class="method-card">
                <h4><i class="fas fa-signal"></i> المشكلة: الإشارة ضعيفة داخل المنزل فقط</h4>
                <p><strong>السبب المحتمل:</strong> جدران سميكة أو مواد عازلة</p>
                <p><strong>الحل:</strong></p>
                <ul>
                    <li>اقترب من النافذة</li>
                    <li>استخدم WiFi Calling إن كان متاحاً</li>
                    <li>فكّر في شراء مقوي إشارة (Repeater)</li>
                    <li>استخدم الواي فاي بدلاً من بيانات الموبايل</li>
                </ul>
            </div>

            <div class="method-card">
                <h4><i class="fas fa-map-marker-alt"></i> المشكلة: الإحداثيات خاطئة أو لا تعمل</h4>
                <p><strong>الحل:</strong></p>
                <ul>
                    <li>تأكد من تشغيل GPS في هاتفك</li>
                    <li>اسمح لـ Google Maps بالوصول للموقع</li>
                    <li>انتظر 30 ثانية حتى يستقر GPS</li>
                    <li>تحقق من أن الأرقام في نطاق الجزائر المذكور أعلاه</li>
                </ul>
            </div>
        </div>

        <div class="content-block">
            <h3 class="block-title">
                <i class="fas fa-star"></i>
                نصائح ذهبية لأفضل تشخيص
            </h3>
            
            <div class="visual-steps">
                <div class="step-card">
                    <div class="step-number"><i class="fas fa-clock"></i></div>
                    <h4>التوقيت</h4>
                    <p>قس في أوقات مختلفة لفهم أوقات الذروة</p>
                </div>
                <div class="step-card">
                    <div class="step-number"><i class="fas fa-compass"></i></div>
                    <h4>الاتجاه</h4>
                    <p>جرّب الوقوف في اتجاهات مختلفة</p>
                </div>
                <div class="step-card">
                    <div class="step-number"><i class="fas fa-home"></i></div>
                    <h4>الموقع</h4>
                    <p>قارن بين Indoor و Outdoor</p>
                </div>
                <div class="step-card">
                    <div class="step-number"><i class="fas fa-redo"></i></div>
                    <h4>التكرار</h4>
                    <p>كرر القياس عدة مرات للتأكد</p>
                </div>
            </div>
        </div>
    </section>

    <!-- CTA Section -->
    <div class="cta-section">
        <h2><i class="fas fa-rocket"></i> جاهز لتشخيص شبكتك؟</h2>
        <p>الآن بعد أن فهمت كل شيء، حان وقت التحليل الفعلي!</p>
        <a href="/" class="cta-btn">
            <i class="fas fa-play-circle"></i> ابدأ التحليل الآن
        </a>
    </div>

</div>

<script>
// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});
</script>

</body>
</html>
"""




KNOWLEDGE_PAGE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/png" href="{{ url_for('static', filename='logo2.png') }}">
    <title>المعرفة التقنية - ISHARATI PRO</title>
    
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&family=IBM+Plex+Sans+Arabic:wght@400;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    
    <style>
    :root {
        --primary: #0052FF;
        --primary-dark: #003db3;
        --secondary: #10b981;
        --accent: #f59e0b;
        --bg: #f8fafc;
        --card-bg: white;
        --text: #1e293b;
        --border: #e2e8f0;
    }
    body { 
        font-family: 'IBM Plex Sans Arabic', 'Tajawal', sans-serif; 
        background: var(--bg); 
        color: var(--text);
        margin: 0; padding: 0;
        line-height: 1.8;
    }
    .header {
        background: linear-gradient(135deg, var(--primary), var(--primary-dark));
        color: white;
        padding: 60px 20px;
        text-align: center;
        border-bottom-left-radius: 40px;
        border-bottom-right-radius: 40px;
        box-shadow: 0 10px 20px rgba(0,0,0,0.1);
    }
    .container { max-width: 1100px; margin: -40px auto 60px; padding: 0 20px; }
    
    .card {
        background: var(--card-bg);
        border-radius: 24px;
        padding: 35px;
        margin-bottom: 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        border: 1px solid var(--border);
    }
    .card h2 { 
        color: var(--primary); 
        font-size: 1.6rem;
        margin-top: 0; 
        border-bottom: 2px solid var(--bg);
        padding-bottom: 15px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .step-list { list-style: none; padding: 0; }
    .step-item { 
        display: flex; 
        gap: 15px; 
        margin-bottom: 15px; 
        background: var(--bg);
        padding: 15px;
        border-radius: 12px;
    }
    .step-number {
        background: var(--primary);
        color: white;
        width: 28px; height: 28px;
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        flex-shrink: 0; font-weight: bold;
    }

    .grid-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 15px;
        max-width: 1200px;
        margin: 30px auto;
    }

    .info-box {
        background: var(--card-bg);
        padding: 30px 20px;
        border: 1px solid #eee;
        transition: all 0.3s ease-in-out;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border-radius: 12px;
    }

    .info-box:hover {
        background: var(--primary);
        transform: translateY(-8px);
        border-color: var(--primary);
        box-shadow: 0 12px 20px rgba(0, 168, 255, 0.2);
    }

    .icon-wrapper {
        font-size: 35px;
        color: var(--primary);
        margin-bottom: 15px;
    }

    .info-box h3 {
        margin-bottom: 15px;
        font-size: 1.1rem;
        color: #333;
    }

    .info-box p {
        font-size: 0.9rem;
        line-height: 1.6;
        color: #555;
        margin-bottom: 8px;
    }

    .info-box:hover h3, 
    .info-box:hover p, 
    .info-box:hover .icon-wrapper {
        color: #fff;
    }

    .read-more {
        margin-top: 20px;
        padding: 8px;
        background: #f0f9ff;
        color: var(--primary);
        font-size: 0.8rem;
        font-weight: bold;
        text-transform: uppercase;
    }

    .info-box:hover .read-more {
        background: rgba(255, 255, 255, 0.2);
        color: #fff;
    }
    
    .comparison-table { width: 100%; border-collapse: collapse; margin-top: 20px; border-radius: 15px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }
    .comparison-table th { background: var(--primary); color: white; padding: 15px; }
    .comparison-table td { padding: 15px; border: 1px solid var(--border); text-align: center; background: white; }
    
    .problem-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
    .problem-card { border-right: 4px solid var(--primary); background: #f1f5f9; padding: 20px; border-radius: 12px; }
    .problem-card h4 { margin-top: 0; color: var(--text); display: flex; align-items: center; gap: 8px; }
    
    .tip-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
    .tip-item { background: #fffbeb; border: 1px solid #fef3c7; padding: 15px; border-radius: 12px; font-size: 0.95rem; }

    .app-badge { background: #e0e7ff; color: var(--primary); padding: 5px 12px; border-radius: 20px; font-weight: bold; }
    .summary-box { background: linear-gradient(135deg, #003db3); color: white; padding: 30px; border-radius: 24px; text-align: center; }

    .back-btn {
        display: inline-flex; align-items: center; gap: 8px;
        color: white; text-decoration: none; font-weight: bold;
        margin-bottom: 25px; background: rgba(255,255,255,0.15);
        padding: 10px 20px; border-radius: 50px; transition: 0.3s;
        backdrop-filter: blur(5px);
    }
    .back-btn:hover { background: white; color: var(--primary); transform: translateX(-5px); }
</style>
</head>
<body>

<div class="header">
    <div style="max-width: 1100px; margin: 0 auto; text-align: right;">
        <a href="/" class="back-btn"><i class="fas fa-arrow-right"></i> العودة للرئيسية</a>
    </div>
    <h1> دليل المعرفة التقنية</h1>
    <p>افهم كيف يعمل اتصالك وكيف ترفع كفاءته</p>
</div>

<div class="container">
    
    <div class="card">
        <h2><i class="fas fa-info-circle"></i> 1. مقدمة عن الإنترنت</h2>
        <p><strong>الإنترنت بشكل مبسط:</strong> هو شبكة عالمية تسمح لأجهزة الكمبيوتر والهواتف بالاتصال ببعضها لنقل البيانات، مثل تصفح المواقع، مشاهدة الفيديو، والتواصل.</p>
        
        <p>يصل الإنترنت لجهازك عبر رحلة تقنية معقدة، تبدأ من الألياف البصرية تحت المحيطات وصولاً إلى هاتفك.</p>
        
        <h4 style="margin-bottom: 10px;">🔍 كيف يصل الإنترنت لجهازك؟</h4>
        <div class="step-list">
            <div class="step-item">
                <div class="step-number">1</div>
                <div><strong>المصدر:</strong> يبدأ من الكابلات البحرية العالمية (Undersea Cables).</div>
            </div>
            <div class="step-item">
                <div class="step-number">2</div>
                <div><strong>التوزيع:</strong> يمر عبر مزود الخدمة المحلي (ISP) مثل اتصالات الجزائر أو متعاملي الهاتف.</div>
            </div>
            <div class="step-item">
                <div class="step-number">3</div>
                <div><strong>الوصول:</strong> يصل إليك إما عبر WiFi المنزلية أو بيانات المحمول (3G/4G/5G).</div>
            </div>
        </div>
        <p style="font-size: 0.9rem; color: var(--accent); font-weight: bold;">💡 فهم هذه الرحلة يساعدك على معرفة سبب أي بطء أو ضعف في الإشارة.</p>
    </div>

    <div class="card">
        <h2><i class="fas fa-wifi"></i> 2. أنواع الإنترنت في المنزل والهاتف</h2>
        <div class="problem-grid">
            <div class="problem-card" style="border-color: var(--secondary);">
                <h4>🏠 الإنترنت المنزلي (WiFi)</h4>
                <p>يوصلك عبر كابل أو الألياف الضوئية (Fiber). يتميز بسرعات مستقرة وعالية، لكنه يتأثر بعدد الأشخاص المتصلين في نفس اللحظة.</p>
                <small>مثال: <strong>Idoom (اتصالات الجزائر)</strong></small>
            </div>
            <div class="problem-card" style="border-color: var(--accent);">
                <h4>📱 بيانات الهاتف (3G/4G/5G)</h4>
                <p>يعتمد على الأبراج (BTS) القريبة منك. سرعته متغيرة جداً وتتأثر بموقعك الجغرافي والتشويش المحيط.</p>
                <small>مثال: <strong>Mobilis, Djezzy, Ooredoo</strong></small>
            </div>
        </div>
        
        <h3 style="margin-top: 30px;"><i class="fas fa-columns"></i> مقارنة: المنزلي vs المحمول</h3>
        <div style="overflow-x: auto;">
            <table class="comparison-table">
                <thead>
                    <tr>
                        <th>النوع</th>
                        <th>مصدر الإشارة</th>
                        <th>السرعة</th>
                        <th>الاستقرار</th>
                        <th>أفضل استخدام</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>WiFi / Fiber</strong></td>
                        <td>الراوتر / الكابل</td>
                        <td>عالية جداً</td>
                        <td>مستقرة</td>
                        <td>المنزل، العمل من المكتب</td>
                    </tr>
                    <tr>
                        <td><strong>Mobile Data</strong></td>
                        <td>أبراج الهاتف</td>
                        <td>متغيرة</td>
                        <td>تعتمد على الموقع</td>
                        <td>أثناء التنقل، خارج المنزل</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
    
    <div class="card">
        <h2><i class="fas fa-tools"></i> 3. مشاكل الإنترنت الشائعة والتعامل معها</h2>
        <p style="margin-bottom: 20px; color: var(--text-light);">مرر الفأرة فوق المشكلة لمعرفة السبب والحل:</p>

        <div class="grid-container">
            <div class="info-box">
                <div class="icon-wrapper"><i class="fas fa-signal"></i></div>
                <h3>ضعف الإشارة</h3>
                <p><strong>السبب:</strong> البعد عن البرج أو وجود جدران سميكة تعيق وصول الموجات.</p>
                <p><strong>الحل:</strong> حاول الاقتراب من النافذة أو استخدم جهاز مقوي إشارة.</p>
                <div class="read-more">التفاصيل</div>
            </div>

            <div class="info-box">
                <div class="icon-wrapper"><i class="fas fa-broadcast-tower"></i></div>
                <h3>تشويش الإشارة</h3>
                <p><strong>السبب:</strong> أجهزة كهربائية قريبة أو تداخل من قنوات WiFi الجيران.</p>
                <p><strong>الحل:</strong> ضع الراوتر في مكان مرتفع وقم بتغيير قناة الـ WiFi.</p>
                <div class="read-more">التفاصيل</div>
            </div>

            <div class="info-box">
                <div class="icon-wrapper"><i class="fas fa-tachometer-alt"></i></div>
                <h3>بطء وقت الذروة</h3>
                <p><strong>السبب:</strong> ضغط كبير على البرج نتيجة كثرة المشتركين (18:00 – 23:00).</p>
                <p><strong>الحل:</strong> تجنب تحميل الملفات الضخمة في هذا الوقت واستخدمها لاحقاً.</p>
                <div class="read-more">التفاصيل</div>
            </div>

            <div class="info-box">
                <div class="icon-wrapper"><i class="fas fa-server"></i></div>
                <h3>مشاكل المزود</h3>
                <p><strong>السبب:</strong> بنية تحتية قديمة أو أعطال فنية في الكابلات الرئيسية للمزود.</p>
                <p><strong>الحل:</strong> تواصل مع مصلحة الزبائن أو فكر في تجربة مزود آخر.</p>
                <div class="read-more">التفاصيل</div>
            </div>
        </div>
    </div>

    <div class="card">
        <h2><i class="fas fa-lightbulb"></i> 4. نصائح عملية لتحسين الإنترنت</h2>
        
        <div class="tip-grid">
            <div class="tip-item"><i class="fas fa-arrow-up"></i> ضع الراوتر في مكان مرتفع ومفتوح بعيداً عن العوائق.</div>
            <div class="tip-item"><i class="fas fa-battery-half"></i> استخدم الـ WiFi داخل المنزل لتوفير بطارية هاتفك.</div>
            <div class="tip-item"><i class="fas fa-power-off"></i> أعد تشغيل (Restart) الهاتف أو المودم عند ملاحظة بطء مفاجئ.</div>
            <div class="tip-item"><i class="fas fa-expand-arrows-alt"></i> استخدم مقوي إشارة (Repeater) في الغرف البعيدة.</div>
            <div class="tip-item"><i class="fas fa-mobile-alt"></i> افحص جودة الشبكة بانتظام لفهم مستوى التغطية في منزلك.</div>
        </div>
    </div>

    <div class="card" style="border-right: 5px solid var(--primary);">
        <h2><i class="fas fa-satellite-dish"></i> 5. كيف تعرف قوة التغطية في منطقتك</h2>
        <p>يمكنك استخدام أدوات احترافية لفحص الشبكة مثل المهندسين:</p>
        <ul style="line-height: 2.5;">
            <li><span class="app-badge">NetMonster</span> لمعرفة قوة إشارة شبكة الهاتف (RSRP / SINR).</li>
            <li><span class="app-badge">WiFi Analyzer</span> لمعرفة تداخل الموجات في شبكتك المنزلية.</li>
        </ul>
        <p><strong>القاعدة الذهبية:</strong> كلما عرفت موقع الأبراج القريبة منك، كلما استطعت توجيه جهازك بشكل صحيح لتحسين السرعة.</p>
    </div>

    <div class="summary-box">
        <h3><i class="fas fa-check-circle"></i> ملخص لك أيها المستخدم</h3>
        <p>تذكر دائماً: حدد نوع اتصالك، راقب جودة الإشارة (ليس فقط عدد الأبراج)، وطبق النصائح البسيطة لتحصل على أفضل تجربة إنترنت ممكنة في الجزائر.</p>
    </div>

</div>
<script>
// 1. Define the keys we want to save
const formFields = ['lat', 'lon', 'rsrp', 'sinr', 'network', 'operator', 'place', 'wilaya', 'city'];

// 2. Function to Save Data
function saveToLocal() {
    const formData = {};
    formFields.forEach(field => {
        const element = document.querySelector(`[name="${field}"]`);
        if (element) {
            formData[field] = element.value;
        }
    });
    localStorage.setItem('isharati_pro_data', JSON.stringify(formData));
}

// 3. Function to Load Data
function loadFromLocal() {
    const savedData = localStorage.getItem('isharati_pro_data');
    if (savedData) {
        const data = JSON.parse(savedData);
        formFields.forEach(field => {
            const element = document.querySelector(`[name="${field}"]`);
            if (element && data[field]) {
                element.value = data[field];
            }
        });
        console.log("Data restored from local storage.");
    }
}

// 4. Initialize Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    // Load existing data
    loadFromLocal();

    // Listen for changes on all inputs in the form
    const form = document.getElementById('analysisForm');
    if (form) {
        form.querySelectorAll('input, select').forEach(input => {
            input.addEventListener('input', saveToLocal);
        });
    }
});

// 5. Optional: Clear data on form reset
function clearStorage() {
    localStorage.removeItem('isharati_pro_data');
}
</script>
<script>
        function clearForm() {
            if (confirm("هل تريد مسح جميع البيانات المدخلة؟")) {
                localStorage.removeItem('isharati_pro_data');
                const form = document.getElementById('analysisForm');
                if (form) {
                    form.reset();
                }
            }
        }
    </script>
<script>
    // منع الزر الأيمن للفأرة
    document.addEventListener('contextmenu', event => event.preventDefault());

    // منع اختصارات لوحة المفاتيح مثل Ctrl+U (رؤية السورس)
    document.onkeydown = function(e) {
        if (e.ctrlKey && (e.keyCode === 85 || e.keyCode === 83)) {
            return false;
        }
    };
</script>
</body>
</html>
"""

# ==================== ROUTES ====================
@app.route("/", methods=["GET", "POST"])
def index():
    analysis = None
    rec = ""
    rsrp = sinr = 0
    network_score = None
    star_rating = None
    
    if request.method == "POST":
        try:
            lat = float(request.form.get("lat", 0))
            lon = float(request.form.get("lon", 0))
            rsrp = int(request.form.get("rsrp", -140))
            sinr = int(request.form.get("sinr", 0))
            network_type = request.form.get("network", "4G")
            operator = request.form.get("operator", "Djezzy")
            place = request.form.get("place", "Indoor")
            wilaya = request.form.get("Wilaya", "")
            city = request.form.get("city", "")
            
            speed_data_str = request.form.get("speed_data", "")
            speed_data = None
            if speed_data_str:
                try:
                    speed_data = json.loads(speed_data_str)
                except:
                    pass
            
            summary, technical_explanation, recommendations, network_score, score_breakdown, rec, issue_type = analyze_network(
                lat, lon, rsrp, sinr, network_type, operator, place, wilaya, city, speed_data
            )
            
            analysis = summary
            star_rating = score_breakdown['stars']
            
            # Store in session for PDF generation
            session['report_data'] = {
                'lat': lat, 'lon': lon, 'rsrp': rsrp, 'sinr': sinr,
                'network': network_type, 'operator': operator, 'place': place,
                'wilaya': wilaya, 'city': city, 'speed_data': speed_data,
                'summary': summary, 'technical_explanation': technical_explanation,
                'recommendations': recommendations, 'network_score': network_score,
                'score_breakdown': score_breakdown, 'short_recommendation': rec
            }
            
            # Save to analytics history
            analysis_data = {
                'lat': lat, 'lon': lon, 'rsrp': rsrp, 'sinr': sinr,
                'network': network_type, 'operator': operator, 'place': place,
                'wilaya': wilaya, 'city': city, 'speed_data': speed_data
            }
            
            analysis_results = {
                'network_score': network_score,
                'score_breakdown': score_breakdown,
                'issue_type': issue_type,
                'summary': summary,
                'recommendations': recommendations,
                'short_recommendation': rec
            }
            
            save_analytics_record(analysis_data, analysis_results)
            
        except ValueError as e:
            rec = f"خطأ في البيانات: {str(e)}"

    return render_template_string(HTML_PAGE, analysis=analysis, rec=rec, rsrp=rsrp, sinr=sinr,
                                 network_score=network_score, star_rating=star_rating, request=request)

@app.route("/analytics")
def analytics_page():
    """Display analytics history"""
    stats = get_analytics_stats()
    return render_template_string(ANALYTICS_PAGE, analytics=analytics_history, 
                                 analytics_json=json.dumps(analytics_history),
                                 stats=stats)

@app.route("/download_pdf")
def download_pdf():
    report_data = session.get('report_data')
    if not report_data:
        return "لا توجد بيانات. قم بتشغيل التحليل أولاً.", 400
    
    pdf = generate_advanced_pdf(report_data)
    return send_file(
        io.BytesIO(pdf),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'ISHARATI_Report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    )

@app.route("/download_pdf_analytics/<record_id>")
def download_pdf_analytics(record_id):
    """Download PDF for a specific analytics record"""
    record = next((r for r in analytics_history if r['id'] == record_id), None)
    if not record:
        return "التحليل غير موجود", 404
    
    report_data = {
        'lat': record['lat'], 
        'lon': record['lon'], 
        'rsrp': record['rsrp'], 
        'sinr': record['sinr'],
        'network': record['network_type'], 
        'operator': record['operator'], 
        'place': record['place'],
        'wilaya': record['wilaya'], 
        'city': record['city'], 
        'speed_data': record.get('speed_data'),
        'network_score': record['network_score'],
        'score_breakdown': record['score_breakdown']
    }
    
    pdf = generate_advanced_pdf(report_data)
    return send_file(
        io.BytesIO(pdf),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'ISHARATI_Analytics_{record_id}.pdf'
    )

@app.route("/api/delete_analytics/<record_id>", methods=["DELETE"])
def delete_analytics(record_id):
    """Delete a specific analytics record"""
    global analytics_history
    analytics_history = [r for r in analytics_history if r['id'] != record_id]
    return jsonify({"success": True})

@app.route("/api/clear_all_analytics", methods=["DELETE"])
def clear_all_analytics():
    """Clear all analytics history"""
    global analytics_history
    analytics_history = []
    return jsonify({"success": True})
@app.route('/api/download-test')
def download_test():
    # Generates 10MB of empty data for the browser to download
    data = b"\0" * 10_000_000 
    return send_file(
        io.BytesIO(data),
        mimetype='application/octet-stream',
        as_attachment=True,
        download_name='testfile'
    )
@app.route("/speed-test")
def speed_test_page():
    return render_template_string(SPEED_TEST_PAGE)
@app.route('/api/speed-test')
def speed_test_fallback():
    # We return a small JSON or redirect the logic to the frontend
    return jsonify({
        "info": "Please use client-side JS for accurate testing on Vercel"
    })
@app.route("/guide")
def guide():
    # Use the original GUIDE_PAGE from your code
    return render_template_string(GUIDE_PAGE)

@app.route("/knowledge")
def knowledge():
    # Use the original KNOWLEDGE_PAGE from your code
    return render_template_string(KNOWLEDGE_PAGE)

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 ISHARATI PRO v1.0 - Advanced Network Diagnostic Platform")
    print("=" * 60)
    print("✅ Features:")
    print("   - Complete UI Design")
    print("   - Advanced Analytics Engine")
    print("   - Network Quality Scoring")
    print("   - PDF Report Generation")
    print("   - Speed Test Integration")
    print("   - 📊 Previous Analytics Page with:")
    print("      • Search and Filter")
    print("      • Statistics Dashboard")
    print("      • Detailed View Modal")
    print("      • PDF Export per Record")
    print("      • Delete Functionality")
    print("=" * 60)
    print("🌐 Access at: http://localhost:5000")
    print("📊 Analytics: http://localhost:5000/analytics")
    print("=" * 60)
    app.run(debug=True, port=5000, host='0.0.0.0')


