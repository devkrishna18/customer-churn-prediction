from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import traceback
import io
import sqlite3
import pickle
import os

app = Flask(__name__)
CORS(app, supports_credentials=True)

DB_PATH = "customers.db"
model = pickle.load(open("churn_prediction_model.pkl", "rb"))

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            age INTEGER,
            gender TEXT,
            churn_prob REAL,
            tenure INTEGER,
            citytier INTEGER,
            satisfactionscore INTEGER,
            complain INTEGER
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route("/upload", methods=["POST"])
def upload():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files['file']
        
        file_content = file.stream.read().decode("utf-8")
        lines = file_content.strip().splitlines()
        cleaned_lines = [line.strip().strip('"') for line in lines]
        cleaned_csv_string = "\n".join(cleaned_lines)
        
        df = pd.read_csv(io.StringIO(cleaned_csv_string))

        # --- FIX: Normalize all column names to lowercase ---
        df.columns = [col.lower() for col in df.columns]
        
        # --- Use lowercase for the expected features list ---
        expected_features = [
            'tenure', 'citytier', 'warehousetohome', 'hourspendonapp',
            'numberofdeviceregistered', 'satisfactionscore', 'numberofaddress',
            'complain', 'orderamounthikefromlastyear', 'couponused', 'ordercount',
            'daysincelastorder', 'cashbackamount', 'gender_female', 'gender_male',
            'maritalstatus_divorced', 'maritalstatus_married', 'maritalstatus_single'
        ]
        
        # Check for missing columns after converting to lowercase
        missing_cols = [col for col in expected_features if col not in df.columns]
        if missing_cols:
            return jsonify({"error": f"Missing required columns in CSV: {', '.join(missing_cols)}"}), 400

        X = df[expected_features]
        preds = model.predict_proba(X)[:, 1]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM customers")

        for i, row in df.iterrows():
            name = f"Customer_{i+1}"
            age = 0 
            churn_prob = float(preds[i])
            # --- Use the lowercase column name to determine gender ---
            gender = 'Female' if row['gender_female'] == 1 else 'Male'
            
            tenure = int(row['tenure'])
            citytier = int(row['citytier'])
            satisfactionscore = int(row['satisfactionscore'])
            complain = int(row['complain'])
            
            c.execute(
                "INSERT INTO customers (name, age, gender, churn_prob, tenure, citytier, satisfactionscore, complain) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (name, age, gender, churn_prob, tenure, citytier, satisfactionscore, complain)
            )

        conn.commit()
        conn.close()
        
        return jsonify({"message": "File processed & predictions saved"})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/customers", methods=["GET"])
def get_customers():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM customers ORDER BY churn_prob DESC")
    rows = c.fetchall()
    conn.close()

    data = [dict(row) for row in rows]
    return jsonify(data)

