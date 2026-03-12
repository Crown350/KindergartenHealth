import random
from datetime import datetime, timedelta
from database import Database

# --- Constants ---
GROUPS = ["Солнышко", "Ромашка", "Пчёлки", "Звёздочки", "Капельки", "Сказка"]

MALE_NAMES = ["Александр", "Дмитрий", "Максим", "Сергей", "Андрей", "Алексей", "Артём", "Илья", "Кирилл", "Михаил"]
FEMALE_NAMES = ["Анна", "Мария", "Елена", "Дарья", "Алина", "Полина", "Виктория", "Екатерина", "Анастасия", "София"]

LAST_NAMES_M = ["Иванов", "Смирнов", "Кузнецов", "Попов", "Васильев", "Петров", "Соколов", "Михайлов", "Новиков", "Фёдоров"]
LAST_NAMES_F = ["Иванова", "Смирнова", "Кузнецова", "Попова", "Васильева", "Петрова", "Соколова", "Михайлова", "Новикова", "Фёдорова"]

PATRONYMICS_M = ["Александрович", "Дмитриевич", "Максимович", "Сергеевич", "Андреевич", "Алексеевич"]
PATRONYMICS_F = ["Александровна", "Дмитриевна", "Максимовна", "Сергеевна", "Андреевна", "Алексеевна"]

DIAGNOSES = ["ОРВИ", "Грипп", "Ветрянка", "Ангина", "Здоров", "Аллергия", "Бронхит"]
VACCINES = ["Манту", "БЦЖ", "АКДС", "Полиомиелит", "Корь", "Краснуха", "Гепатит В"]
HEALTH_TYPES = ["Illness", "Anthropometry", "Checkup"]

def generate_fio(gender):
    if gender == 'M':
        return f"{random.choice(LAST_NAMES_M)} {random.choice(MALE_NAMES)} {random.choice(PATRONYMICS_M)}"
    return f"{random.choice(LAST_NAMES_F)} {random.choice(FEMALE_NAMES)} {random.choice(PATRONYMICS_F)}"

def random_date(start_year=2018, end_year=2021):
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    return (start + timedelta(days=random.randrange(delta.days))).strftime("%Y-%m-%d")

def random_recent_date(days=365):
    start = datetime.now() - timedelta(days=days)
    end = datetime.now()
    delta = end - start
    return (start + timedelta(days=random.randrange(delta.days))).strftime("%Y-%m-%d")

def seed_database():
    db = Database()
    
    print("Clearing old data...")
    # Order matters due to FKs
    tables = ["attendance", "vaccinations", "health_records", "parents", "children", "groups"]
    for t in tables:
        db.cursor.execute(f"DELETE FROM {t}")
    db.conn.commit()

    print("Seeding Groups...")
    group_ids = []
    for g in GROUPS:
        db.add_group(g)
        # Fetch ID back
        db.cursor.execute("SELECT id FROM groups WHERE name=?", (g,))
        group_ids.append(db.cursor.fetchone()['id'])

    print("Seeding Children & Parents...")
    child_ids = []
    for _ in range(30):
        gender = random.choice(['M', 'F'])
        fio = generate_fio(gender)
        dob = random_date()
        gid = random.choice(group_ids)
        
        cid = db.add_child(fio, dob, gid)
        child_ids.append(cid)
        
        # Add 1-2 parents
        for _ in range(random.randint(1, 2)):
            p_gender = random.choice(['M', 'F'])
            p_fio = generate_fio(p_gender)
            phone = f"+7 (9{random.randint(10, 99)}) {random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(10, 99)}"
            db.add_parent(cid, p_fio, phone)

    print("Seeding Health Records & Vaccinations...")
    for _ in range(50):
        cid = random.choice(child_ids)
        date = random_recent_date()
        rtype = random.choice(HEALTH_TYPES)
        
        desc, h, w, diag = "", None, None, ""
        
        if rtype == "Illness":
            diag = random.choice(DIAGNOSES)
            desc = "Жалобы на температуру"
        elif rtype == "Anthropometry":
            h = random.randint(90, 120)
            w = random.randint(14, 25)
            desc = "Плановое измерение"
        else:
            desc = "Плановый осмотр педиатра"
            diag = "Здоров"
            
        db.add_health_record(cid, date, rtype, desc, h, w, diag)

    for _ in range(50):
        cid = random.choice(child_ids)
        vac = random.choice(VACCINES)
        date = random_recent_date(days=700)
        status = random.choice(["Done", "Done", "Refused"])
        db.add_vaccination(cid, vac, date, status)
        
    print("Seeding Attendance...")
    for _ in range(100):
        cid = random.choice(child_ids)
        date = random_recent_date(days=30)
        status = random.choice(["Present", "Present", "Sick", "Absent"])
        db.mark_attendance(cid, date, status)

    db.close()
    print("Database seeded successfully!")

if __name__ == "__main__":
    seed_database()
