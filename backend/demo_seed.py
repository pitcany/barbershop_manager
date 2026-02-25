"""
Realistic demo data seeder for barbershop shops.
Generates clients, barbers, services, appointments, conversations,
transactions, events, waitlist entries, and recovered revenue.
"""
import uuid
import random
from datetime import datetime, timezone, timedelta

def uid():
    return str(uuid.uuid4())

# ======================== DATA POOLS ========================

FIRST_NAMES_M = ["Marcus", "James", "David", "Anthony", "Robert", "Michael", "Chris", "Kevin",
                  "Derek", "Brandon", "Jamal", "Tyler", "Andre", "Darius", "Malik", "Carlos",
                  "Trevor", "Isaiah", "Terrence", "Omar"]
FIRST_NAMES_F = ["Maria", "Jessica", "Tanya", "Nicole", "Alicia", "Keisha", "Sarah", "Lisa",
                  "Brianna", "Jasmine"]
LAST_NAMES = ["Johnson", "Williams", "Brown", "Davis", "Wilson", "Taylor", "Anderson", "Thomas",
              "Jackson", "White", "Harris", "Martin", "Garcia", "Rivera", "Clark", "Lewis",
              "Robinson", "Walker", "Young", "Allen", "King", "Wright", "Scott", "Hill", "Green"]

BARBER_PROFILES = [
    {"name": "Marcus Johnson", "email": "marcus@shop.com", "phone": "+15551001001"},
    {"name": "David Lee", "email": "david@shop.com", "phone": "+15551001002"},
    {"name": "Anthony Davis", "email": "anthony@shop.com", "phone": "+15551001003"},
    {"name": "Chris Walker", "email": "chris@shop.com", "phone": "+15551001004"},
]

SERVICE_MENU = [
    {"name": "Classic Haircut", "description": "Traditional cut with clippers and scissors", "duration_minutes": 30, "price": 25.00},
    {"name": "Fade", "description": "Low, mid, or high fade with sharp line-up", "duration_minutes": 35, "price": 30.00},
    {"name": "Beard Trim & Shape", "description": "Full beard sculpting with hot towel finish", "duration_minutes": 20, "price": 15.00},
    {"name": "Premium Cut + Hot Towel", "description": "Haircut with hot towel, massage, and styling", "duration_minutes": 45, "price": 50.00},
    {"name": "Kids Cut (12 & under)", "description": "Haircut for children 12 and under", "duration_minutes": 25, "price": 18.00},
    {"name": "Line-Up Only", "description": "Edge clean-up and shape-up", "duration_minutes": 15, "price": 12.00},
    {"name": "Full Service (Cut + Beard)", "description": "Haircut and beard trim combo", "duration_minutes": 50, "price": 40.00},
]