@app.route("/stats", methods=["GET"])
def get_stats():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute("SELECT COUNT(*) as count FROM customers WHERE churn_prob > 0.5")
        churn_count = c.fetchone()['count']
        c.execute("SELECT COUNT(*) as count FROM customers WHERE churn_prob <= 0.5")
        retain_count = c.fetchone()['count']

        c.execute("SELECT AVG(tenure) as avg_tenure FROM customers WHERE churn_prob > 0.5")
        avg_tenure_churn = c.fetchone()['avg_tenure'] or 0
        c.execute("SELECT AVG(tenure) as avg_tenure FROM customers WHERE churn_prob <= 0.5")
        avg_tenure_retain = c.fetchone()['avg_tenure'] or 0

        c.execute("SELECT citytier, COUNT(*) as total, SUM(CASE WHEN churn_prob > 0.5 THEN 1 ELSE 0 END) as churned FROM customers GROUP BY citytier")
        churn_by_tier_rows = c.fetchall()
        churn_by_tier = {row['citytier']: (row['churned'] / row['total']) * 100 if row['total'] > 0 else 0 for row in churn_by_tier_rows}

        c.execute("SELECT AVG(churn_prob) as avg_prob FROM customers WHERE complain = 1")
        complaint_churn_prob = c.fetchone()['avg_prob'] or 0
        c.execute("SELECT AVG(churn_prob) as avg_prob FROM customers WHERE complain = 0")
        no_complaint_churn_prob = c.fetchone()['avg_prob'] or 0

        conn.close()

        return jsonify({
            "at_risk": churn_count,
            "likely_to_stay": retain_count,
            "avg_tenure_churned": round(avg_tenure_churn, 1),
            "avg_tenure_retained": round(avg_tenure_retain, 1),
            "churn_rate_by_city": churn_by_tier,
            "complaint_impact": {
                "with_complaint": round(complaint_churn_prob * 100, 1),
                "without_complaint": round(no_complaint_churn_prob * 100, 1)
            }
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route("/segments", methods=["GET"])
def get_segments():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT tenure, churn_prob FROM customers")
        customers = c.fetchall()
        conn.close()

        segments = {
            "High-Value At-Risk": 0,
            "New & Unhappy": 0,
            "Loyal Champions": 0,
            "New & Promising": 0,
            "Other": 0
        }

        for customer in customers:
            tenure = customer['tenure']
            churn_prob = customer['churn_prob']

            if tenure > 12 and churn_prob > 0.6:
                segments["High-Value At-Risk"] += 1
            elif tenure <= 3 and churn_prob > 0.6:
                segments["New & Unhappy"] += 1
            elif tenure > 12 and churn_prob <= 0.3:
                segments["Loyal Champions"] += 1
            elif tenure <= 3 and churn_prob <= 0.3:
                segments["New & Promising"] += 1
            else:
                segments["Other"] += 1
        
        return jsonify(segments)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/insights", methods=["GET"])
def get_insights():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Get all customers data
        c.execute("SELECT * FROM customers")
        customers = c.fetchall()
        conn.close()
        
        if not customers:
            return jsonify({"insights": []})
        
        insights = []
        
        # Insight 1: Complaint-based churn risk
        high_complaint_customers = [c for c in customers if c['complain'] >= 1]
        if high_complaint_customers:
            avg_churn_complaints = sum(c['churn_prob'] for c in high_complaint_customers) / len(high_complaint_customers)
            no_complaint_customers = [c for c in customers if c['complain'] == 0]
            avg_churn_no_complaints = sum(c['churn_prob'] for c in no_complaint_customers) / len(no_complaint_customers) if no_complaint_customers else 0
            
            if avg_churn_no_complaints > 0:
                multiplier = avg_churn_complaints / avg_churn_no_complaints
                insights.append({
                    "title": "Complaint Impact Analysis",
                    "description": f"Customers with complaints have a {multiplier:.1f}× higher churn risk",
                    "severity": "high" if multiplier > 2 else "medium",
                    "metric": f"{len(high_complaint_customers)} customers affected",
                    "icon": "alert"
                })
        
        # Insight 2: Low satisfaction score impact
        low_satisfaction = [c for c in customers if c['satisfactionscore'] <= 2]
        if low_satisfaction:
            avg_churn_low_sat = sum(c['churn_prob'] for c in low_satisfaction) / len(low_satisfaction)
            high_satisfaction = [c for c in customers if c['satisfactionscore'] >= 4]
            avg_churn_high_sat = sum(c['churn_prob'] for c in high_satisfaction) / len(high_satisfaction) if high_satisfaction else 0
            
            if avg_churn_high_sat > 0:
                multiplier = avg_churn_low_sat / avg_churn_high_sat
                insights.append({
                    "title": "Satisfaction Score Correlation",
                    "description": f"Low satisfaction (≤2) customers are {multiplier:.1f}× more likely to churn",
                    "severity": "high" if multiplier > 3 else "medium",
                    "metric": f"{len(low_satisfaction)} customers at risk",
                    "icon": "thumbs-down"
                })
        
        # Insight 3: Tenure and churn relationship
        new_customers = [c for c in customers if c['tenure'] <= 6]
        if new_customers:
            new_churn_rate = sum(1 for c in new_customers if c['churn_prob'] > 0.5) / len(new_customers)
            insights.append({
                "title": "New Customer Retention Challenge",
                "description": f"{new_churn_rate*100:.1f}% of customers with ≤6 months tenure are at high churn risk",
                "severity": "high" if new_churn_rate > 0.4 else "medium",
                "metric": f"{len(new_customers)} new customers",
                "icon": "users"
            })
        
        # Insight 4: City tier impact
        c = sqlite3.connect(DB_PATH).cursor()
        c.execute("""
            SELECT citytier, AVG(churn_prob) as avg_churn 
            FROM customers 
            GROUP BY citytier 
            ORDER BY avg_churn DESC 
            LIMIT 1
        """)
        highest_risk_tier = c.fetchone()
        if highest_risk_tier:
            tier, avg_churn = highest_risk_tier
            insights.append({
                "title": "Geographic Risk Pattern",
                "description": f"City Tier {tier} shows highest churn risk at {avg_churn*100:.1f}%",
                "severity": "medium",
                "metric": f"Tier {tier} customers",
                "icon": "map-pin"
            })
        
        # Insight 5: Combined risk factors (complaints + low satisfaction)
        high_risk_combo = [c for c in customers if c['complain'] >= 1 and c['satisfactionscore'] <= 2]
        if high_risk_combo:
            avg_churn_combo = sum(c['churn_prob'] for c in high_risk_combo) / len(high_risk_combo)
            overall_avg = sum(c['churn_prob'] for c in customers) / len(customers)
            multiplier = avg_churn_combo / overall_avg if overall_avg > 0 else 1
            
            insights.append({
                "title": "Critical Risk Combination",
                "description": f"Customers with complaints AND low satisfaction have {multiplier:.1f}× higher churn risk",
                "severity": "critical" if multiplier > 2 else "high",
                "metric": f"{len(high_risk_combo)} customers in critical state",
                "icon": "alert-triangle"
            })
        
        return jsonify({"insights": insights})
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
@app.route("/recommendations", methods=["GET"])
def get_recommendations():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM customers")
        customers = c.fetchall()
        conn.close()
        
        if not customers:
            return jsonify({"recommendations": []})
        
        recommendations = []
        
        # Categorize customers and generate recommendations
        for customer in customers:
            customer_dict = dict(customer)
            tenure = customer_dict['tenure']
            churn_prob = customer_dict['churn_prob']
            complain = customer_dict['complain']
            satisfaction = customer_dict['satisfactionscore']
            
            # Determine segment
            segment = ""
            recommended_actions = []
            priority = ""
            
            if tenure > 12 and churn_prob > 0.6:
                segment = "High-Value At-Risk"
                priority = "critical"
                recommended_actions = [
                    {
                        "action": "Offer Discount",
                        "details": "Provide 20-30% loyalty discount on next purchase",
                        "urgency": "immediate"
                    },
                    {
                        "action": "Priority Support",
                        "details": "Assign dedicated account manager",
                        "urgency": "immediate"
                    },
                    {
                        "action": "Personal Outreach",
                        "details": "Executive-level call to understand pain points",
                        "urgency": "within 24 hours"
                    }
                ]
            elif tenure <= 3 and churn_prob > 0.6:
                segment = "New & Unhappy"
                priority = "high"
                recommended_actions = [
                    {
                        "action": "Product Education",
                        "details": "Send onboarding tutorial videos and guides",
                        "urgency": "immediate"
                    },
                    {
                        "action": "Welcome Discount",
                        "details": "10-15% discount on next order to encourage retention",
                        "urgency": "within 48 hours"
                    },
                    {
                        "action": "Check-in Call",
                        "details": "Customer success team to ensure smooth onboarding",
                        "urgency": "within 3 days"
                    }
                ]
            elif tenure > 12 and churn_prob <= 0.3:
                segment = "Loyal Champions"
                priority = "low"
                recommended_actions = [
                    {
                        "action": "Referral Program",
                        "details": "Invite to VIP referral program with rewards",
                        "urgency": "no urgency"
                    },
                    {
                        "action": "Exclusive Benefits",
                        "details": "Early access to new products and features",
                        "urgency": "no urgency"
                    },
                    {
                        "action": "Thank You Gift",
                        "details": "Send appreciation gift or loyalty bonus",
                        "urgency": "quarterly"
                    }
                ]
            elif tenure <= 3 and churn_prob <= 0.3:
                segment = "New & Promising"
                priority = "medium"
                recommended_actions = [
                    {
                        "action": "Product Education",
                        "details": "Share best practices and tips for product usage",
                        "urgency": "within 1 week"
                    },
                    {
                        "action": "Engagement Campaign",
                        "details": "Regular check-ins to build relationship",
                        "urgency": "ongoing"
                    },
                    {
                        "action": "Community Invitation",
                        "details": "Invite to user community and events",
                        "urgency": "within 2 weeks"
                    }
                ]
            else:
                segment = "Other"
                priority = "medium"
                recommended_actions = [
                    {
                        "action": "Survey Feedback",
                        "details": "Send satisfaction survey to understand needs",
                        "urgency": "within 1 week"
                    },
                    {
                        "action": "Re-engagement Campaign",
                        "details": "Targeted email campaign with product updates",
                        "urgency": "within 2 weeks"
                    }
                ]
            
            # Add specific actions based on complaints
            if complain >= 1:
                recommended_actions.insert(0, {
                    "action": "Complaint Resolution",
                    "details": "Immediate investigation and resolution of complaint",
                    "urgency": "immediate"
                })
                priority = "critical" if priority != "critical" else priority
            
            # Add specific actions based on low satisfaction
            if satisfaction <= 2:
                recommended_actions.insert(0 if complain == 0 else 1, {
                    "action": "Priority Support",
                    "details": "Fast-track support access and dedicated assistance",
                    "urgency": "within 24 hours"
                })
            
            recommendations.append({
                "customer_id": customer_dict['id'],
                "customer_name": customer_dict['name'],
                "segment": segment,
                "churn_probability": round(churn_prob * 100, 1),
                "priority": priority,
                "recommended_actions": recommended_actions
            })
        
        # Sort by priority (critical > high > medium > low)
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        recommendations.sort(key=lambda x: priority_order[x['priority']])
        
        return jsonify({"recommendations": recommendations})
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/segment-strategies", methods=["GET"])
def get_segment_strategies():
    """Get high-level strategy for each segment"""
    try:
        strategies = {
            "High-Value At-Risk": {
                "description": "Long-term customers showing churn signals",
                "goal": "Win-back and retention",
                "key_actions": [
                    "Offer discount (20-30% loyalty discount)",
                    "Priority support (dedicated account manager)",
                    "Personal outreach (executive-level engagement)"
                ],
                "expected_impact": "Reduce churn by 40-60%",
                "color": "#EF4444"
            },
            "New & Unhappy": {
                "description": "Recently acquired customers at risk",
                "goal": "Onboarding improvement and early engagement",
                "key_actions": [
                    "Product education (tutorials and guides)",
                    "Offer discount (10-15% welcome discount)",
                    "Priority support (customer success check-in)"
                ],
                "expected_impact": "Reduce early churn by 30-50%",
                "color": "#F97316"
            },
            "Loyal Champions": {
                "description": "Satisfied long-term customers",
                "goal": "Advocacy and retention",
                "key_actions": [
                    "Referral program (VIP rewards)",
                    "Exclusive benefits (early access)",
                    "Thank you gift (appreciation rewards)"
                ],
                "expected_impact": "Increase lifetime value by 20-30%",
                "color": "#22C55E"
            },
            "New & Promising": {
                "description": "Recently acquired satisfied customers",
                "goal": "Nurture and engagement",
                "key_actions": [
                    "Product education (best practices)",
                    "Engagement campaign (regular check-ins)",
                    "Community invitation (events and networking)"
                ],
                "expected_impact": "Increase conversion to champions by 40%",
                "color": "#3B82F6"
            },
            "Other": {
                "description": "Mid-tenure customers with moderate risk",
                "goal": "Re-engagement and monitoring",
                "key_actions": [
                    "Survey feedback (understand needs)",
                    "Re-engagement campaign (product updates)",
                    "Offer discount (conditional incentives)"
                ],
                "expected_impact": "Prevent drift and maintain stability",
                "color": "#6B7280"
            }
        }
        
        return jsonify({"strategies": strategies})
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/churn-drivers", methods=["GET"])
def get_churn_drivers():
    """Identify top churn drivers for each customer"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM customers")
        customers = c.fetchall()
        conn.close()
        
        if not customers:
            return jsonify({"churn_drivers": []})
        
        # Calculate averages for comparison
        avg_tenure = sum(c['tenure'] for c in customers) / len(customers)
        avg_satisfaction = sum(c['satisfactionscore'] for c in customers) / len(customers)
        
        churn_drivers_data = []
        
        for customer in customers:
            customer_dict = dict(customer)
            drivers = []
            risk_score = 0
            
            # Driver 1: Complaints
            if customer_dict['complain'] >= 1:
                complaint_impact = customer_dict['complain'] * 25  # Each complaint adds 25% risk
                drivers.append({
                    "driver": "Active Complaints",
                    "severity": "critical" if customer_dict['complain'] > 1 else "high",
                    "description": f"{customer_dict['complain']} unresolved complaint(s)",
                    "impact_score": min(complaint_impact, 40),
                    "recommendation": "Immediate complaint resolution required"
                })
                risk_score += min(complaint_impact, 40)
            
            # Driver 2: Low Satisfaction Score
            if customer_dict['satisfactionscore'] <= 2:
                satisfaction_gap = (3 - customer_dict['satisfactionscore']) * 15
                drivers.append({
                    "driver": "Low Satisfaction Score",
                    "severity": "high" if customer_dict['satisfactionscore'] == 1 else "medium",
                    "description": f"Satisfaction score: {customer_dict['satisfactionscore']}/5 (Critical)",
                    "impact_score": satisfaction_gap,
                    "recommendation": "Priority support and satisfaction survey needed"
                })
                risk_score += satisfaction_gap
            elif customer_dict['satisfactionscore'] == 3:
                drivers.append({
                    "driver": "Medium Satisfaction",
                    "severity": "medium",
                    "description": f"Satisfaction score: {customer_dict['satisfactionscore']}/5 (At risk)",
                    "impact_score": 10,
                    "recommendation": "Proactive engagement to improve experience"
                })
                risk_score += 10
            
            # Driver 3: Short Tenure (Low Usage/Engagement)
            if customer_dict['tenure'] < 3:
                tenure_risk = (3 - customer_dict['tenure']) * 8
                drivers.append({
                    "driver": "Low Engagement (New Customer)",
                    "severity": "high",
                    "description": f"Only {customer_dict['tenure']} months tenure - high early churn risk",
                    "impact_score": tenure_risk,
                    "recommendation": "Enhanced onboarding and product education"
                })
                risk_score += tenure_risk
            elif customer_dict['tenure'] < 6:
                drivers.append({
                    "driver": "Limited Usage History",
                    "severity": "medium",
                    "description": f"{customer_dict['tenure']} months tenure - still in adoption phase",
                    "impact_score": 8,
                    "recommendation": "Regular check-ins to ensure value realization"
                })
                risk_score += 8
            
            # Driver 4: Long tenure but low satisfaction (indicates recent problem)
            if customer_dict['tenure'] > 12 and customer_dict['satisfactionscore'] <= 2:
                drivers.append({
                    "driver": "Long Resolution Time",
                    "severity": "critical",
                    "description": f"Long-term customer ({customer_dict['tenure']} months) with recent dissatisfaction",
                    "impact_score": 30,
                    "recommendation": "Urgent win-back campaign - investigate recent changes"
                })
                risk_score += 30
            
            # Driver 5: Combined risk (complaints + low satisfaction)
            if customer_dict['complain'] >= 1 and customer_dict['satisfactionscore'] <= 2:
                drivers.append({
                    "driver": "Unresolved Issues",
                    "severity": "critical",
                    "description": "Complaints with low satisfaction indicates ongoing problem",
                    "impact_score": 25,
                    "recommendation": "Executive escalation required immediately"
                })
                risk_score += 25
            
            # Driver 6: City Tier risk (if tier 1 or 3 - adjust based on your data)
            if customer_dict['citytier'] == 3:
                drivers.append({
                    "driver": "Geographic Risk",
                    "severity": "low",
                    "description": f"City Tier {customer_dict['citytier']} - higher churn tendency",
                    "impact_score": 5,
                    "recommendation": "Monitor competitive activity in this region"
                })
                risk_score += 5
            
            # Sort drivers by impact score (highest first)
            drivers.sort(key=lambda x: x['impact_score'], reverse=True)
            
            # Get top 3 drivers only
            top_drivers = drivers[:3] if len(drivers) > 3 else drivers
            
            churn_drivers_data.append({
                "customer_id": customer_dict['id'],
                "customer_name": customer_dict['name'],
                "churn_probability": round(customer_dict['churn_prob'] * 100, 1),
                "total_risk_score": min(risk_score, 100),  # Cap at 100
                "top_drivers": top_drivers,
                "driver_count": len(drivers)
            })
        
        # Sort by risk score (highest first)
        churn_drivers_data.sort(key=lambda x: x['total_risk_score'], reverse=True)
        
        return jsonify({"churn_drivers": churn_drivers_data})
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/driver-summary", methods=["GET"])
def get_driver_summary():
    """Get overall summary of churn drivers across all customers"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM customers")
        customers = c.fetchall()
        conn.close()
        
        if not customers:
            return jsonify({"summary": {}})
        
        total_customers = len(customers)
        
        # Count driver occurrences
        complaints_count = sum(1 for c in customers if c['complain'] >= 1)
        low_satisfaction_count = sum(1 for c in customers if c['satisfactionscore'] <= 2)
        low_tenure_count = sum(1 for c in customers if c['tenure'] < 6)
        long_resolution_count = sum(1 for c in customers if c['tenure'] > 12 and c['satisfactionscore'] <= 2)
        
        # Calculate average churn probability for each driver
        complaints_avg_churn = sum(c['churn_prob'] for c in customers if c['complain'] >= 1) / complaints_count if complaints_count > 0 else 0
        low_sat_avg_churn = sum(c['churn_prob'] for c in customers if c['satisfactionscore'] <= 2) / low_satisfaction_count if low_satisfaction_count > 0 else 0
        low_tenure_avg_churn = sum(c['churn_prob'] for c in customers if c['tenure'] < 6) / low_tenure_count if low_tenure_count > 0 else 0
        long_res_avg_churn = sum(c['churn_prob'] for c in customers if c['tenure'] > 12 and c['satisfactionscore'] <= 2) / long_resolution_count if long_resolution_count > 0 else 0
        
        summary = {
            "total_customers": total_customers,
            "drivers": [
                {
                    "name": "Complaints",
                    "affected_customers": complaints_count,
                    "percentage": round((complaints_count / total_customers) * 100, 1),
                    "avg_churn_prob": round(complaints_avg_churn * 100, 1),
                    "priority": "critical"
                },
                {
                    "name": "Low Satisfaction",
                    "affected_customers": low_satisfaction_count,
                    "percentage": round((low_satisfaction_count / total_customers) * 100, 1),
                    "avg_churn_prob": round(low_sat_avg_churn * 100, 1),
                    "priority": "high"
                },
                {
                    "name": "Low Engagement/Usage",
                    "affected_customers": low_tenure_count,
                    "percentage": round((low_tenure_count / total_customers) * 100, 1),
                    "avg_churn_prob": round(low_tenure_avg_churn * 100, 1),
                    "priority": "high"
                },
                {
                    "name": "Long Resolution Time",
                    "affected_customers": long_resolution_count,
                    "percentage": round((long_resolution_count / total_customers) * 100, 1),
                    "avg_churn_prob": round(long_res_avg_churn * 100, 1),
                    "priority": "critical"
                }
            ]
        }
        
        # Sort by affected customers (descending)
        summary["drivers"].sort(key=lambda x: x['affected_customers'], reverse=True)
        
        return jsonify({"summary": summary})
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    


if __name__ == "__main__":
    app.run(debug=True)
