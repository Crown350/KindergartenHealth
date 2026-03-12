-- Скрипт создания БД для MS SQL Server
-- Проект: KindergartenHealth

CREATE TABLE groups (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE children (
    id INT IDENTITY(1,1) PRIMARY KEY,
    full_name NVARCHAR(255) NOT NULL,
    birth_date DATE NOT NULL,
    group_id INT,
    photo_path NVARCHAR(500),
    allergies NVARCHAR(MAX),
    FOREIGN KEY (group_id) REFERENCES groups(id)
);

CREATE TABLE parents (
    id INT IDENTITY(1,1) PRIMARY KEY,
    child_id INT,
    full_name NVARCHAR(255) NOT NULL,
    phone NVARCHAR(50),
    FOREIGN KEY (child_id) REFERENCES children(id) ON DELETE CASCADE
);

CREATE TABLE health_records (
    id INT IDENTITY(1,1) PRIMARY KEY,
    child_id INT,
    record_date DATE NOT NULL,
    record_type NVARCHAR(50) NOT NULL,
    description NVARCHAR(MAX),
    height FLOAT,
    weight FLOAT,
    diagnosis NVARCHAR(255),
    FOREIGN KEY (child_id) REFERENCES children(id) ON DELETE CASCADE
);

CREATE TABLE vaccinations (
    id INT IDENTITY(1,1) PRIMARY KEY,
    child_id INT,
    vaccine_name NVARCHAR(255) NOT NULL,
    date_administered DATE NOT NULL,
    status NVARCHAR(50),
    FOREIGN KEY (child_id) REFERENCES children(id) ON DELETE CASCADE
);

CREATE TABLE attendance (
    id INT IDENTITY(1,1) PRIMARY KEY,
    child_id INT,
    date DATE NOT NULL,
    status NVARCHAR(50) NOT NULL, -- 'Present', 'Sick', 'Absent'
    FOREIGN KEY (child_id) REFERENCES children(id) ON DELETE CASCADE,
    CONSTRAINT UQ_Attendance_Child_Date UNIQUE(child_id, date)
);