# Realistic SMS conversation templates
CONVERSATION_TEMPLATES = [
    # Booking flow
    [
        ("inbound", "Hey, can I book a fade for this Saturday?"),
        ("outbound", "Hi! We'd love to get you in. We have openings at 10:00 AM, 11:30 AM, and 2:00 PM. Which works for you?"),
        ("inbound", "11:30 works. With Marcus if possible"),
        ("outbound", "Done! You're booked with Marcus at 11:30 AM Saturday. A $20 deposit is required to confirm. I'll text you a payment link."),
        ("inbound", "Cool, just paid it"),
        ("outbound", "Payment received! See you Saturday. Reply CANCEL to cancel or CHANGE to reschedule."),
    ],
    # Rescheduling
    [
        ("inbound", "I need to move my appointment tomorrow. Something came up"),
        ("outbound", "No problem! Your current appointment is Tuesday at 3 PM. I can move you to Wednesday at 2 PM or Thursday at 10 AM. Which do you prefer?"),
        ("inbound", "Thursday 10am"),
        ("outbound", "You're rescheduled to Thursday at 10:00 AM with David. Your deposit transfers over. See you then!"),
    ],
    # Reminder response
    [
        ("outbound", "Reminder: You have an appointment tomorrow at 2:00 PM with Anthony. Reply YES to confirm or CANCEL to cancel."),
        ("inbound", "YES"),
        ("outbound", "Confirmed! See you tomorrow at 2:00 PM."),
    ],
    # No-show follow-up
    [
        ("outbound", "We missed you today! You had an appointment at 11:00 AM. Would you like to rebook?"),
        ("inbound", "Sorry I totally forgot. Can I come in next week?"),
        ("outbound", "Of course! I have openings Monday at 1 PM or Wednesday at 3 PM. A deposit will be required for rebooking. Which works?"),
        ("inbound", "Monday 1pm please"),
        ("outbound", "Booked for Monday at 1:00 PM. Deposit link sent. Looking forward to seeing you!"),
    ],
    # New client inquiry
    [
        ("inbound", "Hi, do you guys do beard trims? How much?"),
        ("outbound", "Hey! Yes we do. Beard Trim & Shape is $15 (20 min) or you can get the Full Service Cut + Beard combo for $40 (50 min). Want to book?"),
        ("inbound", "Full service sounds good. What's available this week?"),
        ("outbound", "We have openings Thursday at 11 AM with Chris or Friday at 3 PM with Marcus. Both are great with beards."),
        ("inbound", "Friday 3pm with Marcus"),
        ("outbound", "You're all set! Friday at 3:00 PM with Marcus. A $20 deposit is needed to hold your spot. I'll send the link now."),
    ],
    # Deposit follow-up
    [
        ("outbound", "Hi! Just a reminder that your deposit of $20 is still pending for your appointment Friday at 2 PM. Pay here to confirm your spot."),
        ("inbound", "Just paid, thanks"),
        ("outbound", "Got it! You're confirmed for Friday at 2:00 PM with David. See you then!"),
    ],
    # Cancellation
    [
        ("inbound", "I need to cancel my appointment for tomorrow"),
        ("outbound", "I've cancelled your appointment for tomorrow at 10:00 AM. Your deposit has been applied as credit for your next visit. Would you like to rebook?"),
        ("inbound", "Not right now, maybe next week"),
        ("outbound", "No worries! Just text us when you're ready and we'll get you in. Have a great day!"),
    ],
    # Waitlist notification
    [
        ("outbound", "Great news! A slot just opened up today at 4:00 PM with Marcus. You're first on the waitlist. Want it?"),
        ("inbound", "Yes!"),
        ("outbound", "Booked! Today at 4:00 PM with Marcus. No deposit needed since it's same-day. See you soon!"),
    ],
    # Repeat client
    [
        ("inbound", "Same time next week?"),
        ("outbound", "You got it! Booked for next Saturday at 10:00 AM with Anthony, same as usual. Classic Haircut. Deposit link coming your way."),
        ("inbound", "Thanks man"),
    ],
    # Review follow-up
    [
        ("outbound", "Thanks for coming in today! How was your cut with David?"),
        ("inbound", "Looks great as always. You guys are the best"),
        ("outbound", "Glad to hear it! If you have a moment, a Google review would mean the world to us. See you next time!"),
    ],
]

APPOINTMENT_NOTES = [
    "Wants a low fade, skin on sides",
    "Regular client, same cut as last time",
    "First time visit, referred by Mike",
    "Prefers scissors on top, #2 guard sides",
    "Has a wedding next week, wants something sharp",
    "Beard shape-up after the cut",
    "Running late, called ahead 10 min",
    "Wants to try something new",
    "Kid's cut - age 8, wiggly",
    "Hot towel treatment after cut",
    "Line-up only, quick appointment",
    "",  # Some have no notes
    "",
    "",
]


def generate_demo_data(shop_id: str, now: datetime = None):
    """Generate all demo data for a shop. Returns dict of collection -> documents."""
    if now is None:
        now = datetime.now(timezone.utc)

    # ======================== CLIENTS ========================
    num_clients = 15
    clients = []
    all_names = []
    for _ in range(num_clients):
        if random.random() < 0.8:
            first = random.choice(FIRST_NAMES_M)
        else:
            first = random.choice(FIRST_NAMES_F)
        last = random.choice(LAST_NAMES)
        name = f"{first} {last}"
        while name in all_names:
            last = random.choice(LAST_NAMES)
            name = f"{first} {last}"
        all_names.append(name)

        area = random.choice(["555", "212", "347", "718", "917", "646"])
        phone = f"+1{area}{random.randint(1000000, 9999999)}"
        created_days_ago = random.randint(7, 90)

        clients.append({
            "id": uid(),
            "shop_id": shop_id,
            "name": name,
            "phone": phone,
            "email": f"{first.lower()}.{last.lower()}@email.com" if random.random() < 0.4 else "",
            "sms_consent": True,
            "sms_consent_date": (now - timedelta(days=created_days_ago)).isoformat(),
            "notes": random.choice(["Regular", "New client", "VIP", "Referred by friend", ""]),
            "no_show_count": 0,
            "total_appointments": 0,
            "tags": random.sample(["regular", "new", "vip", "walk-in", "referred"], k=random.randint(0, 2)),
            "created_at": (now - timedelta(days=created_days_ago)).isoformat(),
        })

    # ======================== BARBERS ========================
    barbers = []
    for bp in BARBER_PROFILES:
        barbers.append({
            "id": uid(),
            "shop_id": shop_id,
            "name": bp["name"],
            "email": bp["email"],
            "phone": bp["phone"],
            "active": True,
            "created_at": (now - timedelta(days=60)).isoformat(),
        })

    # ======================== SERVICES ========================
    services = []
    for sm in SERVICE_MENU:
        services.append({
            "id": uid(),
            "shop_id": shop_id,
            "name": sm["name"],
            "description": sm["description"],
            "duration_minutes": sm["duration_minutes"],
            "price": sm["price"],
            "active": True,
            "created_at": (now - timedelta(days=60)).isoformat(),
        })

    # ======================== APPOINTMENTS ========================
    appointments = []
    statuses_pool = (
        ["completed"] * 70 +
        ["confirmed"] * 8 +
        ["pending"] * 3 +
        ["no_show"] * 8 +
        ["cancelled"] * 5 +
        ["deposit_paid"] * 4 +
        ["deposit_pending"] * 2
    )

    # Busy hours: 9-12, 1-5. Busier on Fri/Sat.
    for day_offset in range(30, -1, -1):
        day = now - timedelta(days=day_offset)
        weekday = day.weekday()

        # More appointments on Fri(4)/Sat(5), fewer on Sun(6)/Mon(0)
        if weekday in (4, 5):
            num_apts = random.randint(6, 10)
        elif weekday == 6:
            num_apts = random.randint(1, 3)
        elif weekday == 0:
            num_apts = random.randint(2, 5)
        else:
            num_apts = random.randint(3, 7)

        for _ in range(num_apts):
            client = random.choice(clients)
            barber = random.choice(barbers)
            service = random.choice(services)

            # Realistic hours: 9am - 6pm
            hour = random.choice([9, 9, 10, 10, 10, 11, 11, 11, 12, 13, 13, 14, 14, 15, 15, 16, 16, 17])
            minute = random.choice([0, 0, 0, 30, 30])
            apt_time = day.replace(hour=hour, minute=minute, second=0, microsecond=0)

            if day_offset == 0:
                status = random.choice(["confirmed", "pending", "deposit_paid", "deposit_pending"])
            elif day_offset <= 2:
                status = random.choice(["confirmed", "confirmed", "deposit_paid", "pending"])
            else:
                status = random.choice(statuses_pool)

            deposit_required = random.random() < 0.6
            deposit_paid = deposit_required and status in ("deposit_paid", "completed", "confirmed")
            deposit_amount = 20.0 if deposit_required else 0

            apt_id = uid()
            appointments.append({
                "id": apt_id,
                "shop_id": shop_id,
                "client_id": client["id"],
                "barber_id": barber["id"],
                "service_id": service["id"],
                "scheduled_at": apt_time.isoformat(),
                "duration_minutes": service["duration_minutes"],
                "status": status,
                "price": service["price"],
                "notes": random.choice(APPOINTMENT_NOTES),
                "deposit_required": deposit_required,
                "deposit_paid": deposit_paid,
                "deposit_amount": deposit_amount,
                "created_at": (apt_time - timedelta(days=random.randint(1, 5))).isoformat(),
            })

    # Update client appointment counts and no-show counts
    for client in clients:
        client_apts = [a for a in appointments if a["client_id"] == client["id"]]
        client["total_appointments"] = len(client_apts)
        client["no_show_count"] = sum(1 for a in client_apts if a["status"] == "no_show")

    # ======================== MESSAGES / CONVERSATIONS ========================
    messages = []
    msg_counter = 0
    conv_clients = random.sample(clients, min(10, len(clients)))

    for i, client in enumerate(conv_clients):
        template = CONVERSATION_TEMPLATES[i % len(CONVERSATION_TEMPLATES)]
        base_time = now - timedelta(days=random.randint(0, 14), hours=random.randint(1, 12))

        for j, (direction, body) in enumerate(template):
            msg_counter += 1
            msg_time = base_time + timedelta(minutes=j * random.randint(2, 30))
            messages.append({
                "id": f"msg_demo_{msg_counter}",
                "shop_id": shop_id,
                "client_id": client["id"],
                "direction": direction,
                "body": body,
                "channel": "sms",
                "status": "delivered",
                "created_at": msg_time.isoformat(),
            })

    # ======================== EVENTS ========================
    events = []

    for apt in appointments:
        if apt["status"] == "completed":
            events.append({
                "id": uid(), "shop_id": shop_id,
                "event_type": "appointment_completed",
                "client_id": apt["client_id"],
                "appointment_id": apt["id"],
                "revenue_impact": apt["price"],
                "data": {"service": next((s["name"] for s in services if s["id"] == apt["service_id"]), ""), "barber": next((b["name"] for b in barbers if b["id"] == apt["barber_id"]), "")},
                "created_at": apt["scheduled_at"],
            })
        elif apt["status"] == "no_show":
            events.append({
                "id": uid(), "shop_id": shop_id,
                "event_type": "no_show",
                "client_id": apt["client_id"],
                "appointment_id": apt["id"],
                "revenue_impact": -apt["price"],
                "data": {"service": next((s["name"] for s in services if s["id"] == apt["service_id"]), "")},
                "created_at": apt["scheduled_at"],
            })

    # Deposit events
    for apt in appointments:
        if apt["deposit_paid"]:
            events.append({
                "id": uid(), "shop_id": shop_id,
                "event_type": "deposit_paid",
                "client_id": apt["client_id"],
                "appointment_id": apt["id"],
                "revenue_impact": apt["deposit_amount"],
                "data": {},
                "created_at": (datetime.fromisoformat(apt["scheduled_at"]) - timedelta(days=1)).isoformat(),
            })

    # ======================== TRANSACTIONS ========================
    transactions = []
    for apt in appointments:
        if apt["deposit_paid"]:
            transactions.append({
                "id": uid(),
                "shop_id": shop_id,
                "appointment_id": apt["id"],
                "client_id": apt["client_id"],
                "type": "deposit",
                "amount": apt["deposit_amount"],
                "currency": "usd",
                "status": "completed",
                "stripe_session_id": f"cs_demo_{uid()[:8]}",
                "created_at": (datetime.fromisoformat(apt["scheduled_at"]) - timedelta(days=1)).isoformat(),
            })

    # ======================== RECOVERED REVENUE ========================
    recovered_revenue = []
    # Waitlist fills
    no_show_apts = [a for a in appointments if a["status"] == "no_show"]
    for apt in random.sample(no_show_apts, min(8, len(no_show_apts))):
        svc = next((s for s in services if s["id"] == apt["service_id"]), services[0])
        recovered_revenue.append({
            "id": uid(), "shop_id": shop_id,
            "event_id": uid(), "event_type": "waitlist_filled",
            "source": "waitlist_fill",
            "client_id": random.choice(clients)["id"],
            "amount": svc["price"],
            "notes": svc["name"],
            "created_at": apt["scheduled_at"],
            "attributed_at": apt["scheduled_at"],
        })
    # No-show fees
    for apt in random.sample(no_show_apts, min(5, len(no_show_apts))):
        recovered_revenue.append({
            "id": uid(), "shop_id": shop_id,
            "event_id": uid(), "event_type": "revenue_recovered",
            "source": "no_show_fee",
            "client_id": apt["client_id"],
            "amount": apt["deposit_amount"] if apt["deposit_amount"] > 0 else 20.0,
            "notes": "No-show deposit retained",
            "created_at": apt["scheduled_at"],
            "attributed_at": apt["scheduled_at"],
        })

    # ======================== WAITLIST ========================
    waitlist = []
    for _ in range(random.randint(2, 5)):
        client = random.choice(clients)
        service = random.choice(services)
        waitlist.append({
            "id": uid(), "shop_id": shop_id,
            "client_id": client["id"],
            "service_id": service["id"],
            "preferred_barber_id": random.choice(barbers)["id"] if random.random() < 0.5 else None,
            "preferred_date": (now + timedelta(days=random.randint(0, 3))).strftime("%Y-%m-%d"),
            "preferred_time": random.choice(["morning", "afternoon", "any"]),
            "status": "waiting",
            "notes": random.choice(["Flexible on time", "ASAP please", "After 2pm only", ""]),
            "created_at": (now - timedelta(hours=random.randint(1, 48))).isoformat(),
        })

    return {
        "clients": clients,
        "barbers": barbers,
        "services": services,
        "appointments": appointments,
        "messages": messages,
        "events": events,
        "transactions": transactions,
        "recovered_revenue_events": recovered_revenue,
        "waitlist": waitlist,
    }
